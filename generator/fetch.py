"""The one place a Run talks to the outside world.

Every request carries the Brief's User-Agent and a timeout. `Unavailable` is
raised for anything that is not a useful answer — a connection error, a
timeout, a non-2xx status, or a body that does not parse into the expected
shape (#4). Nothing here retries around a rate limit.
"""

import time
import requests

from . import config


class Unavailable(Exception):
    """A Source did not answer usefully. Carries the reason shown on the page."""


# arXiv is fetched as its API Terms of Use invites: one request every three
# seconds, one connection at a time. This is the decision recorded on #10 —
# export.arxiv.org/robots.txt is a blanket `Disallow: /` while the API docs
# point clients at that exact host, and the specific invitation to API clients
# is read as governing. The sleep lives here rather than at the call site so a
# future second arXiv request cannot violate it by forgetting.
_ARXIV_MIN_INTERVAL = 3.0
_last_arxiv_request = 0.0


def get(url, headers=None, timeout=None, polite_host=None):
    """Issue one GET. Raise Unavailable with a readable reason on any fault."""
    global _last_arxiv_request

    if polite_host == "arxiv":
        wait = _ARXIV_MIN_INTERVAL - (time.time() - _last_arxiv_request)
        if wait > 0:
            time.sleep(wait)

    all_headers = {"User-Agent": config.USER_AGENT}
    if headers:
        all_headers.update(headers)

    try:
        response = requests.get(
            url, headers=all_headers, timeout=timeout or config.HTTP_TIMEOUT
        )
    except requests.exceptions.Timeout:
        raise Unavailable(f"timed out after {timeout or config.HTTP_TIMEOUT:.0f}s")
    except requests.exceptions.RequestException as exc:
        raise Unavailable(f"{type(exc).__name__}: {_short(exc)}")
    finally:
        if polite_host == "arxiv":
            _last_arxiv_request = time.time()

    if response.status_code != 200:
        host = requests.utils.urlparse(url).netloc
        raise Unavailable(f"HTTP {response.status_code} from {host}")

    return response


def get_json(url, headers=None, timeout=None):
    """GET and parse JSON, turning a body that is not JSON into Unavailable."""
    response = get(url, headers=headers, timeout=timeout)
    try:
        return response.json()
    except ValueError:
        raise Unavailable("response body did not parse as JSON")


def _short(exc, limit=90):
    text = " ".join(str(exc).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
