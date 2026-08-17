"""arXiv — one request per Run against export.arxiv.org. Pinned on #4.

Novelty here is two conditions, both required: a 96-hour window on `published`
(a literal 24 hours returns nothing on most Runs, because arXiv announces
6-30h late and a Monday is ~62h behind Friday's batch), plus the Identity being
absent from the previous Snapshot so Friday's batch is not republished for
three days running.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from ..fetch import get, Unavailable
from ..item import Item

KEY = "arxiv"

ENDPOINT = (
    "https://export.arxiv.org/api/query"
    "?search_query=cat:cs.AI+OR+cat:cs.LG+OR+cat:cs.CL+OR+cat:cs.CV+OR+cat:stat.ML"
    "&start=0&max_results=40&sortBy=submittedDate&sortOrder=descending"
)

CATEGORIES = {"cs.AI", "cs.LG", "cs.CL", "cs.CV", "stat.ML"}
WINDOW_HOURS = 96

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def fetch(run_at):
    response = get(ENDPOINT, polite_host="arxiv")

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise Unavailable(f"response body did not parse as Atom: {exc}")

    entries = root.findall(f"{ATOM}entry")
    if not entries:
        # arXiv always has recent papers, so an empty feed means the query
        # broke, not that the day was quiet (#4).
        raise Unavailable("Atom feed carried zero entries")

    cutoff = run_at - timedelta(hours=WINDOW_HOURS)
    seen, items = [], []

    for entry in entries:
        # Parse INSIDE the entry. A document-level <updated> precedes the first
        # <entry>, so anything reading the feed whole misaligns published and
        # updated by one (#4).
        raw_id = _text(entry, f"{ATOM}id")
        if not raw_id:
            continue
        identity = _strip_version(raw_id.rsplit("/", 1)[-1])
        seen.append(identity)

        published = _parse_time(_text(entry, f"{ATOM}published"))
        if published is None or published < cutoff:
            continue

        # The OR-query matches on ANY category tag, so returned papers carry
        # tags outside the five. Re-check client-side rather than assume —
        # the assumption is what would break silently.
        tags = [
            c.get("term")
            for c in entry.findall(f"{ATOM}category")
            if c.get("term")
        ]
        if not CATEGORIES.intersection(tags):
            continue

        title = _collapse(_text(entry, f"{ATOM}title"))
        summary = _collapse(_text(entry, f"{ATOM}summary"))
        url = f"https://arxiv.org/abs/{identity}"
        for link in entry.findall(f"{ATOM}link"):
            if link.get("rel") == "alternate" and link.get("href"):
                url = link.get("href")

        primary = entry.find(f"{ARXIV_NS}primary_category")
        shown = [t for t in tags if t in CATEGORIES] or tags
        if primary is not None and primary.get("term"):
            shown = [primary.get("term")] + [
                t for t in shown if t != primary.get("term")
            ]

        items.append(
            Item(
                source=KEY,
                identity=identity,
                title=title,
                url=url,
                text=summary,
                meta="%s · submitted %s"
                % (", ".join(shown[:2]), published.strftime("%-d %b")),
            )
        )

    return items, seen


def _strip_version(tail):
    """`2608.14546v1` -> `2608.14546`, so a v2 is not a new Item."""
    if "v" in tail:
        head, _, version = tail.rpartition("v")
        if head and version.isdigit():
            return head
    return tail


def _text(element, path):
    found = element.find(path)
    return found.text if found is not None and found.text else ""


def _collapse(text):
    return " ".join(text.split())


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
