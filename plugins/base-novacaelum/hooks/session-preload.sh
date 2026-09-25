#!/bin/bash
# session-preload.sh — SessionStart hook.
#
# Source: adapted from Nova Caelum's internal agentOS session-preload
# pattern (2026). License: MIT.
#
# If this project has been set up (user.md exists at the project root),
# inject it plus the 3 most recent worklog entries into context. Otherwise
# print one line pointing at /technical-cofounder:init.
#
# Plain stdout on SessionStart is added to Claude's context as plain text
# (code.claude.com/docs/en/hooks-guide) — no JSON needed here.
#
# Fails open: nothing in this script can break the session. Every fallible
# command is guarded so a read failure degrades to a visible stderr note,
# never a nonzero exit.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
USER_MD="$PROJECT_DIR/user.md"

# Consume stdin so nothing upstream blocks on an unread pipe; content is
# irrelevant to this hook (it reads $CLAUDE_PROJECT_DIR, not stdin).
cat >/dev/null 2>&1 || true

if [ ! -f "$USER_MD" ]; then
    echo "technical-cofounder: this project hasn't been set up yet — run /technical-cofounder:init to copy the starter workspace in."
    exit 0
fi

echo "═══ technical-cofounder session preload ═══"
echo
echo "## user.md"
echo
cat "$USER_MD" 2>/dev/null || echo "(could not read user.md)"
echo

ENTRIES_DIR="$PROJECT_DIR/worklog/entries"
echo "## Recent worklog — last 3"
echo
if [ -d "$ENTRIES_DIR" ]; then
    # Entries are named <timestamp>-<slug>.md, so a lexical sort is a
    # chronological sort.
    RECENT=""
    RECENT="$(find "$ENTRIES_DIR" -maxdepth 1 -type f -name '*.md' 2>/dev/null | sort | tail -3)" || RECENT=""
    if [ -n "$RECENT" ]; then
        while IFS= read -r entry; do
            [ -n "$entry" ] || continue
            echo "--- $(basename "$entry") ---"
            cat "$entry" 2>/dev/null || true
            echo
        done <<<"$RECENT"
    else
        echo "(no worklog entries yet)"
    fi
else
    echo "(no worklog entries yet)"
fi
echo "═══ end preload ═══"
exit 0
