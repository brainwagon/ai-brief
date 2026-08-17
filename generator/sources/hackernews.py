"""Hacker News, through the Algolia search API. Pinned on #4.

The 24-hour window is in the query itself, so novelty needs no Snapshot here —
but the Run records one anyway, uniformly with the other six, so that a second
Run on the same day does not republish the same stories.

`points > 75` is a noise gate, not a selector: it took a real 770-story day
down to 29 candidates. The Score does the choosing after that.
"""

from urllib.parse import quote

from .. import config
from ..fetch import get_json, Unavailable
from ..item import Item

KEY = "hackernews"


def fetch(run_at):
    run_ts = int(run_at.timestamp())
    numeric = f"created_at_i>{run_ts - 86400},created_at_i<{run_ts}"
    url = (
        "https://hn.algolia.com/api/v1/search_by_date"
        "?tags=story"
        f"&numericFilters={quote(numeric, safe=',')}"
        "&hitsPerPage=1000"
    )

    body = get_json(url)
    if not isinstance(body, dict) or "hits" not in body:
        raise Unavailable("response body carried no `hits` key")

    candidates = []
    for hit in body["hits"]:
        identity = hit.get("objectID")
        if not identity:
            continue

        points = hit.get("points") or 0
        if points <= config.HN_POINTS_FLOOR:
            continue

        # `url` is null on text posts (Ask HN, Tell HN); fall back to the
        # discussion, which is the whole Item in that case.
        url_out = hit.get("url") or f"https://news.ycombinator.com/item?id={identity}"
        comments = hit.get("num_comments") or 0

        candidates.append(
            (
                points,
                Item(
                    source=KEY,
                    identity=identity,
                    title=" ".join((hit.get("title") or "").split()),
                    url=url_out,
                    # Hacker News arrives as bare titles. That is the known
                    # weakness recorded on #7, not a gap to paper over.
                    text=hit.get("story_text") or "",
                    meta=f"{points:,} points · {comments:,} comments",
                ),
            )
        )

    # Rank by points before Enrichment so a trimmed Run is trimmed from the
    # bottom, and so 29 candidates do not go to the model to fill 8 slots (#4).
    candidates.sort(key=lambda pair: -pair[0])
    items = [item for _, item in candidates[: config.HN_ENRICH_LIMIT]]
    # The Snapshot records only what was put forward, not all ~900 stories in
    # the window. The query's own 24-hour filter is what supplies novelty here;
    # the Snapshot only has to stop a second Run republishing the first Run's
    # Items, and recording the whole day would grow committed state by a
    # megabyte a month for nothing.
    return items, [item.identity for item in items]
