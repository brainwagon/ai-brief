"""Fixed settings for a Run.

Everything here is a number or an endpoint that a ticket pinned. Tunable
*text* — the Rubric, the Prompt — is never here; it lives in editable files at
the repo root (map standing preference).
"""

from pathlib import Path

# The repo root, found relative to this file so a Run works from any cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent

DOCS_DIR = REPO_ROOT / "docs"
STATE_DIR = REPO_ROOT / "state"

RUBRIC_FILE = REPO_ROOT / "rubric.md"
PROMPT_FILE = REPO_ROOT / "prompt.md"
PICK_PROMPT_FILE = REPO_ROOT / "pick-prompt.md"

# One string for the whole generator, so the Brief identifies itself honestly.
# arXiv rejects a request without one and GitHub's API requires one; sending it
# everywhere costs nothing. Pinned on #4.
SITE_URL = "https://mvandewettering.com/ai-brief/"
USER_AGENT = f"ai-brief/1.0 (+{SITE_URL})"

# Every Source gets the same transport budget. #4's Unavailable rule turns a
# timeout into a hole on the page rather than a crash.
HTTP_TIMEOUT = 20.0

# --- Enrichment (#5) -------------------------------------------------------
#
# The model is a free one hosted on OpenRouter, reached with an OpenAI-shaped
# chat/completions call. It replaced a local Ollama, which stopped a Run dead
# whenever the daemon was not up on this machine.

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_KEY_ENV = "OPENROUTER_API_KEY"

# Free models only, and all three honour a strict json_schema response format —
# which is what keeps a Score in range without a validator. The first is the
# fastest measured on this task; the others exist because a free model is
# rate-limited upstream without warning, and OpenRouter walks the list itself.
OPENROUTER_MODEL = "nvidia/nemotron-nano-9b-v2:free"
OPENROUTER_FALLBACK_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "z-ai/glm-5.2:free",
]

OPENROUTER_PREFLIGHT_TIMEOUT = 10.0
OPENROUTER_CONNECT_TIMEOUT = 10.0
# A call that is going to answer answers in 7-13s. What a free model also does,
# several times in a Run, is accept the request and then sit on it for minutes.
# So the timeout is a few times a normal call and nowhere near the patience the
# provider would like: abandoning a stalled draw and taking another is far
# faster than waiting one out, and this is the single number that decides how
# long a Run takes.
OPENROUTER_ITEM_TIMEOUT = 45.0
# The Pick pass is ONE call carrying a dozen Items, so it is both slower to
# generate and worth waiting for: an Item that stalls costs one Synopsis out of
# hundreds, and the Pick pass stalling costs the whole day's Picks. Impatience
# there is what left an Edition with no Picks during #12's testing.
OPENROUTER_PICK_TIMEOUT = 180.0
OPENROUTER_ATTEMPTS = 3     # per call, transient faults only
OPENROUTER_BACKOFF = 3.0    # seconds, multiplied by the attempt number

# Unlike the old local model, this call is latency-bound rather than
# compute-bound, so requests in flight together are what turns a 300-Item Run
# from an hour into minutes. Not as high as it could be, though: a free model
# queues rather than refusing, and past about four in flight the extra requests
# only sit in the provider's queue until the deadline above cancels them, which
# reads as throughput and is really just churn.
OPENROUTER_CONCURRENCY = 4

# --- Selection (#7) --------------------------------------------------------

CUTOFF = 3          # Score >= 3 appears in the Edition. Never relaxed.
CEILING = 8         # Hard cap of Items per Source.
FLOOR = 3           # A cap that yields: trim protection, never a quota.
EDITION_MAX = 25    # Map note 6's 15-25. Trimming starts above this.

# --- Pre-ranking before Enrichment (#4, #7) --------------------------------

HN_POINTS_FLOOR = 75    # noise gate; the Score does the choosing
HN_ENRICH_LIMIT = 20    # what the Rubric was calibrated against
DEVTO_ENRICH_LIMIT = 15  # ditto

# --- The eight Sources, in the order they appear in an Edition -------------
#
# key            -> the Snapshot filename and the HTML id stem
# label          -> the <h2> text, and the name used in "title as X gave it"
SOURCE_ORDER = [
    "arxiv",
    "hackernews",
    "github",
    "devto",
    "reddit",
    "hf-models",
    "hf-datasets",
    "hf-papers",
]

SOURCE_LABELS = {
    "arxiv": "arXiv",
    "hackernews": "Hacker News",
    "github": "GitHub New Repos",
    "devto": "dev.to",
    "reddit": "r/LocalLLaMA",
    "hf-models": "Hugging Face models",
    "hf-datasets": "Hugging Face datasets",
    "hf-papers": "Hugging Face papers",
}

# Snapshots are kept for a rolling 30-day window (map note 5).
SNAPSHOT_WINDOW_DAYS = 30
