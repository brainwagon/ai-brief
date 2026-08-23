#!/usr/bin/env bash
#
# Publish: commit and push what a Run wrote.
#
# WHY THIS IS A SEPARATE FILE. The generator writes files and never touches
# git (map note 11). Keeping the commit and the push out here is what makes a
# git failure — no network, a rejected push, a dirty tree — distinguishable
# from a failure to Generate. CONTEXT.md names the two acts separately for the
# same reason: Generate touches files, Publish makes them public.
#
# WHY IT IS THE THING A TIMER POINTS AT. A systemd user service (#9) runs this
# one command; it needs no working directory, no venv on PATH, and no
# arguments. Its exit status is the whole contract:
#
#     0   an Edition was Generated, and either Published or already current
#     1   the Run failed; nothing was committed and nothing was pushed
#     2   the Run succeeded but Publish failed; the Edition is on disk,
#         uncommitted, and the next Run will pick it up
#
# The two failures are deliberately different numbers so an OnFailure= unit can
# say which half broke.

set -u -o pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The venv, unless something is deliberately pointing elsewhere — a git
# worktree used for development has no .venv of its own.
PYTHON="${AI_BRIEF_PYTHON:-$REPO/.venv/bin/python}"

cd "$REPO" || exit 2

# Enrichment needs an OpenRouter key, and neither a systemd unit nor a cron
# line sources ~/.bashrc. This file is the one place the key is read from for
# an unattended Run; without it the Run still succeeds and every Item is
# Unenriched, which is why the source is conditional rather than fatal.
ENV_FILE="${AI_BRIEF_ENV:-$HOME/.config/ai-brief/env}"
if [ -z "${OPENROUTER_API_KEY:-}" ] && [ -r "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

if [ ! -x "$PYTHON" ]; then
    echo "publish.sh: no interpreter at $PYTHON; create the venv first" >&2
    exit 1
fi

# --- Generate --------------------------------------------------------------
# Everything the generator writes lands in docs/ and state/. It never runs git.
if ! "$PYTHON" -m generator.run; then
    echo "publish.sh: the Run failed; nothing committed" >&2
    exit 1
fi

# --- Publish ---------------------------------------------------------------
if [ -z "$(git status --porcelain -- docs state)" ]; then
    echo "publish.sh: nothing changed; already current"
    exit 0
fi

git add -- docs state || exit 2

# Name the commit after the Edition that was actually written, not after the
# clock — a Run given an explicit date must not commit under today's.
EDITION="$(git diff --cached --name-only -- docs \
           | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | sort -u | tail -1)"
EDITION="${EDITION:-$(date -u +%Y-%m-%d)}"

git -c user.name="ai-brief" \
    -c user.email="ai-brief@mvandewettering.com" \
    commit -q -m "Edition ${EDITION}" || exit 2

# Pull first: the repo is edited by hand as well as by the timer, so a push
# that has not rebased is the ordinary failure, not an exceptional one.
git pull --rebase --quiet origin main || exit 2
git push --quiet origin HEAD:main || exit 2

echo "publish.sh: Edition ${EDITION} published"
exit 0
