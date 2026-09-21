"""Stage B: writing a Synopsis for each Item the Edition will carry.

Stage A (`jev.py`) has already scored every Item. The cutoff and the ceiling
have already run in `select.select`, so `items` here is the survivors — the
twenty-five or so that will actually be rendered. That is the whole point of the
split: a Synopsis is only written for an Item the reader can see, where the old
single-pass Enrichment wrote one for every considered Item and threw most away.

The transport, retries and parsing live in `model.py`. What is settled here is
the ask and what happens when it comes back empty:

- One retry beyond the transport's own, then the Item keeps its Source's raw
  title. There is never a fabricated Synopsis.
- An EMPTY Synopsis is the real failure mode, and is checked for.
- Items are written several at a time. This is a network call — latency-bound,
  not compute-bound — so requests in flight together are what makes the pass
  take seconds. The Items are mutated in place, so nothing is reordered.

A Synopsis and a Score fail independently: this stage failing leaves an Edition
whose Items carry Scores and raw titles, which `render` states on the page.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import config
from .model import Client, reachable  # noqa: F401 - `reachable` is re-exported

SCHEMA = {
    "type": "object",
    "properties": {
        "synopsis": {"type": "string"},
    },
    "required": ["synopsis"],
    "additionalProperties": False,
}


def build_system_prompt():
    """The Synopsis Prompt, read from disk. No Rubric, and no substitution.

    The Rubric is Stage A's concern now; this Prompt never saw it and is smaller
    for it.
    """
    return config.SYNOPSIS_PROMPT_FILE.read_text(encoding="utf-8")


class Synopsiser:
    def __init__(self, system_prompt, log, base=None, model=None):
        self.system_prompt = system_prompt
        self.log = log
        self.client = Client(log, base=base, model=model)

    @property
    def fatal(self):
        return self.client.fatal

    def write(self, item):
        """Set item.synopsis, or leave the Item carrying its raw title."""
        user = f"Title: {item.title}\nText: {item.text}".strip()

        for _ in (1, 2):
            if self.client.fatal:
                return
            parsed = self.client.complete(
                self.system_prompt, user, SCHEMA, "synopsis", item.identity
            )
            if parsed is None:
                continue
            synopsis = parsed.get("synopsis")
            if not isinstance(synopsis, str) or not synopsis.strip():
                # The one check that genuinely earns its place.
                self.log(f"  Synopsis came back empty on {item.identity}")
                continue
            item.synopsis = " ".join(synopsis.split())
            return
        # Two draws both came back unusable. The Item keeps its raw title and
        # the Run goes on.


def synopsise_all(items, log, base=None, model=None):
    """Write a Synopsis for each Item, a few requests in flight at a time.

    The log is written from several threads, so it is serialised behind a lock;
    a Run's output is read as a narrative and interleaved half-lines would ruin
    it.
    """
    if not items:
        return

    lock = threading.Lock()

    def safe_log(message):
        with lock:
            log(message)

    writer = Synopsiser(build_system_prompt(), safe_log, base=base, model=model)
    started = time.time()
    done = 0

    def work(item):
        nonlocal done
        writer.write(item)
        with lock:
            done += 1
            if done % 10 == 0:
                log(f"  Synopsised {done}/{len(items)} "
                    f"({time.time() - started:.0f}s elapsed)")

    with ThreadPoolExecutor(max_workers=config.OPENROUTER_CONCURRENCY) as pool:
        list(pool.map(work, items))

    unwritten = sum(1 for item in items if not (item.synopsis or "").strip())
    log(f"  Synopsis finished: {len(items)} Items in "
        f"{time.time() - started:.0f}s, {unwritten} left with a raw title")
