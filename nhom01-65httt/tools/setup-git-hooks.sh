#!/bin/sh
# Cài git hook của nhóm cho bản clone hiện tại. Chạy một lần sau khi clone:
#   sh nhom01-65httt/tools/setup-git-hooks.sh
# (Trên Windows chạy trong Git Bash.)

set -e
TEAM_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(git -C "$TEAM_DIR" rev-parse --show-toplevel)"
REL="$(basename "$TEAM_DIR")/tools/hooks"

chmod +x "$ROOT/$REL/"* 2>/dev/null || true
git -C "$ROOT" config core.hooksPath "$REL"
git -C "$ROOT" update-index --chmod=+x "$REL/commit-msg" 2>/dev/null || true

echo "Da bat hook: core.hooksPath = $REL"
echo "Commit sai quy chuan (cu phap hoac co-author cua agent) se bi tu choi."
