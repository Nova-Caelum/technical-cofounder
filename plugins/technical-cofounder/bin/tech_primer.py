#!/usr/bin/env python3
"""tech_primer.py -- the session briefing's live tech primer.

Source: Nova Caelum (2026). License: MIT.

    python3 tech_primer.py <project> <home> <plugin root>

Prints which Nova Caelum plugins are present, expected but missing, or not
chosen; whether Hyperspace Engine's verifier judge is on or off, and how to
switch it; a pointer to the without-super fallbacks when super isn't present;
a line saying no run is open yet, when Hyperspace Engine has no open run; setup
progress while steps are pending; and each skipped setup step with what
skipping costs. hooks/session-preload.sh prints the heading above it.

It reads JSON (settings enabledPlugins, core_text/setup.json) and the
`judge = "..."` line of .hyperspace/config.toml, which the engine obeys (a
record that disagrees is stale), and names only a known judge; the setup
record adds why it is off when it names the same judge. It prints the
three fixed plugin names and states and, for a skipped step, the name and cost
text the setup record carries (one line each, cut short); never a settings
value. It reads no file of the setup plugin, starts no program, and never
writes a file. Standard library only.
"""
import json
import re
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
engine_config = project / ".hyperspace" / "config.toml"
he_state = state(enabled("hyperspace-engine") or engine_config.is_file(), False)
he_owned = " · worklog: hyperspace (owned by TC preload)" if he_mode == "tc-preload" else ""
print(f"- hyperspace-engine: {he_state}{he_owned}")
if engine_config.is_file():
    try:
        found = re.search(r"""(?m)^\s*judge\s*=\s*["']([^"']*)["']""", engine_config.read_text(encoding="utf-8"))
    except Exception:
        found = None
    judge = found.group(1) if found else "none"  # the engine's default
    if judge != "none":
        named = f" ({judge})" if judge in ("claude-code", "codex", "openrouter", "anthropic") else ""
        print(f'- verifier judge: on{named} — say "turn off the judge" to stop it.')
    elif choices.get("judge") == "none" and choices.get("judge_why") in ("not-signed-in", "no-answer"):
        print("- verifier judge: off — Claude Code's command line is not signed in or did not answer: "
              'run `claude auth login` in your terminal, then say "turn on the judge".')
    else:
        print('- verifier judge: off — say "turn on the judge" to switch it on.')
if not super_present:
    print(f"Without super: {plugin / 'reference' / 'without-super.md'} lists what to use instead of each super service.")

# A run is open while its loop.state.json under hyperspace/runs has a status
# other than done, descoped or killed: the rule Hyperspace Engine's own
# briefing uses to print a block per open run. Only the status is read, and
# nothing from the file is printed. An unreadable file is no open run.
FINISHED = ("done", "descoped", "killed")
states = (load(path) for path in (project / "hyperspace" / "runs").glob("*/loop.state.json"))
if not any(state and state.get("status") not in FINISHED for state in states):
    print("No run is open yet in this project: the first step of any piece of work is Understand"
          " (say what you want, and the team frames it before anything is built).")

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
