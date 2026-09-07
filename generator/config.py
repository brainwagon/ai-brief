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
# The model is a cheap hosted one on OpenRouter, reached with an OpenAI-shaped
# chat/completions call. It replaced a local Ollama, which stopped a Run dead
# whenever the daemon was not up on this machine.

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_KEY_ENV = "OPENROUTER_API_KEY"

# Paid, and deliberately so. The free tiers were tried and are not worth what
# they cost in wall clock: measured 2026-09-06 against this Prompt, 24 calls at
# four in flight, the best free model available anywhere answered 19 of 24 with
# a median of 23s, where deepseek-v4-flash answered 24 of 24 with a median of
# 2.3s. A whole Run of ~200 Items bills about three cents, which is under a
# dollar a month, and buys a Run that finishes in minutes rather than one that
# runs into the unit's 30-minute wall.
#
# All three honour a strict json_schema response format — which is what keeps a
# Score in range without a validator — AND accept the `reasoning` field below.
# That second requirement is the one that is easy to miss: a growing number of
# endpoints answer HTTP 400 "Reasoning is mandatory for this endpoint and
# cannot be disabled", which model.py correctly treats as fatal — so such a
# model in this list would not degrade a Run, it would end Enrichment outright.
# gemini-3.5-flash-lite, glm-5.3-flash and minimax-m2.5 were all rejected on
# exactly that, having passed every other test.
#
# The first is the cheapest and the fastest. The second is the same model under
# a dated pin, so a floating alias that moves under us is survivable. The third
# is a different vendor entirely, because two DeepSeek entries share an outage.
# OpenRouter walks the list itself.
#
#   deepseek/deepseek-v4-flash       24/24, p50 2.3s, ~$0.030 a Run
#   deepseek/deepseek-v4-flash-0731  24/24, p50 3.5s, ~$0.033 a Run
#   openai/gpt-5.4-nano               4/4, mean 1.3s, ~$0.068 a Run
OPENROUTER_MODEL = "deepseek/deepseek-v4-flash"
OPENROUTER_FALLBACK_MODELS = [
    "deepseek/deepseek-v4-flash-0731",
    "openai/gpt-5.4-nano",
]

OPENROUTER_PREFLIGHT_TIMEOUT = 10.0
OPENROUTER_CONNECT_TIMEOUT = 10.0
# A call that is going to answer answers in 2-4s; the slowest of 48 measured
# took 6.1s. What a hosted model also does, occasionally, is accept the request
# and then sit on it for minutes. So the timeout is many times a normal call
# and nowhere near the patience the provider would like: abandoning a stalled
# draw and taking another is far faster than waiting one out, and this is the
# single number that decides how long a Run takes. It was 45s when the model
# was a free one that genuinely needed 13s to think.
OPENROUTER_ITEM_TIMEOUT = 30.0
# The Pick pass is ONE call carrying a dozen Items, so it is both slower to
# generate and worth waiting for: an Item that stalls costs one Synopsis out of
# hundreds, and the Pick pass stalling costs the whole day's Picks. Impatience
# there is what left an Edition with no Picks during #12's testing.
OPENROUTER_PICK_TIMEOUT = 180.0
OPENROUTER_ATTEMPTS = 3     # per call, transient faults only
OPENROUTER_BACKOFF = 3.0    # seconds, multiplied by the attempt number

# Unlike the old local model, this call is latency-bound rather than
# compute-bound, so requests in flight together are what turns a 300-Item Run
# from an hour into minutes. Four was the right number for a free model, which
# queues rather than refusing: past about four in flight the extra requests
# only sat in the provider's queue until the deadline above cancelled them,
# which read as throughput and was really just churn. A paid endpoint does not
# queue that way — 24 calls took 14.9s at four in flight and 9.7s at eight,
# with no failures either way — so the ceiling moved with the model.
OPENROUTER_CONCURRENCY = 8

# --- Selection (#7) --------------------------------------------------------

CUTOFF = 3          # Score >= 3 appears in the Edition. Never relaxed.
CEILING = 8         # Hard cap of Items per Source.
FLOOR = 3           # A cap that yields: trim protection, never a quota.
EDITION_MAX = 25    # Map note 6's 15-25. Trimming starts above this.

# --- Pre-ranking before Enrichment (#4, #7) --------------------------------

HN_POINTS_FLOOR = 75    # noise gate; the Score does the choosing
HN_ENRICH_LIMIT = 20    # what the Rubric was calibrated against
DEVTO_ENRICH_LIMIT = 15  # ditto

# --- The nine Sources, in the order they appear in an Edition --------------
#
# key            -> the Snapshot filename and the HTML id stem
# label          -> the <h2> text, and the name used in "title as X gave it"
SOURCE_ORDER = [
    "arxiv",
    "hackernews",
    "github",
    "devto",
    "reddit",
    "wired",
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
    "wired": "WIRED",
    "hf-models": "Hugging Face models",
    "hf-datasets": "Hugging Face datasets",
    "hf-papers": "Hugging Face papers",
}

# Snapshots are kept for a rolling 30-day window (map note 5).
SNAPSHOT_WINDOW_DAYS = 30
