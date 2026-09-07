"""The model transport: one OpenRouter call, retried, parsed, or nothing.

Enrichment and the Pick pass both put text to a model and both want the same
thing back — a JSON object matching a schema, or nothing at all. This is that
call, in one place, so the two callers differ only in prompt and schema.

The parts that are load-bearing and easy to get wrong, in order:

- The budget per call is WALL CLOCK, enforced by hand in `_post`. OpenRouter
  dribbles whitespace down the connection while a generation is pending, which
  resets the socket read timeout every few hundred milliseconds — so
  `requests`' `timeout=` alone never fires on the failure that actually
  happens, and one stalled draw can hold a worker for the length of the Run.
- `models` carries a fallback list; OpenRouter walks it when the first choice
  errors, so a provider's outage or 429 costs a few seconds rather than the
  morning. Every model in that list must accept the `reasoning` field below as
  well as the schema — an endpoint that refuses to have reasoning disabled says
  so with a 400, which is fatal here by design.
- A 429 or a 5xx is TRANSIENT and retried with backoff. A 400/401/402/404 is
  the request builder or the account, is the same for every Item, and is fatal:
  the rest of the Run goes Unenriched rather than making 300 identical
  mistakes. 402 is the one to recognise on sight — the model is paid for now,
  so an empty account reads as an all-Unenriched Edition and nothing worse.
- `finish_reason` is checked BEFORE the JSON is parsed. A truncated generation
  comes back HTTP 200 with half an object in `content`.
- The schema is sent as a strict `json_schema` response format, so a missing
  field or an out-of-range Score is close to unreachable. An EMPTY string field
  is the real failure mode, and it arrives with `finish_reason: "stop"`.
- There is never a fabricated answer. A guessed Score of 3 is indistinguishable
  from an earned one and would quietly corrupt the Pick pass, which reads
  Scores.

OpenRouter is not a Source, so it is never Unavailable. When it cannot be
reached, the correct description is that every Item in the Edition is
Unenriched.
"""

import json
import os
import time

import requests

from . import config

# Retried rather than given up on: the provider is busy, not the request wrong.
TRANSIENT = (429, 500, 502, 503, 504)


class Stalled(requests.exceptions.RequestException):
    """The wall-clock budget ran out with the generation still pending."""


def api_key():
    """The key, or None. Absent is a legitimate state: an Unenriched Edition."""
    key = os.environ.get(config.OPENROUTER_KEY_ENV, "").strip()
    return key or None


def reachable(log, base=None):
    """The pre-flight: a key, and an endpoint that answers.

    Cheap, and it turns the commonest failure — an unset key in a systemd
    unit's environment — into one clear line instead of 300 identical 401s.
    """
    base = base or config.OPENROUTER_BASE
    key = api_key()
    if not key:
        log(f"  {config.OPENROUTER_KEY_ENV} is unset — "
            f"every Item in this Edition will be Unenriched")
        return False
    try:
        response = requests.get(
            base + "/key",
            headers={"Authorization": f"Bearer {key}"},
            timeout=config.OPENROUTER_PREFLIGHT_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        log(f"  OpenRouter pre-flight failed ({type(exc).__name__}) — "
            f"every Item in this Edition will be Unenriched")
        return False
    if response.status_code != 200:
        log(f"  OpenRouter pre-flight returned HTTP {response.status_code} — "
            f"every Item in this Edition will be Unenriched")
        return False
    return True


class Answer:
    """A status code and a fully-read body, gathered inside one deadline."""

    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body


class Client:
    """One model, one key, one `fatal` flag shared across every call."""

    def __init__(self, log, base=None, model=None, timeout=None):
        self.log = log
        self.base = base or config.OPENROUTER_BASE
        self.model = model or config.OPENROUTER_MODEL
        self.timeout = timeout or config.OPENROUTER_ITEM_TIMEOUT
        self.key = api_key()
        # Set when the fault is in the request builder or the account rather
        # than the data: a 401, a 404 for a retired model, a 400. Retrying that
        # per Item just wastes the morning, so the rest of the Run stops.
        self.fatal = False

    def complete(self, system, user, schema, schema_name, label):
        """Return the parsed object, or None and the caller degrades.

        `label` names the thing being worked on in the log — an Item's
        Identity, or the Pick pass.
        """
        if self.fatal:
            return None

        payload = {
            "model": self.model,
            # OpenRouter's own fallback: when the first model errors or is
            # rate-limited upstream, it tries the next without a round trip
            # back to us.
            "models": [self.model] + [
                m for m in config.OPENROUTER_FALLBACK_MODELS if m != self.model
            ],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
            # Reasoning would be slow and would land in a separate field this
            # task has no use for.
            "reasoning": {"enabled": False},
            "stream": False,
        }
        # max_tokens is deliberately never set. Unbounded is the default, and a
        # hand-set value is the easiest way to reintroduce silent truncation.

        for attempt in range(1, config.OPENROUTER_ATTEMPTS + 1):
            parsed, retry = self._attempt(payload, label)
            if parsed is not None:
                return parsed
            if self.fatal or not retry:
                return None
            if attempt < config.OPENROUTER_ATTEMPTS:
                time.sleep(config.OPENROUTER_BACKOFF * attempt)
        return None

    def _post(self, payload):
        """POST and read the body, giving up on the clock rather than the socket.

        `stream=True` hands back the response as soon as the headers land, so
        the status is known before a single keepalive byte is read; the body is
        then drained chunk by chunk with the deadline checked between chunks. A
        generation that is never going to arrive is abandoned in seconds rather
        than holding a worker open for as long as the provider likes.
        """
        deadline = time.monotonic() + self.timeout
        response = requests.post(
            self.base + "/chat/completions",
            headers={
                "Authorization": f"Bearer {self.key}",
                # OpenRouter attributes free-model traffic by these; the Brief
                # identifies itself here as it does to every Source.
                "HTTP-Referer": config.SITE_URL,
                "X-Title": "ai-brief",
            },
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
        """Return (parsed, retry). `retry` says whether another draw is worth it."""
        try:
            response = self._post(payload)
        except Stalled:
            self.log(f"  Model stalled past {self.timeout:.0f}s on {label}; retrying")
            return None, True
        except requests.exceptions.RequestException as exc:
            self.log(f"  Model transport fault on {label}: {type(exc).__name__}")
            return None, True

        if response.status_code in TRANSIENT:
            # Upstream congestion or a rate limit. Every model in the fallback
            # list was busy; waiting is the whole remedy.
            self.log(f"  Model HTTP {response.status_code} on {label}; retrying")
            return None, True

        if response.status_code != 200:
            # Not per-Item data — the key, the account, or a retired model.
            self.fatal = True
            self.log(f"  Model HTTP {response.status_code}: "
                     f"{response.body[:200]} — remaining Items are Unenriched")
            return None, False

        try:
            body = json.loads(response.body)
        except ValueError:
            self.log(f"  Model body did not parse as JSON on {label}")
            return None, True

        # An error can arrive inside an HTTP 200 when every fallback model
        # failed; it carries no `choices`.
        error = body.get("error")
        if error:
            code = error.get("code") if isinstance(error, dict) else None
            self.log(f"  Model error {code!r} on {label}: {str(error)[:160]}")
            return None, code in TRANSIENT or code is None

        choices = body.get("choices") or []
        if not choices:
            self.log(f"  Model returned no choices on {label}")
            return None, True
        choice = choices[0]

        # finish_reason BEFORE parsing the content. A truncated generation
        # reports HTTP 200 and a well-formed envelope.
        if choice.get("finish_reason") != "stop":
            self.log(f"  Model finish_reason={choice.get('finish_reason')!r} on {label}")
            return None, True

        content = (choice.get("message") or {}).get("content") or ""
        try:
            parsed = json.loads(content)
        except ValueError:
            self.log(f"  Model content did not parse as JSON on {label}")
            return None, True
        if not isinstance(parsed, dict):
            self.log(f"  Model content was not an object on {label}")
            return None, True
        return parsed, True
