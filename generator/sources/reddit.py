"""r/LocalLLaMA, through Reddit's Atom feed of the subreddit's hot listing.

The feed is 25 entries and carries no score and no comment count — the JSON
endpoints that do are the ones Reddit gates behind OAuth, and `.rss` is served
to a plain User-Agent. So there is no noise gate here and nothing to pre-rank
by: all 25 go to the model, and the Score does the choosing.

Novelty is the Snapshot diff alone, as with the Hugging Face trending lists.
The listing is hot-ordered rather than chronological, so a post can surface
days after it was submitted; a published-time window would drop exactly those
and the diff already stops anything being carried twice.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from ..fetch import get, Unavailable
from ..item import Item

KEY = "reddit"

ENDPOINT = "https://www.reddit.com/r/LocalLLaMA.rss"

ATOM = "{http://www.w3.org/2005/Atom}"

# A self-post body can run to thousands of words. Enrichment reads the opening
# of it, which is where the claim always is.
TEXT_LIMIT = 1500


def fetch(run_at):
    response = get(ENDPOINT)

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise Unavailable(f"response body did not parse as Atom: {exc}")

    entries = root.findall(f"{ATOM}entry")
    if not entries:
        # The subreddit posts every day, so an empty feed means Reddit served
        # something other than the listing, not that nothing was posted.
        raise Unavailable("Atom feed carried zero entries")

    seen, items = [], []
    for entry in entries:
        # `t3_1vzxdui` is the fullname; the `t3_` prefix is the kind and is
        # the same on every entry, so the Identity is the post id alone.
        raw_id = _text(entry, f"{ATOM}id")
        if not raw_id:
            continue
        identity = raw_id.split("_", 1)[1] if raw_id.startswith("t3_") else raw_id
        seen.append(identity)

        link = entry.find(f"{ATOM}link")
        url = link.get("href") if link is not None else ""
        if not url:
            continue

        posted = _parse_time(_text(entry, f"{ATOM}published"))

        meta = []
        author = entry.find(f"{ATOM}author")
        if author is not None and _text(author, f"{ATOM}name"):
            meta.append(_text(author, f"{ATOM}name"))
        if posted:
            meta.append("posted %s" % posted.strftime("%-d %b"))

        items.append(
            Item(
                source=KEY,
                identity=identity,
                title=_collapse(_text(entry, f"{ATOM}title")),
                url=url,
                text=_body(_text(entry, f"{ATOM}content")),
                meta=" · ".join(meta),
            )
        )

    return items, seen


def _body(content):
    """The self-post text out of the entry's HTML, or nothing.

    A link post's content is a thumbnail and the `[link] [comments]` pair, and
    that carries no more than the title already does — an Item with no text is
    normal and Enrichment handles it.
    """
    if not content:
        return ""
    soup = BeautifulSoup(content, "html.parser")
    md = soup.find("div", class_="md")
    if md is None:
        return ""
    return _collapse(md.get_text(" "))[:TEXT_LIMIT]


def _text(element, path):
    found = element.find(path)
    return found.text if found is not None and found.text else ""


def _collapse(text):
    return " ".join(text.split())


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except ValueError:
        return None
