"""dev.to — one request per tag, three tags. Pinned on #4.

The ordering trap: the default listing is NOT chronological, and a 1000-item
page spans four days unsorted. Pull the whole page for each tag and sort
client-side; never stop early because results "look old", because the newest
article can sit anywhere in the page.

A fault on any one of the three tags marks the whole Source Unavailable — a
partial tag set would silently skew the day's selection, which is worse than an
honest hole.
"""

import time
from datetime import datetime, timedelta, timezone

from .. import config
from ..fetch import get_json, Unavailable
from ..item import Item

KEY = "devto"

TAGS = ["ai", "llm", "machinelearning"]


def fetch(run_at):
    cutoff = run_at - timedelta(hours=24)

    by_identity = {}
    for index, tag in enumerate(TAGS):
        if index:
            time.sleep(1.0)  # self-imposed: no published rate limit exists
        body = get_json(f"https://dev.to/api/articles?tag={tag}&per_page=1000")
        if not isinstance(body, list):
            raise Unavailable(f"tag `{tag}` did not return a JSON array")
        for article in body:
            identity = article.get("id")
            if identity is None:
                continue
            # Roughly a third of the 3000 fetched articles are multi-tag
            # duplicates; dedup by Identity before anything else.
            by_identity.setdefault(str(identity), article)

    candidates = []
    for identity, article in by_identity.items():
        published = _parse_time(article.get("published_at"))
        if published is None or published < cutoff:
            continue

        reactions = article.get("public_reactions_count") or 0
        candidates.append(
            (
                reactions,
                Item(
                    source=KEY,
                    identity=identity,
                    title=" ".join((article.get("title") or "").split()),
                    url=article.get("url") or "",
                    text=(article.get("description") or "").strip(),
                    meta="%d reactions · published %s"
                    % (reactions, published.strftime("%-d %b")),
                ),
            )
        )

    # dev.to is the lowest-signal Source in the set and its 24-hour union runs
    # to hundreds. Pre-rank by reactions and put only the top few to the model.
    candidates.sort(key=lambda pair: -pair[0])
    items = [item for _, item in candidates[: config.DEVTO_ENRICH_LIMIT]]
    # As with Hacker News: the Snapshot records what was put forward, not all
    # ~2100 unique articles, because the 24-hour window already supplies the
    # novelty and committed state should not grow by a megabyte a month.
    return items, [item.identity for item in items]


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
