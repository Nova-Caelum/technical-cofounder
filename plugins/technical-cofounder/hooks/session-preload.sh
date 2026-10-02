#!/bin/bash
# session-preload.sh — SessionStart hook.
#
# Source: adapted from Nova Caelum's internal agentOS session-preload
# pattern (2026). License: MIT.
#
# If this project has been set up (core_text/user.md, or a legacy user.md at
# the project root), inject it plus the 3 most recent worklog entries into
# context. Otherwise print one line pointing at /technical-cofounder:quick-start.
# Either way, print the live tech primer: which Nova Caelum plugins are
# present, expected but missing, or not chosen; a pointer to the
# without-super fallbacks when super isn't present; and setup progress while
# steps are pending. The static "what runs where" lives in the project's
# CLAUDE.md, which Claude Code loads on its own.
#
# The primer reads JSON (settings enabledPlugins, core_text/setup.json) with
# python3, the plugin's own prerequisite. It prints only the three fixed
# plugin names and states, never a settings value, and never writes a file.
#
# With Hyperspace Engine present (.hyperspace/graph.db), bin/he_bridge.py
# takes over the worklog block: in a set-up project it runs the one-time
# handshake (write worklog_owner, and worklog_mirror_dir for an Obsidian
# view, after importing worklog/entries once), then prints the block from
# Hyperspace's store when TC owns the preload, or nothing when Hyperspace's
# own hook does. Without .hyperspace/graph.db this script is unchanged.
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
ASK_LINE="Stuck, found a bug, or have an idea? /technical-cofounder:contact reaches Nova Caelum."

USER_MD="$PROJECT_DIR/core_text/user.md"
LEGACY=0
if [ ! -f "$USER_MD" ] && [ -f "$PROJECT_DIR/user.md" ]; then
    USER_MD="$PROJECT_DIR/user.md"
    LEGACY=1
fi

# Consume stdin so nothing upstream blocks on an unread pipe; content is
# irrelevant to this hook (it reads $CLAUDE_PROJECT_DIR, not stdin).
cat >/dev/null 2>&1 || true

tech_primer() {
    echo "## Tech primer (live)"
    echo
    python3 - "$PROJECT_DIR" "${HOME:-}" "$PLUGIN_ROOT" <<'PY' 2>/dev/null || echo "(plugin stack unavailable: python3 could not run)"
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # Windows pipes default to the ANSI code page
project, home, plugin = (Path(a) for a in sys.argv[1:4])
sys.path.insert(0, str(plugin / "bin"))
try:
    import he_bridge
    he_mode = he_bridge.mode(project)
except Exception:
    he_mode = "tc"


def load(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


# Most specific scope first; the first scope that mentions a plugin decides.
scopes = [load(project / ".claude" / "settings.local.json"), load(project / ".claude" / "settings.json"),
          load(home / ".claude" / "settings.json") if str(home) not in ("", ".") else {}]


def enabled(name):
    for scope in scopes:
        plugins = scope.get("enabledPlugins")
        if isinstance(plugins, dict):
            values = [v for k, v in plugins.items() if isinstance(k, str) and k.split("@", 1)[0] == name]
            if values:
                return any(v is True for v in values)
    return False


def state(present, expected):
    return "present" if present else "expected but missing" if expected else "not chosen"


record = load(project / "core_text" / "setup.json")
choices = record.get("choices") if isinstance(record.get("choices"), dict) else {}
super_present = enabled("super-novacaelum")
print("- technical-cofounder: present")
print(f"- super-novacaelum: {state(super_present, choices.get('super') == 'yes')}")
he_state = state(enabled("hyperspace-engine") or (project / ".hyperspace" / "config.toml").is_file(), False)
he_owned = " · worklog: hyperspace (owned by TC preload)" if he_mode == "tc-preload" else ""
print(f"- hyperspace-engine: {he_state}{he_owned}")
if not super_present:
    print(f"Without super: {plugin / 'reference' / 'without-super.md'} lists what to use instead of each super service.")

if record:
    steps = record.get("steps") if isinstance(record.get("steps"), dict) else {}
    ids = [s.get("id") for s in load(plugin / "setup" / "steps.json").get("steps", []) if isinstance(s, dict) and s.get("part", 1) == 1] or list(steps)
    status = [(steps.get(i) if isinstance(steps.get(i), dict) else {}).get("status", "pending") for i in ids]
    if "pending" in status:
        print(f'Setup: {status.count("done")} of {len(ids)} steps done — say "continue setup" to pick up where you left off.')
PY
}

if [ ! -f "$USER_MD" ]; then
    echo "technical-cofounder: this project hasn't been set up yet — run /technical-cofounder:quick-start to copy the starter workspace in."
    echo
    tech_primer
    echo
    echo "$ASK_LINE"
    exit 0
fi

echo "═══ technical-cofounder session preload ═══"
echo
echo "## user.md"
echo
cat "$USER_MD" 2>/dev/null || echo "(could not read user.md)"
if [ "$LEGACY" = 1 ]; then
    echo "Note: this profile is at the old location (./user.md); /technical-cofounder:quick-start can move it into core_text/ for you."
fi
echo

ENTRIES_DIR="$PROJECT_DIR/worklog/entries"
if [ -f "$PROJECT_DIR/.hyperspace/graph.db" ]; then
    python3 "$PLUGIN_ROOT/bin/he_bridge.py" preload "$PROJECT_DIR" 2>/dev/null \
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
tech_primer
echo
echo "$ASK_LINE"
echo "═══ end preload ═══"
exit 0
