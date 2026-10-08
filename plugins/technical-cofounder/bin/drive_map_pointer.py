#!/usr/bin/env python3
"""drive_map_pointer.py -- Technical Cofounder's side of the project drive map.

The map is Hyperspace Engine's: its bin/drive_map.py `tree` mode walks the
project under <project>/.drivemap.toml and writes core_text/drive-map.md. This
module is the adapter. At session start it finds that script, runs it with the
project's own Hyperspace interpreter, and prints ONE line pointing at the map.
The map itself is never printed: a SessionStart hook's output has a size cap and
becomes model context.

Finding the engine. he_bridge.py reaches the engine through the project's
Hyperspace environment (`.hyperspace/env`, which has the `hyperspace` package).
The environment does not have bin/drive_map.py: bin/ is part of the engine
plugin, not of the installed package. So the script is found where Claude Code
records an installed plugin: installed_plugins.json, in the plugins folder, one
list of installs per `<name>@<catalog>` with each install's `installPath`. The
plugins folder is, in order:
    $CLAUDE_CODE_PLUGIN_CACHE_DIR
    the folder three levels above this plugin's own root (the plugin sits at
        <plugins>/cache/<catalog>/<name>/<version>)
    $CLAUDE_CONFIG_DIR/plugins
    ~/.claude/plugins
An install made for another project is not this project's engine.

The script runs with `.hyperspace/env`'s Python, not the system python3: the
engine needs 3.11 (tomllib) and the system one may be older.

Failing is quiet and free: one line on stderr (the hook log, never the model's
context), exit 0, and no pointer line, because a pointer to a map that was not
written is worse than none. A project with no map this session simply has none.

CLI:
    python3 drive_map_pointer.py preload <project>   write the map, print the pointer line
    python3 drive_map_pointer.py locate <project>    print the engine script's path (exit 1: not found)

Standard library only.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAP = "core_text/drive-map.md"
ENGINE_PREFIX = "hyperspace-engine@"
PREFERRED_ENGINE = "hyperspace-engine@nova-caelum"
RUN_SECONDS = 20  # the most a session start waits for the engine
_COUNT = re.compile(r"\((\d+) folders?\b")


class Quiet(Exception):
    """Why there is no map this session: one line for the hook log."""


def log(message):
    try:
        print(f"drive-map: {message}", file=sys.stderr)
    except Exception:
        pass


def plugin_folders():
    """Where installed_plugins.json may be, most specific first."""
    found = []
    if os.environ.get("CLAUDE_CODE_PLUGIN_CACHE_DIR"):
        found.append(Path(os.environ["CLAUDE_CODE_PLUGIN_CACHE_DIR"]))
    own = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent).resolve()
    if len(own.parents) > 3 and own.parents[2].name == "cache":
        found.append(own.parents[3])
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        found.append(Path(os.environ["CLAUDE_CONFIG_DIR"]) / "plugins")
    found.append(Path.home() / ".claude" / "plugins")
    return found


def _same_folder(a, b):
    return bool(a) and os.path.normcase(os.path.realpath(str(a))) == os.path.normcase(os.path.realpath(str(b)))


def find_engine_script(project, folders):
    """The engine's bin/drive_map.py recorded for this project (or for the user), else None."""
    for folder in folders:
        try:
            plugins = json.loads((folder / "installed_plugins.json").read_text(encoding="utf-8")).get("plugins", {})
        except (OSError, ValueError, AttributeError):
            continue
        found = []
        for plugin_id, installs in plugins.items() if isinstance(plugins, dict) else ():
            if not str(plugin_id).startswith(ENGINE_PREFIX):
                continue
            for install in installs if isinstance(installs, list) else [installs]:
                if not isinstance(install, dict) or not install.get("installPath"):
                    continue
                if install.get("projectPath") and not _same_folder(install["projectPath"], project):
                    continue  # installed for another project
                script = Path(install["installPath"]) / "bin" / "drive_map.py"
                if script.is_file():
                    rank = (plugin_id != PREFERRED_ENGINE, not install.get("projectPath"))
                    found.append((rank, str(install.get("lastUpdated") or ""), script))
        if found:
            # this catalog's engine first, then an install made for this very project, then the newest
            found.sort(key=lambda f: f[1], reverse=True)
            found.sort(key=lambda f: f[0])
            return found[0][2]
    return None


def engine_python(project):
    """The project's own Hyperspace interpreter (Mac and Linux: bin/, Windows: Scripts/)."""
    env = Path(project) / ".hyperspace" / "env"
    for parts in (("bin", "python"), ("bin", "python.exe"), ("Scripts", "python.exe")):
        if env.joinpath(*parts).is_file():
            return env.joinpath(*parts)
    return None


def preload(project, seconds=RUN_SECONDS):
    """Write the map and print the one pointer line. Always returns 0."""
    project = Path(project)
    try:
        script = find_engine_script(project, plugin_folders())
        if script is None:
            raise Quiet("Hyperspace Engine's drive_map.py was not found in the installed plugins, so there is no drive map this session")
        python = engine_python(project)
        if python is None:
            raise Quiet("this project has no Hyperspace environment yet, so there is no drive map this session")
        target = project / MAP
        try:
            done = subprocess.run(
                [str(python), str(script), "tree", str(project), "--out", str(target)],
                stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=seconds, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            )
        except subprocess.TimeoutExpired:
            raise Quiet(f"the engine did not finish in {seconds} seconds, so there is no drive map this session")
        except OSError as exc:
            raise Quiet(f"the engine could not be started ({exc.__class__.__name__})")
        if done.returncode != 0:
            tail = next((ln.strip() for ln in reversed(done.stderr.splitlines()) if ln.strip()), "no message")
            raise Quiet(f"the engine's `tree` mode failed (an engine from before it?): {tail[:160]}")
        counted = _COUNT.search(done.stdout)
        if not counted or not target.is_file():
            raise Quiet("the engine reported no map, so there is no drive map this session")
        n = int(counted.group(1))
        print(f"Drive map: {MAP} ({n} folder{'' if n == 1 else 's'}) — read it before creating a file.")
    except Quiet as why:
        log(str(why))
    except Exception as exc:  # nothing here may break a session
        log(f"unexpected {exc.__class__.__name__}; no drive map this session")
    return 0


def locate(project):
    script = find_engine_script(Path(project), plugin_folders())
    if script is None:
        log("Hyperspace Engine's drive_map.py was not found in the installed plugins")
        return 1
    print(script)
    return 0


def main(argv):
    if len(argv) != 3 or argv[1] not in ("preload", "locate"):
        print("usage: drive_map_pointer.py preload|locate <project>", file=sys.stderr)
        return 2
    for stream in (sys.stdout, sys.stderr):  # Windows pipes default to the ANSI code page
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    return (preload if argv[1] == "preload" else locate)(argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
