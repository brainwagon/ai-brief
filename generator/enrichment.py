"""Enrichment: putting one Item to the model for a Score and a Synopsis.

The transport, the retries and the parsing all live in `model.py`, which both
this and the Pick pass share. What is settled here is the shape of the ask and
what happens when it comes back empty:

- One retry beyond the transport's own, then the Item is Unenriched. There is
  never a fabricated Score: a guessed 3 is indistinguishable from an earned one
  and would quietly corrupt the Pick pass, which reads Scores.
- The schema pins the Score to 1-5, so an out-of-range Score is close to
  unreachable. An EMPTY Synopsis is the real failure mode and is checked for.
- Items are Enriched several at a time. This is a network call now rather than
  a local one — latency-bound, not compute-bound — so requests in flight
  together are what makes a 300-Item Run take minutes instead of an hour. The
  Items are mutated in place, so nothing is reordered and `rank` still holds.

OpenRouter is not a Source, so it is never Unavailable. When it cannot be
reached, the correct description is that every Item in the Edition is
Unenriched.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import config
from .model import Client, reachable  # noqa: F401 - `reachable` is re-exported

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


class Enricher:
    def __init__(self, system_prompt, log, base=None, model=None):
        self.system_prompt = system_prompt
        self.log = log
        self.client = Client(log, base=base, model=model)

    @property
    def fatal(self):
        return self.client.fatal

    def enrich(self, item):
        """Set item.score and item.synopsis, or leave the Item Unenriched."""
        user = f"Title: {item.title}\nText: {item.text}".strip()

        for _ in (1, 2):
            if self.client.fatal:
                return
            parsed = self.client.complete(
                self.system_prompt, user, SCHEMA, "enrichment", item.identity
            )
            if parsed is None:
                continue
            score = parsed.get("score")
            synopsis = parsed.get("synopsis")
            if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
                self.log(f"  Enrichment Score {score!r} out of range on {item.identity}")
                continue
            if not isinstance(synopsis, str) or not synopsis.strip():
                # The one check that genuinely earns its place.
                self.log(f"  Enrichment returned an empty Synopsis on {item.identity}")
                continue
            item.score = score
            item.synopsis = " ".join(synopsis.split())
            return
        # Two draws both came back unusable. Sampling is stochastic, so a third
        # has never bought anything; the Item is Unenriched and the Run goes on.


def enrich_all(items, log, base=None, model=None):
    """Enrich every Item, a few requests in flight at a time.

    The log is written from several threads, so it is serialised behind a lock;
    a Run's output is read as a narrative and interleaved half-lines would
    ruin it.
    """
    if not items:
        return

    lock = threading.Lock()

    def safe_log(message):
        with lock:
            log(message)

    enricher = Enricher(build_system_prompt(), safe_log, base=base, model=model)
    started = time.time()
    done = 0

    def work(item):
        nonlocal done
        enricher.enrich(item)
        with lock:
            done += 1
            if done % 25 == 0:
                log(f"  Enriched {done}/{len(items)} "
                    f"({time.time() - started:.0f}s elapsed)")

    with ThreadPoolExecutor(max_workers=config.OPENROUTER_CONCURRENCY) as pool:
        list(pool.map(work, items))

    unenriched = sum(1 for item in items if item.unenriched)
    log(f"  Enrichment finished: {len(items)} Items in "
        f"{time.time() - started:.0f}s, {unenriched} Unenriched")
