"""session_preload.py — SessionStart hook (run by session-preload.sh).

Source: adapted from Nova Caelum's internal agentOS session-preload pattern
(2026). License: MIT.

If this project has been set up (core_text/user.md, or a legacy user.md at
the project root), inject it plus the 3 most recent worklog entries into
context. Otherwise print one line pointing at /base-novacaelum:setup. Either
way, print the live tech primer: which Nova Caelum plugins are present,
expected but missing, or not chosen; a pointer to the without-super fallbacks
when super isn't present; and setup progress while steps are pending. The
static "what runs where" lives in the project's CLAUDE.md, which Claude Code
loads on its own.

The primer prints only the three fixed plugin names and states, never a
settings value, and never writes a file.

With Hyperspace Engine present (.hyperspace/graph.db), bin/he_bridge.py takes
over the worklog block: in a set-up project it runs the one-time handshake
(write worklog_owner, and worklog_mirror_dir for an Obsidian view, after
importing worklog/entries once), then prints the block from Hyperspace's store
when TC owns the preload, or nothing when Hyperspace's own hook does. Without
.hyperspace/graph.db the markdown block below is used.

Plain stdout on SessionStart is added to Claude's context as plain text
(code.claude.com/docs/en/hooks-guide) — no JSON needed here.

Fails open: nothing in this script can break the session. Every fallible read
degrades to a visible note, never a nonzero exit.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from _shared import read_stdin, utf8_stdio

ASK_LINE = "Stuck, found a bug, or have an idea? /base-novacaelum:ask reaches Nova Caelum."


def load(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def tech_primer(project, home, plugin):
    print("## Tech primer (live)")
    print()
    try:
        _primer_body(project, home, plugin)
    except Exception:
        print("(plugin stack unavailable: the primer could not run)")


def _primer_body(project, home, plugin):
    sys.path.insert(0, str(plugin / "bin"))
    try:
        import he_bridge
        he_mode = he_bridge.mode(project)
    except Exception:
        he_mode = "tc"

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
    print("- base-novacaelum: present")
    print(f"- super-novacaelum: {state(super_present, choices.get('super') == 'yes')}")
    he_state = state(enabled("hyperspace-engine") or (project / ".hyperspace" / "config.toml").is_file(), False)
    he_owned = " · worklog: hyperspace (owned by TC preload)" if he_mode == "tc-preload" else ""
    print(f"- hyperspace-engine: {he_state}{he_owned}")
    if not super_present:
        print(f"Without super: {(plugin / 'reference' / 'without-super.md').as_posix()} lists what to use instead of each super service.")

    if record:
        steps = record.get("steps") if isinstance(record.get("steps"), dict) else {}
        ids = [s.get("id") for s in load(plugin / "setup" / "steps.json").get("steps", []) if isinstance(s, dict)] or list(steps)
        status = [(steps.get(i) if isinstance(steps.get(i), dict) else {}).get("status", "pending") for i in ids]
        if "pending" in status:
            print(f'Setup: {status.count("done")} of {len(ids)} steps done — say "continue setup" to pick up where you left off.')


def print_file(path, fallback):
    try:
        sys.stdout.write(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        print(fallback)


def worklog_block(project, plugin):
    if (project / ".hyperspace" / "graph.db").is_file():
        sys.stdout.flush()
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        try:
            done = subprocess.run([sys.executable, str(plugin / "bin" / "he_bridge.py"), "preload", str(project)],
                                  stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env).returncode == 0
        except OSError:
            done = False
        if not done:
            print("(worklog unavailable: the Hyperspace bridge could not run)")
        return
    print("## Recent worklog — last 3")
    print()
    entries = project / "worklog" / "entries"
    try:
        # Entries are named <timestamp>-<slug>.md, so a lexical sort is a
        # chronological sort.
        recent = sorted(p for p in entries.iterdir()
                        if p.name.endswith(".md") and p.is_file() and not p.is_symlink())[-3:]
    except OSError:
        recent = []
    if not recent:
        print("(no worklog entries yet)")
    for entry in recent:
        print(f"--- {entry.name} ---")
        print_file(entry, "")
        print()


def main():
    utf8_stdio()
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    plugin = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent)
    home = Path(os.environ.get("HOME", ""))
    # Consume stdin so nothing upstream blocks on an unread pipe; the content
    # is irrelevant here (this hook reads CLAUDE_PROJECT_DIR, not stdin).
    read_stdin()

    user_md, legacy = project / "core_text" / "user.md", False
    if not user_md.is_file() and (project / "user.md").is_file():
        user_md, legacy = project / "user.md", True

    if not user_md.is_file():
        print("base-novacaelum: this project hasn't been set up yet — run /base-novacaelum:setup to copy the starter workspace in.")
        print()
        tech_primer(project, home, plugin)
        print()
        print(ASK_LINE)
        return 0

    print("═══ base-novacaelum session preload ═══")
    print()
    print("## user.md")
    print()
    print_file(user_md, "(could not read user.md)")
    if legacy:
        print("Note: this profile is at the old location (./user.md); /base-novacaelum:setup can move it into core_text/ for you.")
    print()
    worklog_block(project, plugin)
    print()
    tech_primer(project, home, plugin)
    print()
    print(ASK_LINE)
    print("═══ end preload ═══")
    return 0


if __name__ == "__main__":
    sys.exit(main())
