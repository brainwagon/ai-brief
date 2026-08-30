"""The eight Sources, and the one function that gathers them.

Every Source is fail-soft: a fault becomes an Unavailable SourceResult with a
reason the page can print, and never an exception out of a Run (map note 10).
"""

from ..fetch import Unavailable
from ..item import SourceResult
from . import arxiv, devto, github, hackernews, huggingface, reddit

# key -> the callable that issues that Source's request(s)
FETCHERS = {
    arxiv.KEY: arxiv.fetch,
    hackernews.KEY: hackernews.fetch,
    github.KEY: github.fetch,
    devto.KEY: devto.fetch,
    reddit.KEY: reddit.fetch,
    huggingface.MODELS_KEY: huggingface.fetch_models,
    huggingface.DATASETS_KEY: huggingface.fetch_datasets,
    huggingface.PAPERS_KEY: huggingface.fetch_papers,
}


def gather(key, run_at, log):
    """Fetch one Source. Returns a SourceResult, Unavailable or not."""
    started = run_at.strftime("%H:%M")
    try:
        items, seen = FETCHERS[key](run_at)
    except Unavailable as exc:
        log(f"  {key}: Unavailable — {exc}")
        return SourceResult(
            key=key,
            unavailable=True,
            reason=f"1 attempt, {started} UTC · last: {exc}",
        )
    except Exception as exc:  # noqa: BLE001 - a Source may never crash a Run
        log(f"  {key}: Unavailable — unexpected {type(exc).__name__}: {exc}")
        return SourceResult(
            key=key,
            unavailable=True,
            reason=f"1 attempt, {started} UTC · last: {type(exc).__name__}: {exc}",
        )

    for position, item in enumerate(items):
        item.rank = position
    log(f"  {key}: {len(items)} candidates from {len(seen)} fetched")
    return SourceResult(key=key, items=items, seen=seen)
