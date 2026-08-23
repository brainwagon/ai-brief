"""Which Items make the Edition.

The rules, settled on #7:

- **The cutoff never moves.** Score >= 3 is absolute and is never relaxed to
  fill a quota. A Source with 0, 1 or 2 qualifying Items contributes exactly
  that many. A padded Item is indistinguishable on the page from an earned one.
- **The ceiling is 8 Items per Source**, a hard cap, counted against a stream.
- **The floor is a cap that yields, not a quota.** Its work is trim
  protection: no Source is trimmed below 3 Items while any other Source still
  holds more than 3. If every Source is down to 3 and the Edition is still
  over, the floor yields rather than the target.

One rule this ticket had to settle, because no earlier ticket reached it:
**an Unenriched Item has no Score, so the cutoff cannot judge it.** It is
admitted in its Source's pre-Enrichment rank order, subject to the same ceiling
of 8, and sorts below every scored Item for trimming. Without that, an outage at
the model would put several hundred raw titles on the page instead of an
Edition.
"""

from . import config


def dedup_papers(results):
    """Hugging Face papers and arXiv share a key form, so the overlap is a
    key collision rather than a guess. The Hugging Face copy wins, because it
    carries upvotes (map note 8).
    """
    papers = results.get("hf-papers")
    arxiv = results.get("arxiv")
    if not papers or not arxiv or papers.unavailable or arxiv.unavailable:
        return 0
    hf_ids = {item.identity for item in papers.items}
    before = len(arxiv.items)
    arxiv.items = [item for item in arxiv.items if item.identity not in hf_ids]
    for position, item in enumerate(arxiv.items):
        item.rank = position
    return before - len(arxiv.items)


def _sort_key(item):
    """Scored Items first, best Score first; Unenriched last, in rank order."""
    if item.score is None:
        return (1, 0, item.rank)
    return (0, -item.score, item.rank)


def select(results):
    """Apply the cutoff and the ceiling per Source, then trim toward the target.

    Mutates each SourceResult.items down to what the Edition carries, and
    returns the Items that were dropped only as a count.
    """
    for result in results.values():
        if result.unavailable:
            result.items = []
            continue
        kept = [
            item
            for item in result.items
            if item.unenriched or item.score >= config.CUTOFF
        ]
        kept.sort(key=_sort_key)
        result.items = kept[: config.CEILING]

    _trim(results)


def _trim(results):
    """Trim by ascending Score across the whole day, with the floor protecting
    Sources, until the Edition is at the target."""
    def total():
        return sum(len(result.items) for result in results.values())

    while total() > config.EDITION_MAX:
        eligible = [
            result
            for result in results.values()
            if len(result.items) > config.FLOOR
        ]
        if not eligible:
            # Every Source is at or below the floor and the Edition is still
            # over the target. The floor yields; it was never a quota.
            eligible = [result for result in results.values() if result.items]
        if not eligible:
            return

        worst_result = None
        worst_key = None
        for result in eligible:
            candidate = result.items[-1]  # already sorted worst-last
            key = _sort_key(candidate)
            if worst_key is None or key > worst_key:
                worst_key, worst_result = key, result
        worst_result.items.pop()
