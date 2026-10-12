#!/bin/bash
# session-preload.sh — SessionStart hook.
#
# Source: adapted from Nova Caelum's internal agentOS session-preload
# pattern (2026). License: MIT.
#
# If this project has been set up (core_text/user.md, or a legacy user.md at
# the project root), inject it plus the 3 most recent worklog entries into
# context. Otherwise print one line pointing at /technical-cofounder-setup:start.
# Either way, print the live tech primer: which Nova Caelum plugins are
# present, expected but missing, or not chosen; whether Hyperspace Engine's
# verifier judge is on or off, and how to switch it; a pointer to the
# without-super fallbacks when super isn't present; a line saying no run is
# open yet and that work starts at Understand, when Hyperspace Engine has no
# open run (its own briefing prints a block for each one it has); setup
# progress while steps are pending; and each skipped setup step with what
# skipping costs.
# The static "what runs where" lives in the project's CLAUDE.md, which Claude
# Code loads on its own.
#
# Before any of that, a "## Health" block names what is broken, one plain line
# per fault, each with its fix. It is checked live, in this order, and a
# project with no fault prints no block at all:
#   1. the project has no Hyperspace environment, or its interpreter does not run
#   2. it has one, but setup did not build it on this computer (or built it
#      before setup kept a record), so nothing in it is started
#   3. it runs, but the team's server (mcp/server.py, started the way .mcp.json
#      starts it) does not answer an initialize request in 5 seconds
#   4. no jq runs, so the guardrail hooks are switched off
#   5. no Python runs, so the primer below cannot be read
# bin/health_probe.py does 1 to 3, and asks bin/launch_env.py before it starts
# anything from the project. The block reports and nothing else: it repairs
# nothing and writes no file. Whether a restart is pending is not reported: a
# new session is the restart.
#
# The primer is bin/tech_primer.py. Every Python here is the one
# lib/resolve-tools.sh finds on this computer, never the project's own: a
# folder that came from somewhere else can ship a file at
# .hyperspace/env/bin/python.
#
# With Hyperspace Engine present (.hyperspace/graph.db), bin/he_bridge.py
# takes over the worklog block: in a set-up project it runs the one-time
# handshake (write worklog_owner and worklog_mirror_dir, after importing
# worklog/entries once; a project that has the owner but not the mirror gets
# the mirror key and one rebuild), then prints the block from
# Hyperspace's store when TC owns the preload, or nothing when Hyperspace's
# own hook does. Without .hyperspace/graph.db this script is unchanged.
#
# In a set-up project, bin/drive_map_pointer.py then rebuilds the project's drive
# map (core_text/drive-map.md, with Hyperspace Engine's drive_map.py in its `tree`
# mode) and the briefing carries one line pointing at it, never the map itself.
# With no engine, no project environment, one setup has no record of, or an
# engine from before `tree`, it prints nothing and logs one line to stderr.
# Both scripts start the project's environment only when bin/launch_env.py says
# setup built it on this computer.
#
# Plain stdout on SessionStart is added to Claude's context as plain text
# (code.claude.com/docs/en/hooks-guide) — no JSON needed here.
#
# Fails open: nothing in this script can break the session. Every fallible
# command is guarded so a read failure degrades to a visible note, never a
# nonzero exit.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"
[ -n "$PLUGIN_ROOT" ] || PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)" || PLUGIN_ROOT=""
# This computer's own Python, never the project's.
NC_PYTHON=""
# shellcheck source=lib/resolve-tools.sh disable=SC1091
if source "$(dirname "${BASH_SOURCE[0]}")/lib/resolve-tools.sh" 2>/dev/null; then
    NC_PYTHON="$(nc_resolve_system_python)" || NC_PYTHON=""
else
    NC_JQ=""
fi
ASK_LINE="Stuck, found a bug, or have an idea? /technical-cofounder:contact reaches Nova Caelum."
FIX="Fix: run /technical-cofounder-setup:start"
ENGINE_FAULT="Hyperspace Engine isn't set up in this project yet, so the task graph and the worklog tools are off. $FIX (or say \"set up hyperspace\")."
UNKNOWN_FAULT="This folder's Hyperspace environment was not built by setup on this computer, or was built before setup kept a record of it, so the worklog server and the engine were not started. $FIX and choose repair to rebuild it."
SERVER_FAULT="The team's worklog server could not start, so worklog tools are off. $FIX."
JQ_FAULT="jq isn't installed, so the retry breaker and the word-budget checks are off. $FIX."
PYTHON_FAULT="No Python was found, so the plugin overview could not be read. $FIX."

USER_MD="$PROJECT_DIR/core_text/user.md"
LEGACY=0
if [ ! -f "$USER_MD" ] && [ -f "$PROJECT_DIR/user.md" ]; then
    USER_MD="$PROJECT_DIR/user.md"
    LEGACY=1
fi

# Consume stdin so nothing upstream blocks on an unread pipe; content is
# irrelevant to this hook (it reads $CLAUDE_PROJECT_DIR, not stdin).
cat >/dev/null 2>&1 || true

# Prints one word: engine, unknown, server or ok (see bin/health_probe.py).
health_probe() {
    "$NC_PYTHON" "$PLUGIN_ROOT/bin/health_probe.py" "$PROJECT_DIR" "$PLUGIN_ROOT"
}

health_block() {
    local state="engine" faults=""
    if [ -n "$NC_PYTHON" ]; then
        # A probe that could not run decides nothing: no line, never a guess.
        state="$(health_probe 2>/dev/null)" || state=""
    fi
    case "$state" in
        engine) faults+="$ENGINE_FAULT"$'\n' ;;
        unknown) faults+="$UNKNOWN_FAULT"$'\n' ;;
        server) faults+="$SERVER_FAULT"$'\n' ;;
    esac
    [ -n "$NC_JQ" ] || faults+="$JQ_FAULT"$'\n'
    [ -n "$NC_PYTHON" ] || faults+="$PYTHON_FAULT"$'\n'
    [ -n "$faults" ] || return 0
    printf '## Health\n\n%s\n' "$faults"
}

tech_primer() {
    # With no Python the Health block has already said so, in one line.
    [ -n "$NC_PYTHON" ] || return 0
    echo "## Tech primer (live)"
    echo
    "$NC_PYTHON" "$PLUGIN_ROOT/bin/tech_primer.py" "$PROJECT_DIR" "${HOME:-}" "$PLUGIN_ROOT" 2>/dev/null \
        || echo "(plugin stack unavailable: python3 could not run)"
}

if [ ! -f "$USER_MD" ]; then
    echo "technical-cofounder: this project hasn't been set up yet — run /technical-cofounder-setup:start to copy the starter workspace in."
    echo
    health_block
    tech_primer
    echo
    echo "$ASK_LINE"
    exit 0
fi

echo "═══ technical-cofounder session preload ═══"
echo
health_block
echo "## user.md"
echo
cat "$USER_MD" 2>/dev/null || echo "(could not read user.md)"
if [ "$LEGACY" = 1 ]; then
    echo "Note: this profile is at the old location (./user.md); /technical-cofounder-setup:start can move it into core_text/ for you."
fi
echo

ENTRIES_DIR="$PROJECT_DIR/worklog/entries"
if [ -f "$PROJECT_DIR/.hyperspace/graph.db" ]; then
    "$NC_PYTHON" "$PLUGIN_ROOT/bin/he_bridge.py" preload "$PROJECT_DIR" 2>/dev/null \
        || echo "(worklog unavailable: python3 could not run the Hyperspace bridge)"
else
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
fi
echo
# The project's drive map: written fresh, then one pointer line (or a log line on stderr).
[ -z "$NC_PYTHON" ] || "$NC_PYTHON" "$PLUGIN_ROOT/bin/drive_map_pointer.py" preload "$PROJECT_DIR" || true
tech_primer
echo
echo "$ASK_LINE"
echo "═══ end preload ═══"
exit 0
