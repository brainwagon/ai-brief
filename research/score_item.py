#!/usr/bin/env python3
"""
score_item.py — score ONE item end-to-end against a live Ollama instance.

Minimal working demonstration for research/gemma4-structured-output.md
(ai-brief issue #5). Fail-soft by design: on any error (connection refused,
bad HTTP status, malformed/truncated JSON, timeout) it prints an error to
stderr and exits non-zero WITHOUT raising, so a caller can catch the
failure and fall back to "no synopsis" rather than crash the brief.

Usage:
    python3 score_item.py "Title text" "Abstract or body text"

Example:
    python3 score_item.py "Attention Is All You Need" \\
        "The dominant sequence transduction models are based on complex \\
         recurrent or convolutional neural networks..."

Prints a single line of JSON on success: {"score": N, "synopsis": "..."}
"""
import json
import sys
import time
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:e4b"
TIMEOUT_S = 30  # generous; empirical p50 is ~1.2s/item, warm, think:false

SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 1, "maximum": 5},
        "synopsis": {"type": "string"},
    },
    "required": ["score", "synopsis"],
}

SYSTEM_PROMPT = (
    "You are an item scorer for an AI news brief. Score how interesting or "
    "important the item is to an AI practitioner audience on a 1-5 scale "
    "(5 = must-see, 1 = skip) and write a one-sentence synopsis."
)


def score_item(title: str, text: str, keep_alive: str = "5m") -> dict:
    """Score one item. Raises on any failure — caller should catch and
    fall back to a raw-title-only entry (no synopsis)."""
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Title: {title}\nAbstract/Text: {text}"},
        ],
        "format": SCHEMA,
        "think": False,  # empirically: thinking adds ~5-6s/item hidden latency
                          # for no measurable quality gain on this task; disable it.
        "stream": False,
        "keep_alive": keep_alive,
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        raw = resp.read()
        payload = json.loads(raw)

    if payload.get("done_reason") not in ("stop", None):
        # e.g. "length" == truncated before valid JSON completed
        raise ValueError(f"model did not finish cleanly: done_reason={payload.get('done_reason')!r}")

    content = payload["message"]["content"]
    parsed = json.loads(content)  # may raise json.JSONDecodeError

    if not isinstance(parsed.get("score"), int) or not (1 <= parsed["score"] <= 5):
        raise ValueError(f"score out of range or missing: {parsed!r}")
    if not isinstance(parsed.get("synopsis"), str) or not parsed["synopsis"].strip():
        raise ValueError(f"synopsis missing/empty: {parsed!r}")

    return {"score": parsed["score"], "synopsis": parsed["synopsis"].strip()}


def main() -> int:
    if len(sys.argv) < 3:
        print(f"usage: {sys.argv[0]} TITLE TEXT", file=sys.stderr)
        return 2
    title, text = sys.argv[1], sys.argv[2]

    t0 = time.time()
    try:
        result = score_item(title, text)
    except urllib.error.URLError as e:
        print(f"ERROR: could not reach Ollama at {OLLAMA_URL}: {e}", file=sys.stderr)
        return 1
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"ERROR: bad/unusable response from model: {e}", file=sys.stderr)
        return 1
    except TimeoutError:
        print(f"ERROR: request timed out after {TIMEOUT_S}s", file=sys.stderr)
        return 1

    elapsed = time.time() - t0
    print(json.dumps(result))
    print(f"# elapsed: {elapsed:.2f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
