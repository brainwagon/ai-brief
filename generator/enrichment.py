"""Enrichment: putting one Item to the local model for a Score and a Synopsis.

Everything here is settled on #5. The parts that are load-bearing and easy to
get wrong, in order:

- A dead Ollama HANGS under WSL2 rather than refusing, so the pre-flight GET at
  a 3s timeout is mandatory. Without it a 300-Item Run blocks for hours before
  publishing an all-Unenriched Edition.
- `done_reason` is checked BEFORE the JSON is parsed. A truncated generation
  comes back HTTP 200 with `done: true` and half an object in `content`.
- The schema is compiled into the decoding grammar, so a missing field or an
  out-of-range Score is effectively unreachable. An EMPTY `synopsis` is the
  real failure mode, and it arrives with `done_reason: "stop"`.
- One retry, unchanged, then the Item is Unenriched. There is never a
  fabricated Score: a guessed 3 is indistinguishable from an earned one and
  would quietly corrupt the Pick pass, which reads Scores.

Ollama is not a Source, so it is never Unavailable. When it cannot be reached,
the correct description is that every Item in the Edition is Unenriched.
"""

import json
import time

import requests

from . import config

SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 5},
        "synopsis": {"type": "string"},
    },
    "required": ["score", "synopsis"],
    "additionalProperties": False,
}


def build_system_prompt():
    """The Prompt with the Rubric interpolated. One substitution, nothing else.

    The Prompt never restates taste and the Rubric never mentions JSON, so
    editing taste cannot break the model call.
    """
    prompt = config.PROMPT_FILE.read_text(encoding="utf-8")
    rubric = config.RUBRIC_FILE.read_text(encoding="utf-8")
    if "{{RUBRIC}}" not in prompt:
        raise RuntimeError(f"{config.PROMPT_FILE} carries no {{{{RUBRIC}}}} placeholder")
    return prompt.replace("{{RUBRIC}}", rubric)


def reachable(log, host=None):
    """The mandatory pre-flight. Short timeout, because a dead port blackholes."""
    host = host or config.OLLAMA_HOST
    try:
        response = requests.get(host + "/", timeout=config.OLLAMA_PREFLIGHT_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        log(f"  Ollama pre-flight failed ({type(exc).__name__}) — "
            f"every Item in this Edition will be Unenriched")
        return False
    if response.status_code != 200:
        log(f"  Ollama pre-flight returned HTTP {response.status_code} — "
            f"every Item in this Edition will be Unenriched")
        return False
    return True


class Enricher:
    def __init__(self, system_prompt, log, host=None, model=None):
        self.system_prompt = system_prompt
        self.log = log
        self.host = host or config.OLLAMA_HOST
        self.model = model or config.OLLAMA_MODEL
        # Set when the fault is in the request builder rather than the data:
        # a 404 for a missing model, a 400, a 500. Retrying that per Item just
        # wastes the morning, so the rest of the Run goes Unenriched.
        self.fatal = False

    def enrich(self, item):
        """Set item.score and item.synopsis, or leave the Item Unenriched."""
        if self.fatal:
            return

        user = f"Title: {item.title}\nText: {item.text}".strip()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user},
            ],
            "format": SCHEMA,
            # ~5x faster with no quality loss on this task; reasoning would
            # land in a separate `thinking` field and is not wanted.
            "think": False,
            "stream": False,
            # Holds the model resident for the rest of the Run without
            # touching any global Ollama config.
            "keep_alive": "5m",
        }
        # options.num_predict is deliberately never set. The default is
        # unbounded, and a hand-set value is the easiest way to reintroduce
        # silent truncation.

        for attempt in (1, 2):
            result = self._attempt(payload, item)
            if result is not None:
                item.score, item.synopsis = result
                return
            if self.fatal:
                return
        # Two identical draws both failed. Sampling is stochastic, so a third
        # has never bought anything; the Item is Unenriched and the Run goes on.

    def _attempt(self, payload, item):
        try:
            response = requests.post(
                self.host + "/api/chat",
                json=payload,
                timeout=config.OLLAMA_ITEM_TIMEOUT,
            )
        except requests.exceptions.RequestException as exc:
            self.log(f"  Enrichment transport fault on {item.identity}: "
                     f"{type(exc).__name__}")
            return None

        if response.status_code != 200:
            # Not per-Item data — a bug in the request builder or a missing
            # model. Log loudly and stop calling.
            self.fatal = True
            self.log(f"  Enrichment HTTP {response.status_code}: "
                     f"{response.text[:200]} — remaining Items are Unenriched")
            return None

        try:
            body = response.json()
        except ValueError:
            self.log(f"  Enrichment body did not parse as JSON on {item.identity}")
            return None

        # done_reason BEFORE parsing the content. A truncated generation
        # reports HTTP 200 and `done: true`.
        if body.get("done_reason") != "stop":
            self.log(f"  Enrichment done_reason={body.get('done_reason')!r} "
                     f"on {item.identity}")
            return None

        content = (body.get("message") or {}).get("content") or ""
        try:
            parsed = json.loads(content)
        except ValueError:
            self.log(f"  Enrichment content did not parse as JSON on {item.identity}")
            return None

        score = parsed.get("score")
        synopsis = parsed.get("synopsis")
        if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
            self.log(f"  Enrichment Score {score!r} out of range on {item.identity}")
            return None
        if not isinstance(synopsis, str) or not synopsis.strip():
            # The one check that genuinely earns its place.
            self.log(f"  Enrichment returned an empty Synopsis on {item.identity}")
            return None

        return score, " ".join(synopsis.split())


def enrich_all(items, log, host=None, model=None):
    """Enrich every Item, sequentially, one request in flight at a time.

    Measured at ~1.0-1.3s/Item warm, plus a one-time ~6s cold load. Concurrency
    was tested on #5 and buys ~2 minutes on the worst realistic day at the cost
    of a 6x worse tail; a bad trade in a job that runs once a morning.
    """
    if not items:
        return
    enricher = Enricher(build_system_prompt(), log, host=host, model=model)
    started = time.time()
    for index, item in enumerate(items, 1):
        enricher.enrich(item)
        if index % 25 == 0:
            log(f"  Enriched {index}/{len(items)} "
                f"({time.time() - started:.0f}s elapsed)")
    unenriched = sum(1 for item in items if item.unenriched)
    log(f"  Enrichment finished: {len(items)} Items in "
        f"{time.time() - started:.0f}s, {unenriched} Unenriched")
