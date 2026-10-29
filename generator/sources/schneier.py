"""Schneier on Security — one request per Run against its RSS feed.

Bruce Schneier's blog: security research, policy and, increasingly, AI —
model backdoors, AI cryptanalysis, misuse reports. Its value is the choosing:
one reader with long judgement picking a paper or story a day.

The whole-blog feed is read, not the `ai` tag: the tag misses posts that are
plainly about models (2026-10-26's "Bias in Qwen3-Coder Model" was untagged).
That brings in squid and PHP patches too, and the Score drops them. Posting is
about one a weekday, so the 72-hour window carries a weekend; the stable
`<guid>` (`?p=NNNNN`) lets the Snapshot diff carry novelty.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from ..fetch import get, Unavailable
from ..item import Item

KEY = "schneier"

ENDPOINT = "https://www.schneier.com/feed/"

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
