#!/usr/bin/env bash
#
# Install the daily Run's units so a rebuilt machine can get them back.
#
# WHY SYMLINKS AND NOT COPIES. The repo is the system (map, "Destination"), and
# a copied unit file drifts the first time someone edits the installed one to
# try something - silently, and invisibly until the day it matters. A symlink
# makes `systemctl --user cat ai-brief.timer` show the versioned file, so the
# unit that runs and the unit that is reviewed cannot disagree. The cost is
# that ~/.config/systemd/user now depends on this repo staying where it is,
# which it must anyway: ExecStart= names a path inside it.

set -eu

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

mkdir -p "$DEST"
for unit in ai-brief.timer ai-brief.service ai-brief-failed.service; do
    ln -sfn "$REPO/systemd/$unit" "$DEST/$unit"
    echo "linked $DEST/$unit -> $REPO/systemd/$unit"
done

chmod +x "$REPO/systemd/ai-brief-failed" "$REPO/publish.sh"

systemctl --user daemon-reload
systemctl --user enable --now ai-brief.timer
systemctl --user list-timers ai-brief.timer --all
