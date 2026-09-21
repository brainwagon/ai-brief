"""Stage A: putting every Item to Jev for a Score.

Jev is TypeSafe's System One decision model, reached through OpenRouter's
Decisions endpoint. It answers typed questions about a piece of text and returns
calibrated probabilities — a `score` position on an ordered ladder, a `choice`,
or a `noul`, which is the probability that a statement holds. It does not
generate prose, so it cannot write a Synopsis; that is Stage B (`synopsis.py`).

The transport is deliberately not `model.py`. That module speaks
chat/completions with a strict `json_schema` response format and a `finish_reason`
check; this endpoint speaks `{model, state, questions}` and answers
`{answers}`. What the two share is the discipline, copied here on purpose:

- The budget per call is WALL CLOCK, enforced in `_post`, because a provider
  that accepts a request and then sits on it would otherwise hold a worker for
  as long as it likes.
- A 429 or a 5xx is TRANSIENT and retried; a 400/401/402/404 is the request or
  the account, is the same for every Item, and is fatal — the rest of the Run
  scores nothing rather than making 300 identical mistakes.
- There is never a fabricated Score. A guessed 3 is indistinguishable from an
  earned one and would quietly corrupt selection, which reads Scores.

The Score is not Jev's answer alone. Jev supplies the ladder position and the
noul probabilities; the adjustment policy in `jev-questions.json` — the Rubric's
named exceptions, as arithmetic — turns those into the Score the Brief uses.
Jev answers its questions independently, so the combination is ours by
necessity, and it lives in an editable file rather than here.
"""

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from . import config

TRANSIENT = (429, 500, 502, 503, 504)


class Stalled(requests.exceptions.RequestException):
    """The wall-clock budget ran out with the answer still pending."""


def api_key():
    """The key, or None. Absent is a legitimate state: a Score-less Edition."""
    key = os.environ.get(config.OPENROUTER_KEY_ENV, "").strip()
    return key or None


# A stated PARAMETER count under 1B, which is what the Rubric's size point is
# for. The number must sit next to a parameter word: a bare "1M" once matched
# "1M-token context windows" and "240M domain names", neither of which is a model
# size. Copied from calibration/2026-09-06-retune/check-editions.py.
SUB1B = re.compile(
    r"\b(\d{1,3}(?:\.\d+)?\s?[MmKk]|0\.\d+\s?B)[\s-]*(param|parameter|weights?\b)"
    r"|\b(param|parameter)\w*[\s:-]*(\d{1,3}(?:\.\d+)?\s?[MmKk]|0\.\d+\s?B)\b",
    re.I,
)


def sub_1b(title, text):
    """The Rubric's stated-size rule, detected rather than asked of Jev.

    Jev is documented as unable to count or do arithmetic, so a magnitude
    comparison is the one question that should not be put to it.
    """
    return bool(SUB1B.search(f"{title} {text}"))


# The Score's five levels are read from `rubric.md`, not repeated in
# `jev-questions.json`: one home per fact. The format is the one the Rubric has
# always used — a level is a bold `**N — label**` line and the prose under it,
# running until the next level. The Rubric is still also read whole by the Pick
# pass, so this adds no new file to keep in step.
_LEVEL_RE = re.compile(r"^\*\*([1-5])\s+—\s+(.+?)\*\*\s*$")
_HEADING_RE = re.compile(r"^##\s+")


def _scale_lines(rubric):
    lines = rubric.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().lower() == "## the scale":
            start = index + 1
            break
    if start is None:
        raise RuntimeError(f"{config.RUBRIC_FILE} has no `## The scale` section")
    section = []
    for line in lines[start:]:
        if _HEADING_RE.match(line):
            break
        section.append(line)
    return section


def _clean(text):
    return " ".join(text.replace("*", "").split())


def levels_from_rubric(rubric):
    """Return (preamble, {"N - ..." criterion for N in 1..5}) from the Rubric.

    Everything before the first level line is the preamble — the "start every
    Item at 2" sentence — and is folded into the question's instructions by
    `Policy`. A missing level raises here, so a malformed edit stops the Run
    before a network call rather than after two hundred Scores.
    """
    preamble, levels, current, body = [], {}, None, []
    for line in _scale_lines(rubric):
        match = _LEVEL_RE.match(line)
        if match:
            if current is not None:
                levels[current] = f"{current} - {_clean(' '.join(body))}"
            current, body = int(match.group(1)), [match.group(2)]
        elif current is not None:
            body.append(line)
        else:
            preamble.append(line)
    if current is not None:
        levels[current] = f"{current} - {_clean(' '.join(body))}"
    missing = [level for level in range(1, 6) if level not in levels]
    if missing:
        raise RuntimeError(
            f"{config.RUBRIC_FILE} scale is missing level(s) {missing}"
        )
    return _clean(" ".join(preamble)), levels


class Policy:
    """The editable question set and the arithmetic that turns it into a Score.

    The Score ladder is compiled from `rubric.md`; the noul definitions, the
    question phrasing and the adjustment policy come from
    `jev-questions.json`. Neither fact is written down twice.
    """

    def __init__(self, document, rubric):
        preamble, levels = levels_from_rubric(rubric)
        instructions = document.get("score_instructions", "").strip()
        if preamble:
            instructions = f"{instructions} {preamble}".strip()
        self.questions = {
            "score": {
                "type": "score",
                "instructions": instructions,
                "criteria": [levels[level] for level in range(1, 6)],
            }
        }
        self.questions.update(document.get("nouls", {}))
        self.adjustment = document.get("adjustment", [])
        self.threshold = float(document.get("threshold", 0.5))
        self.nouls = [
            name for name, spec in self.questions.items()
            if spec.get("type") == "noul"
        ]


def load_policy():
    document = json.loads(config.JEV_QUESTIONS_FILE.read_text(encoding="utf-8"))
    rubric = config.RUBRIC_FILE.read_text(encoding="utf-8")
    return Policy(document, rubric)


def apply_adjustment(level, probabilities, stated_under_1b, policy):
    """Apply the Rubric's named exceptions to Jev's ladder position, in order.

    The policy is a list of rules, each keyed on a noul (or the detected
    `sub_1b`). `set` replaces the Score, `cap` lowers it no further than a
    value, `add` raises it no further than a value, and `blocks_boost` stops the
    later size point from applying — the Rubric says that point does not apply
    to a quantised re-upload.
    """
    score = level
    blocked = False
    for rule in policy.adjustment:
        when = rule["when"]
        if when == "sub_1b":
            if blocked or not stated_under_1b:
                continue
            add = rule.get("add", 1)
            score = min(score + add, rule.get("cap", score + add))
            continue
        if (probabilities.get(when) or 0.0) < policy.threshold:
            continue
        if "set" in rule:
            score = rule["set"]
        if "cap" in rule:
            score = min(score, rule["cap"])
        if rule.get("blocks_boost"):
            blocked = True
    return max(1, min(5, score))


def reachable(log, base=None):
    """The pre-flight: a key, and a Decisions endpoint that answers.

    Turns the commonest failure — an unset key in a systemd unit's environment —
    into one clear line instead of hundreds of identical faults.
    """
    base = base or config.JEV_BASE
    key = api_key()
    if not key:
        log(f"  {config.OPENROUTER_KEY_ENV} is unset — no Item will carry a Score")
        return False
    payload = {
        "model": config.JEV_MODEL,
        "state": "probe",
        "questions": {
            "ok": {"type": "noul", "instructions": "Is this text non-empty?"},
        },
    }
    try:
        response = requests.post(
            base, headers=_headers(key), json=payload,
            timeout=config.JEV_PREFLIGHT_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        log(f"  Jev pre-flight failed ({type(exc).__name__}) — no Score today")
        return False
    if response.status_code != 200:
        log(f"  Jev pre-flight returned HTTP {response.status_code} — no Score today")
        return False
    if not response.json().get("answers"):
        log("  Jev pre-flight returned no answers — no Score today")
        return False
    return True


def _headers(key):
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # OpenRouter attributes traffic by these; the Brief identifies itself.
        "HTTP-Referer": config.SITE_URL,
        "X-Title": "ai-brief",
    }


class Answer:
    """A status code and a fully-read body, gathered inside one deadline."""

    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body


class Client:
    """One Jev model, one key, one `fatal` flag shared across every call."""

    def __init__(self, policy, log, base=None, model=None, timeout=None):
        self.policy = policy
        self.log = log
        self.base = base or config.JEV_BASE
        self.model = model or config.JEV_MODEL
        self.timeout = timeout or config.JEV_ITEM_TIMEOUT
        self.key = api_key()
        self.fatal = False

    def ask(self, state, label):
        """Return the `answers` object, or None and the caller degrades."""
        if self.fatal:
            return None
        payload = {
            "model": self.model,
            "state": state,
            "questions": self.policy.questions,
        }
        for attempt in range(1, config.JEV_ATTEMPTS + 1):
            answers, retry = self._attempt(payload, label)
            if answers is not None:
                return answers
            if self.fatal or not retry:
                return None
            if attempt < config.JEV_ATTEMPTS:
                time.sleep(config.JEV_BACKOFF * attempt)
        return None

    def _post(self, payload):
        """POST and read the body, giving up on the clock rather than the socket."""
        deadline = time.monotonic() + self.timeout
        response = requests.post(
            self.base,
            headers=_headers(self.key),
            json=payload,
            timeout=(config.OPENROUTER_CONNECT_TIMEOUT, self.timeout),
            stream=True,
        )
        chunks = []
        try:
            for chunk in response.iter_content(chunk_size=8192):
                chunks.append(chunk)
                if time.monotonic() > deadline:
                    raise Stalled("wall-clock budget exhausted")
        finally:
            response.close()
        return Answer(
            response.status_code, b"".join(chunks).decode("utf-8", "replace")
        )

    def _attempt(self, payload, label):
        """Return (answers, retry). `retry` says whether another draw is worth it."""
        try:
            response = self._post(payload)
        except Stalled:
            self.log(f"  Jev stalled past {self.timeout:.0f}s on {label}; retrying")
            return None, True
        except requests.exceptions.RequestException as exc:
            self.log(f"  Jev transport fault on {label}: {type(exc).__name__}")
            return None, True

        if response.status_code in TRANSIENT:
            self.log(f"  Jev HTTP {response.status_code} on {label}; retrying")
            return None, True

        if response.status_code != 200:
            self.fatal = True
            self.log(f"  Jev HTTP {response.status_code}: {response.body[:200]} — "
                     f"remaining Items are Unenriched")
            return None, False

        try:
            body = json.loads(response.body)
        except ValueError:
            self.log(f"  Jev body did not parse as JSON on {label}")
            return None, True

        error = body.get("error")
        if error:
            code = error.get("code") if isinstance(error, dict) else None
            self.log(f"  Jev error {code!r} on {label}: {str(error)[:160]}")
            return None, code in TRANSIENT or code is None

        answers = body.get("answers")
        if not isinstance(answers, dict):
            self.log(f"  Jev returned no answers on {label}")
            return None, True
        return answers, True


def _level(answer):
    """Jev's probability-weighted position on the ladder, as an integer 1-5.

    The ladder is zero-based, so the mean is shifted before rounding. The mean,
    not the mode: measured against the human reference it agrees more closely.
    """
    value = (answer or {}).get("score")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    level = round(value) + 1
    return level if 1 <= level <= 5 else None


def score_all(items, log, base=None, model=None):
    """Score every Item, a few requests in flight at a time.

    The log is written from several threads, so it is serialised behind a lock;
    a Run's output is read as a narrative and interleaved half-lines would ruin
    it. Items are mutated in place, so nothing is reordered and `rank` holds.
    """
    if not items:
        return

    policy = load_policy()
    lock = threading.Lock()

    def safe_log(message):
        with lock:
            log(message)

    client = Client(policy, safe_log, base=base, model=model)
    started = time.time()
    done = 0

    def work(item):
        nonlocal done
        state = f"Title: {item.title}\nText: {item.text}".strip()
        answers = client.ask(state, item.identity)
        if answers is not None:
            level = _level(answers.get("score"))
            if level is not None:
                probabilities = {
                    name: (answers.get(name) or {}).get("noul")
                    for name in policy.nouls
                }
                stated_small = sub_1b(item.title, item.text)
                item.raw_score = level
                item.noul = probabilities
                item.score_confidence = (answers.get("score") or {}).get("confidence")
                item.sub_1b = stated_small
                item.score = apply_adjustment(level, probabilities, stated_small, policy)
            else:
                safe_log(f"  Jev Score unusable on {item.identity}")
        with lock:
            done += 1
            if done % 25 == 0:
                log(f"  Scored {done}/{len(items)} ({time.time() - started:.0f}s elapsed)")

    with ThreadPoolExecutor(max_workers=config.JEV_CONCURRENCY) as pool:
        list(pool.map(work, items))

    unscored = sum(1 for item in items if item.score is None)
    log(f"  Scoring finished: {len(items)} Items in {time.time() - started:.0f}s, "
        f"{unscored} with no Score")
