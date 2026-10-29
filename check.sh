#!/usr/bin/env bash
#
# The repo's one check: lint the shell, compile the generator, confirm the
# Sources are registered consistently, and Generate a throwaway Edition with
# every model endpoint dead, so it costs nothing and touches neither docs/ nor
# state/. Run by githooks/pre-commit; safe to run by hand at any time.
#
# Offline it still passes: a Source that cannot be fetched is reported as
# Unavailable, which is a describable Edition rather than a failed Run.

set -eu -o pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${AI_BRIEF_PYTHON:-$REPO/.venv/bin/python}"
cd "$REPO"

step() { echo "check.sh: $*"; }

step "shellcheck"
SHELLCHECK="$(command -v shellcheck || echo "$REPO/.venv/bin/shellcheck")"
"$SHELLCHECK" publish.sh check.sh githooks/pre-commit \
    systemd/ai-brief-failed systemd/install.sh

step "compile"
"$PY" -m compileall -q generator

step "Sources consistent"
"$PY" - <<'PY'
from generator import config, sources
assert set(config.SOURCE_ORDER) == set(config.SOURCE_LABELS) \
    == set(sources.FETCHERS), "SOURCE_ORDER, SOURCE_LABELS, FETCHERS differ"
PY

step "smoke Generate, models unreachable"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/docs" "$TMP/state"
cp docs/index.html docs/style.css "$TMP/docs/"
env -u OPENROUTER_API_KEY "$PY" -m generator.run \
    --docs-dir "$TMP/docs" --state-dir "$TMP/state" --only the-decoder \
    --decisions-base http://127.0.0.1:9/ \
    --openrouter-base http://127.0.0.1:9/ \
    --date 2000-01-01 >"$TMP/run.log" 2>&1 \
    || { cat "$TMP/run.log"; exit 1; }
[ -s "$TMP/docs/2000-01-01.html" ] \
    || { cat "$TMP/run.log"; echo "check.sh: no Edition written" >&2; exit 1; }

step "ok"
