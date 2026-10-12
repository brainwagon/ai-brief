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
#     2   the Run succeeded but Publish failed; the Edition is on disk but was
#         not published, and the next Run will pick it up
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

# --- Retrying the network steps --------------------------------------------
#
# The two steps that talk to GitHub sit at the very end of a Run which, until
# them, has touched only the local disk. When one fails for a reason that has
# nothing to do with the Run — the server-side blip seen as `remote: fatal
# error in commit_refs`, or an ordinary flaky connection — failing the whole
# morning over it is the wrong response. Both steps are safe to repeat:
# `pull --rebase` on an already-integrated tree does nothing, and a push that
# partly landed just offers the same objects again. Backoff is geometric
# because such a failure is expected to be brief; five tries span about three
# minutes, well inside the unit's 30-minute wall.
retry() {
    local -i attempt=1 max=5 delay=5
    until "$@"; do
        if (( attempt >= max )); then
            echo "publish.sh: '$*' failed after ${attempt} attempts" >&2
            return 1
        fi
        echo "publish.sh: '$*' failed (attempt ${attempt}/${max}); retrying in ${delay}s" >&2
        sleep "$delay"
        (( attempt++ ))
        (( delay *= 3 ))
    done
}

# --- Generate --------------------------------------------------------------
# Everything the generator writes lands in docs/ and state/. It never runs git.
if ! "$PYTHON" -m generator.run; then
    echo "publish.sh: the Run failed; nothing committed" >&2
    exit 1
fi

# --- Publish ---------------------------------------------------------------
#
# The ordinary Run writes a new Edition, so there is usually something to
# commit. But "did this Run write anything" is the wrong test for whether to
# publish. A previous Run whose push failed leaves a commit behind, and a
# later Run that writes nothing new — the generator stops early on a date that
# already exists — would take a "nothing changed" exit and strand that commit
# forever. So committing is conditional and pushing is not: the commit happens
# only when the Run wrote something, but the push happens whenever HEAD is
# ahead of origin, whoever committed it.
if [ -n "$(git status --porcelain -- docs state)" ]; then
    git add -- docs state || exit 2

    # Name the commit after the Edition that was actually written, not after
    # the clock — a Run given an explicit date must not commit under today's.
    EDITION="$(git diff --cached --name-only -- docs \
               | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | sort -u | tail -1)"
    EDITION="${EDITION:-$(date -u +%Y-%m-%d)}"

    # An Edition is published once and revised only to repair a failed Run
    # (CONTEXT.md), and the commit says which it is. If the date was already
    # committed, this is a revision of it, and the subject says so rather than
    # reusing the bare `Edition <date>`. The generator reports *why* it revised
    # on stdout; the subject only carries the fact.
    SUBJECT="Edition ${EDITION}"
    if git cat-file -e "HEAD:docs/${EDITION}.html" 2>/dev/null; then
        SUBJECT="Edition ${EDITION} (revised)"
    fi

    git -c user.name="ai-brief" \
        -c user.email="ai-brief@mvandewettering.com" \
        commit -q -m "$SUBJECT" || exit 2
else
    EDITION=""
fi

# Nothing written and nothing stranded: the ordinary quiet outcome.
if [ "$(git rev-list --count origin/main..HEAD)" -eq 0 ]; then
    echo "publish.sh: nothing changed; already current"
    exit 0
fi

# Pull first: the repo is edited by hand as well as by the timer, so a push
# that has not rebased is the ordinary failure, not an exceptional one.
#
# --autostash for the same reason. A rebase refuses to start on a dirty tree,
# and the dirt is normally work in progress somewhere outside docs/ and state/
# — which has nothing to do with the Edition just committed. Without it, an
# uncommitted edit anywhere in the repo silently stops Publish every morning
# while Generate keeps succeeding, and the Editions pile up unpushed.
retry git pull --rebase --autostash --quiet origin main || exit 2
retry git push --quiet origin HEAD:main || exit 2

if [ -n "$EDITION" ]; then
    echo "publish.sh: Edition ${EDITION} published"
else
    echo "publish.sh: pushed a previously stranded commit; now current"
fi
exit 0
