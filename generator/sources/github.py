"""GitHub New Repos, through the documented search API. Pinned on #4 and #10.

The HTML scrape of github.com/trending is dead — robots.txt disallows
`/*since=*`, which is literally the planned fetch — so this Source reads the
search API and is named for what it now returns.

The 7-day creation window is a candidate pool, not a novelty signal: stars take
days to accumulate, so a 24-hour window returns junk. Novelty is the Snapshot
diff — a repo that has just climbed into the top 30.
"""

from urllib.parse import quote_plus
from datetime import timedelta

from ..fetch import get_json, Unavailable
from ..item import Item

KEY = "github"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def fetch(run_at):
    since = (run_at - timedelta(days=7)).strftime("%Y-%m-%d")
    url = (
        "https://api.github.com/search/repositories"
        f"?q={quote_plus(f'created:>{since}')}+{quote_plus('stars:>=50')}"
        "&sort=stars&order=desc&per_page=30"
    )

    body = get_json(url, headers=HEADERS)
    if not isinstance(body, dict) or "items" not in body:
        raise Unavailable("response body carried no `items` array")

    seen, items = [], []
    for repo in body["items"]:
        identity = repo.get("full_name")
        if not identity:
            continue
        seen.append(identity)

        description = (repo.get("description") or "").strip()
        topics = repo.get("topics") or []
        language = repo.get("language")
        stars = repo.get("stargazers_count") or 0

        meta_parts = [f"{stars:,} stars"]
        if language:
            meta_parts.append(language)
        meta_parts.append("new to the top 30")

        text = description
        if topics:
            text = (text + "\nTopics: " + ", ".join(topics)).strip()

        items.append(
            Item(
                source=KEY,
                identity=identity,
                title=identity,
                url=repo.get("html_url") or f"https://github.com/{identity}",
                text=text,
                meta=" · ".join(meta_parts),
            )
        )

    return items, seen
