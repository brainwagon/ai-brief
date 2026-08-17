"""The second pass: choosing the day's Picks from the high scorers.

Map note 3 fixes the shape — the model scores each Item independently first,
and only a second pass over the *high scorers* picks the headline Items. It
never ranks the whole day in one prompt.

This pass is allowed to fail. If it does, the Edition carries no `picks`
section and not one Item's rendering changes (#6). That is the property that
made the anchor-list design worth having, so nothing here may raise.
"""

import json

import requests

from . import config

MAX_PICKS = 4
SHORTLIST_MAX = 12

SCHEMA = {
    "type": "object",
    "properties": {
        "picks": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["picks"],
    "additionalProperties": False,
}


def shortlist(items):
    """The high scorers, best first, capped so the prompt stays small.

    Score 4 and above is the shortlist. If the day produced fewer than three of
    those, 3s are added — a thin day still deserves a Pick — but a day with
    nothing above the cutoff gets none.
    """
    scored = [item for item in items if item.score is not None]
    high = sorted(
        [item for item in scored if item.score >= 4],
        key=lambda item: (-item.score, item.rank),
    )
    if len(high) < 3:
        rest = sorted(
            [item for item in scored if item.score == 3],
            key=lambda item: item.rank,
        )
        high = high + rest
    return high[:SHORTLIST_MAX]


def choose(items, log, host=None, model=None):
    """Mark the Picks in place. Returns the Picks in order, or an empty list."""
    candidates = shortlist(items)
    if len(candidates) < 2:
        log("  Picks: shortlist too short, no second pass")
        return []

    try:
        system = _system_prompt()
    except Exception as exc:  # noqa: BLE001
        log(f"  Picks: could not build the prompt ({exc}); no Picks")
        return []

    lines = []
    for number, item in enumerate(candidates, 1):
        lines.append(
            "%d. [%s] Score %d — %s\n   %s"
            % (
                number,
                config.SOURCE_LABELS[item.source],
                item.score,
                item.title,
                item.synopsis or "",
            )
        )
    user = "\n".join(lines)

    payload = {
        "model": model or config.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "format": SCHEMA,
        "think": False,
        "stream": False,
        "keep_alive": "5m",
    }

    try:
        response = requests.post(
            (host or config.OLLAMA_HOST) + "/api/chat",
            json=payload,
            timeout=config.OLLAMA_ITEM_TIMEOUT,
        )
        if response.status_code != 200:
            log(f"  Picks: HTTP {response.status_code}; no Picks")
            return []
        body = response.json()
        if body.get("done_reason") != "stop":
            log(f"  Picks: done_reason={body.get('done_reason')!r}; no Picks")
            return []
        parsed = json.loads((body.get("message") or {}).get("content") or "")
        numbers = parsed.get("picks")
        if not isinstance(numbers, list):
            log("  Picks: `picks` was not a list; no Picks")
            return []
    except Exception as exc:  # noqa: BLE001 - Picks degrade to nothing
        log(f"  Picks: {type(exc).__name__}: {exc}; no Picks")
        return []

    picks = []
    for number in numbers:
        if not isinstance(number, int) or isinstance(number, bool):
            continue
        if not 1 <= number <= len(candidates):
            continue
        item = candidates[number - 1]
        if item not in picks:
            picks.append(item)
        if len(picks) == MAX_PICKS:
            break

    for item in picks:
        item.is_pick = True
    log(f"  Picks: {len(picks)} of {len(candidates)} shortlisted")
    return picks


def _system_prompt():
    prompt = config.PICK_PROMPT_FILE.read_text(encoding="utf-8")
    rubric = config.RUBRIC_FILE.read_text(encoding="utf-8")
    if "{{RUBRIC}}" not in prompt:
        raise RuntimeError(
            f"{config.PICK_PROMPT_FILE} carries no {{{{RUBRIC}}}} placeholder"
        )
    return prompt.replace("{{RUBRIC}}", rubric)
