"""WIRED AI tag — one request per Run against its RSS feed.

WIRED publishes on its own rhythm, and the tag feed's "latest" listing is
already newest-first, so the bare 24-hour window some Sources rely on would
leave a quiet ai-tag day silent. The window here is a few days and the
Snapshot diff is what actually stops a story being carried twice.

The feed is a small handful of Items, so there is no noise gate and nothing to
pre-rank by: everything fresh goes to the model and the Score does the
choosing.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from ..fetch import get, Unavailable
from ..item import Item

KEY = "wired"

ENDPOINT = "https://www.wired.com/feed/tag/ai/latest/rss"

# Stories surface in the feed as much as three days before a quiet tag day
# catches them; the Snapshot diff already stops a second Run republishing.
WINDOW_HOURS = 72

DC = "{http://purl.org/dc/elements/1.1/}"

# The `<description>` is a short kicker, but bytes are bytes: clean it of any
# markup so Enrichment reads prose, not tags.
TEXT_LIMIT = 1500


def fetch(run_at):
    response = get(ENDPOINT)

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise Unavailable(f"response body did not parse as RSS: {exc}")

    items_node = root.find("channel")
    entries = items_node.findall("item") if items_node is not None else []
    if not entries:
        # WIRED posts several AI stories a week, so an empty feed means the
        # tag broke, not that the day was quiet.
        raise Unavailable("RSS feed carried zero entries")

    cutoff = run_at - timedelta(hours=WINDOW_HOURS)
    seen, items = [], []

    for entry in entries:
        # The `<guid>` is the stable key: the same story ID across re-issues,
        # where the URL slug is at the story's whim.
        identity = _text(entry, "guid")
        if not identity:
            continue
        seen.append(identity)

        published = _parse_time(_text(entry, "pubDate"))
        if published is None or published < cutoff:
            continue

        url = _text(entry, "link")
        if not url:
            continue

        meta = []
        author = _text(entry, DC + "creator")
        if author:
            meta.append(author)
        if published:
            meta.append("published %s" % published.strftime("%-d %b"))

        items.append(
            Item(
                source=KEY,
                identity=identity,
                title=_collapse(_text(entry, "title")),
                url=url,
                text=_clean(_text(entry, "description")),
                meta=" · ".join(meta),
            )
        )

    return items, seen


def _clean(description):
    if not description:
        return ""
    soup = BeautifulSoup(description, "html.parser")
    return _collapse(soup.get_text(" "))[:TEXT_LIMIT]


def _text(element, path):
    found = element.find(path)
    return found.text if found is not None and found.text else ""


def _collapse(text):
    return " ".join(text.split())


def _parse_time(value):
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None
