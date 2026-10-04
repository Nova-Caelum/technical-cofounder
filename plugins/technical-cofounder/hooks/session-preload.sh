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
# present, expected but missing, or not chosen; a pointer to the
# without-super fallbacks when super isn't present; setup progress while
# steps are pending; and each skipped setup step with what skipping costs.
# The static "what runs where" lives in the project's CLAUDE.md, which Claude
# Code loads on its own.
#
# Before any of that, a "## Health" block names what is broken, one plain line
# per fault, each with its fix. It is checked live, in this order, and a
# project with no fault prints no block at all:
#   1. the project's Hyperspace environment has no interpreter that runs
#   2. it has one, but the team's server (mcp/server.py, started the way
#      .mcp.json starts it) does not answer an initialize request in 5 seconds
#   3. no jq runs, so the guardrail hooks are switched off
#   4. no Python runs, so the primer below cannot be read
# The block reports and nothing else: it repairs nothing and writes no file.
# Whether a restart is pending is not reported: a new session is the restart.
#
# The primer reads JSON (settings enabledPlugins, core_text/setup.json) with
# the Python lib/resolve-tools.sh finds: one on PATH first, and the project's
# Hyperspace environment only when PATH has none. It prints the three fixed
# plugin names and states and, for a skipped step, the name and cost text the
# setup record carries (one line each, cut short); never a settings value. It
# reads no file of the setup plugin, and never writes a file.
#
# With Hyperspace Engine present (.hyperspace/graph.db), bin/he_bridge.py
# takes over the worklog block: in a set-up project it runs the one-time
# handshake (write worklog_owner and worklog_mirror_dir, after importing
# worklog/entries once; a project that has the owner but not the mirror gets
# the mirror key and one rebuild), then prints the block from
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
# This is the one hook that uses Python, so the one hook that looks for it,
# in the same project folder the rest of this script reads.
NC_PYTHON=""
# shellcheck source=lib/resolve-tools.sh disable=SC1091
if source "$(dirname "${BASH_SOURCE[0]}")/lib/resolve-tools.sh" 2>/dev/null; then
    NC_PYTHON="$(CLAUDE_PROJECT_DIR="$PROJECT_DIR" nc_resolve_python)" || NC_PYTHON=""
else
    NC_JQ=""
fi
ASK_LINE="Stuck, found a bug, or have an idea? /technical-cofounder:contact reaches Nova Caelum."
FIX="Fix: run /technical-cofounder-setup:start"
ENGINE_FAULT="Hyperspace Engine isn't set up in this project yet, so the task graph and the worklog tools are off. $FIX (or say \"set up hyperspace\")."
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

# Prints one word: "engine" when the project's Hyperspace environment has no
# interpreter that runs, "server" when it has one and the team's server does
# not answer with it, "ok" otherwise. Every program it starts has its input
# closed (the server gets its one request, then end of input) and 5 seconds.
health_probe() {
    "$NC_PYTHON" - "$PROJECT_DIR" "$PLUGIN_ROOT" <<'PY'
import json
import os
import subprocess
import sys
import threading

LIMIT = 5  # seconds, for each program started here
project, plugin = sys.argv[1:3]
env_dir = os.path.join(project, ".hyperspace", "env")
quiet = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")  # a probe leaves no file behind


def runs(python):
    """True when it starts and exits clean, None when it never comes back."""
    try:
        done = subprocess.run([python, "-S", "-c", ""], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=LIMIT, env=quiet)
    except subprocess.TimeoutExpired:
        return None
    except OSError:
        return False
    return done.returncode == 0


def answers(python):
    """True when the team's server, started with this interpreter, answers one
    initialize request. The reply is read on a thread, so a server that never
    answers cannot hold this script past LIMIT."""
    request = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                          "clientInfo": {"name": "session-briefing", "version": "1"}}}
    try:
        server = subprocess.Popen([python, os.path.join(plugin, "mcp", "server.py")], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=quiet)
    except OSError:
        return False
    lines = []

    def ask():
        try:
            server.stdin.write((json.dumps(request) + "\n").encode("utf-8"))
            server.stdin.close()
            lines.append(server.stdout.readline())
        except Exception:
            pass

    reader = threading.Thread(target=ask, daemon=True)
    reader.start()
    reader.join(LIMIT)
    try:
        server.kill()
    except Exception:
        pass
    try:
        reply = json.loads(lines[0].decode("utf-8"))
        return reply["id"] == 1 and "serverInfo" in reply["result"]
    except Exception:
        return False


def first_file(*layouts):
    return next((p for p in (os.path.join(env_dir, *layout) for layout in layouts) if os.path.isfile(p)), None)


state = "engine"
# Both layouts: bin/ on a Mac or Linux, Scripts/ on Windows.
for layout in (("bin", "python"), ("bin", "python.exe"), ("Scripts", "python.exe")):
    python = os.path.join(env_dir, *layout)
    if not os.path.isfile(python):
        continue
    ran = runs(python)
    if ran:
        # The server is started the way .mcp.json starts it: env/bin/python.
        served = first_file(("bin", "python"), ("bin", "python.exe"))
        state = "ok" if served and answers(served) else "server"
    if ran is not False:  # one that runs, or one that hangs: stop looking
        break
sys.stdout.write(state)
sys.stdout.flush()
os._exit(0)  # the reader thread may still be waiting on a server that never answered
PY
}

health_block() {
    local state="engine" faults=""
    if [ -n "$NC_PYTHON" ]; then
        # A probe that could not run decides nothing: no line, never a guess.
        state="$(health_probe 2>/dev/null)" || state=""
    fi
    case "$state" in
        engine) faults+="$ENGINE_FAULT"$'\n' ;;
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
    "$NC_PYTHON" - "$PROJECT_DIR" "${HOME:-}" "$PLUGIN_ROOT" <<'PY' 2>/dev/null || echo "(plugin stack unavailable: python3 could not run)"
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
    # The record says which part each step belongs to; part 2 (the extras)
    # never holds up the count. A step with no part recorded counts as part 1.
    entries = [s if isinstance(s, dict) else {} for s in steps.values()]
    status = [s.get("status", "pending") for s in entries if s.get("part", 1) == 1]
    if "pending" in status:
        print(f'Setup: {status.count("done")} of {len(status)} steps done — say "continue setup" to pick up where you left off.')

    # Each skipped step, in either part, with what skipping costs. The record
    # is the only source: a step is called by the title the record carries,
    # or by its id when the record has none.
    def one_line(value):
        return " ".join(value.split())[:300] if isinstance(value, str) else ""

    skipped = [(key, s) for key, s in steps.items() if isinstance(s, dict) and s.get("status") == "skipped"][:20]
    for key, step in skipped:
        cost = one_line(step.get("if_skipped"))
        cost = cost if cost.endswith((".", "!", "?")) or not cost else cost + "."
        print(f"{one_line(step.get('title')) or one_line(key)}: skipped." + (f" {cost}" if cost else ""))
    if skipped:
        print('Say "continue setup" to pick any of these up.')
PY
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
tech_primer
echo
echo "$ASK_LINE"
echo "═══ end preload ═══"
exit 0
