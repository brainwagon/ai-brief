"""The Decoder — one request per Run against its RSS feed.

A European AI-news desk: model releases, vendors, and EU regulation, which is
the one beat none of the existing nine covers. The feed is rss 2.0 with a
stable `<guid>` (`?p=NNNNN`), so the Snapshot diff carries novelty and the
72-hour window only keeps the feed's own latency from losing a quiet day.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from ..fetch import get, Unavailable
from ..item import Item

KEY = "the-decoder"

ENDPOINT = "https://the-decoder.com/feed/"

WINDOW_HOURS = 72

DC = "{http://purl.org/dc/elements/1.1/}"

TEXT_LIMIT = 1500


def fetch(run_at):
    response = get(ENDPOINT)

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise Unavailable(f"response body did not parse as RSS: {exc}")

    channel = root.find("channel")
    entries = channel.findall("item") if channel is not None else []
    if not entries:
        raise Unavailable("RSS feed carried zero entries")

    cutoff = run_at - timedelta(hours=WINDOW_HOURS)
    seen, items = [], []

    for entry in entries:
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
