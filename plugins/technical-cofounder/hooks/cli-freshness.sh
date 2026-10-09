#!/bin/bash
# cli-freshness.sh — SessionStart hook: once every 14 days, say when a tool the
# team relies on (Claude Code, uv, jq, gh, Git for Windows) is out of date.
#
# Source: Nova Caelum (2026). License: Apache-2.0.
#
# All of the work is bin/cli_freshness.py; this script only finds a Python that
# runs (lib/resolve-tools.sh, the resolver every hook here shares) and starts it.
# What it checks, when, and what it costs: the header of that file.
#
# When something is out of date it prints one line, which Claude Code adds to
# the session's context; the agent then tells the user and offers the update
# command, and runs it only on a yes. With nothing out of date, offline, or
# not yet due, it prints nothing.
#
# SessionStart hooks run in parallel, so this never adds to session-preload.sh's
# time; hooks.json also gives it a 10-second limit, the most it can ever hold
# a session up. Set TC_CLI_FRESHNESS=off in the environment to disable it.
#
# Fails open: no Python, no network, a broken check — it prints nothing and
# exits 0. (No Python is already reported by session-preload.sh's Health block.)

set -euo pipefail

if [ "${TC_CLI_FRESHNESS:-}" = "off" ]; then
    exit 0
fi

# Consume stdin so nothing upstream blocks on an unread pipe; this hook reads
# the environment, not the event.
cat >/dev/null 2>&1 || true

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || exit 0
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$HERE/..}"

# shellcheck source=lib/resolve-tools.sh disable=SC1091
source "$HERE/lib/resolve-tools.sh" 2>/dev/null || exit 0
NC_PYTHON="$(CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}" nc_resolve_python)" || NC_PYTHON=""
[ -n "$NC_PYTHON" ] || exit 0

"$NC_PYTHON" "$PLUGIN_ROOT/bin/cli_freshness.py" || true
exit 0
