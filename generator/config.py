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
USER_AGENT = "ai-brief/1.0 (+https://mvandewettering.com/ai-brief/)"

# Every Source gets the same transport budget. #4's Unavailable rule turns a
# timeout into a hole on the page rather than a crash.
HTTP_TIMEOUT = 20.0

# --- Enrichment (#5) -------------------------------------------------------

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "gemma4:e4b"
# A dead Ollama HANGS under WSL2 rather than refusing, so the pre-flight is
# mandatory and its timeout is short. Without it a 300-Item Run blocks for
# hours. See #5.
OLLAMA_PREFLIGHT_TIMEOUT = 3.0
OLLAMA_ITEM_TIMEOUT = 30.0

# --- Selection (#7) --------------------------------------------------------

CUTOFF = 3          # Score >= 3 appears in the Edition. Never relaxed.
CEILING = 8         # Hard cap of Items per Source.
FLOOR = 3           # A cap that yields: trim protection, never a quota.
EDITION_MAX = 25    # Map note 6's 15-25. Trimming starts above this.

# --- Pre-ranking before Enrichment (#4, #7) --------------------------------

HN_POINTS_FLOOR = 75    # noise gate; the Score does the choosing
HN_ENRICH_LIMIT = 20    # what the Rubric was calibrated against
DEVTO_ENRICH_LIMIT = 15  # ditto

# --- The seven Sources, in the order they appear in an Edition -------------
#
# key            -> the Snapshot filename and the HTML id stem
# label          -> the <h2> text, and the name used in "title as X gave it"
SOURCE_ORDER = [
    "arxiv",
    "hackernews",
    "github",
    "devto",
    "hf-models",
    "hf-datasets",
    "hf-papers",
]

SOURCE_LABELS = {
    "arxiv": "arXiv",
    "hackernews": "Hacker News",
    "github": "GitHub New Repos",
    "devto": "dev.to",
    "hf-models": "Hugging Face models",
    "hf-datasets": "Hugging Face datasets",
    "hf-papers": "Hugging Face papers",
}

# Snapshots are kept for a rolling 30-day window (map note 5).
SNAPSHOT_WINDOW_DAYS = 30
