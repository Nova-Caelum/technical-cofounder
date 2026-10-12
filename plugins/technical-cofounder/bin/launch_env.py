#!/usr/bin/env python3
"""Start a project's Hyperspace environment only when setup built it on this
computer.

Source: Nova Caelum (2026). License: MIT.

This one file ships twice, byte for byte: as `hyperspace/provenance.py` in
Hyperspace Engine and as `bin/launch_env.py` in Technical Cofounder. Each
plugin's MCP server, and every script that runs the project's environment,
goes through it.

Why: the environment lives inside the project, at `.hyperspace/env`, and a
downloaded or cloned folder can ship a file at `.hyperspace/env/bin/python`.
Starting that file runs whatever it is. So when setup builds the environment
it also writes a record OUTSIDE the project, in `~/.hyperspace/envs.json`, and
this launcher starts the environment only when the folder still matches its
record: the same project path, the same environment folder (by path and by
file-system identity), the same `pyvenv.cfg` and the same interpreter. A
folder that arrived from somewhere else has no record on this computer, so it
is refused and nothing in it runs. What the check does not cover: a file
added inside an environment that was already recorded (for example a `.pth`
file in its site-packages), which needs write access to a folder the user
already set up.

Standard library only. It is started by the computer's own Python, never the
project's, and runs on any Python from 3.8.

    launch_env.py run [--] <args...>   run the project's environment Python
                                       with <args>, or refuse with one line
    launch_env.py check [<project>]    print ok, unknown or missing

The project is CLAUDE_PROJECT_DIR, else the current folder (`check` can be
given one). Exit codes: 0 ok, 2 usage, 3 refused (no record, or the folder no
longer matches it), 4 no environment. Setup records an environment by calling
register(); there is no command for it, on purpose: the way to make a folder's
environment trusted is to let setup build it.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time

OK, USAGE, REFUSED, MISSING = 0, 2, 3, 4
RECORD_VERSION = 1
# The fields that must match the record, in the order they are compared.
FIELDS = ("project", "env", "env_id", "pyvenv_cfg_sha256", "python", "python_sha256")

REFUSED_LINE = (
    "This folder's Hyperspace environment (.hyperspace/env) was not built by setup on this computer, "
    "or has changed since, so nothing in it was started. To rebuild it, run setup again: "
    "/technical-cofounder-setup:start and choose repair, or the hyperspace-setup skill."
)
MISSING_LINE = (
    "This folder has no Hyperspace environment (.hyperspace/env) yet. "
    "Run setup: /technical-cofounder-setup:start, or the hyperspace-setup skill."
)
WORDS = {OK: "ok", REFUSED: "unknown", MISSING: "missing"}


def record_path():
    """~/.hyperspace/envs.json: the user's profile folder, which the Claude
    desktop app on Windows does not redirect (it redirects AppData)."""
    return os.path.join(os.path.expanduser("~"), ".hyperspace", "envs.json")


def project_dir(given=None):
    return os.path.realpath(given or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def env_dir(project):
    return os.path.join(project, ".hyperspace", "env")


def interpreter(env, platform=None):
    """The interpreter a virtual environment contains on this OS."""
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        return os.path.join(env, "Scripts", "python.exe")
    return os.path.join(env, "bin", "python")


def _key(project):
    return os.path.normcase(os.path.realpath(project))


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def _inside(path, folder):
    path, folder = os.path.normcase(path), os.path.normcase(folder)
    return path.startswith(folder.rstrip(os.sep) + os.sep)


def fingerprint(project):
    """What identifies the project's environment now, or None when there is
    none. Raises OSError when something is there but cannot be read.

    The interpreter is named by its real path. When that real path is inside
    the environment (Windows copies python.exe in) its bytes are hashed too;
    when it is outside (a POSIX venv links to the Python it was made from) the
    path alone is compared, because the file belongs to that Python."""
    env = env_dir(project)
    if not os.path.lexists(env):
        return None
    real_env = os.path.realpath(env)
    status = os.stat(real_env)
    python = os.path.realpath(interpreter(env))
    return {
        "project": os.path.realpath(project),
        "env": real_env,
        "env_id": "%d:%d" % (status.st_dev, status.st_ino),
        "pyvenv_cfg_sha256": _sha256(os.path.join(real_env, "pyvenv.cfg")),
        "python": python,
        "python_sha256": _sha256(python) if _inside(python, real_env) else None,
    }


def _load():
    try:
        with open(record_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    envs = data.get("envs") if isinstance(data, dict) else None
    return envs if isinstance(envs, dict) else {}


def verify(project):
    """(status, interpreter, reason). OK comes with the interpreter to run;
    REFUSED and MISSING come with None and a few words on why."""
    try:
        current = fingerprint(project)
    except OSError as exc:
        return REFUSED, None, "it could not be read: %s" % exc.__class__.__name__
    if current is None:
        return MISSING, None, "there is no .hyperspace/env"
    entry = _load().get(_key(project))
    if not isinstance(entry, dict):
        return REFUSED, None, "this computer has no record of it"
    for field in FIELDS:
        if entry.get(field) != current[field]:
            return REFUSED, None, "its %s no longer matches the record" % field
    python = interpreter(env_dir(project))
    if not os.path.isfile(python):
        return REFUSED, None, "it has no interpreter"
    return OK, python, "ok"


def register(project, by=""):
    """Record the project's environment as built on this computer. Called by
    setup right after it builds the environment, and by nothing else. Returns
    the entry; raises OSError when there is no environment to record."""
    current = fingerprint(project)
    if current is None or not os.path.isfile(interpreter(env_dir(project))):
        raise FileNotFoundError("no environment with an interpreter at %s" % env_dir(project))
    entry = dict(current, registered_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), by=by)
    path = record_path()
    folder = os.path.dirname(path)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    envs = _load()
    envs[_key(project)] = entry
    handle_fd, partial = tempfile.mkstemp(prefix="envs.", suffix=".part", dir=folder)
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
            json.dump({"version": RECORD_VERSION, "envs": envs}, handle, indent=1, sort_keys=True)
            handle.write("\n")
        os.replace(partial, path)
    except BaseException:
        try:
            os.unlink(partial)
        except OSError:
            pass
        raise
    return entry


def refusal(status, reason):
    """The one plain line a refused start prints."""
    return "%s (%s)" % (MISSING_LINE if status == MISSING else REFUSED_LINE, reason)


def run(args, project=None):
    """Start the project's environment Python with args, or refuse. On POSIX
    the launcher becomes that Python (exec); Windows has no true exec, so it
    waits for it and passes its exit code on."""
    status, python, reason = verify(project_dir(project))
    if status != OK:
        sys.stderr.write(refusal(status, reason) + "\n")
        return status
    argv = [python] + list(args)
    try:
        if sys.platform == "win32":
            return subprocess.call(argv)
        os.execv(python, argv)
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        sys.stderr.write("The Hyperspace environment could not be started: %s\n" % exc)
        return 1
    return 1  # not reached: execv does not return


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    verb, rest = (argv[0], argv[1:]) if argv else ("", [])
    if verb == "run":
        return run(rest[1:] if rest[:1] == ["--"] else rest)
    if verb == "check" and len(rest) <= 1:
        status, _, _ = verify(project_dir(rest[0] if rest else None))
        print(WORDS[status])
        return status
    sys.stderr.write("usage: launch_env.py run [--] <args...> | check [<project>]\n")
    return USAGE


if __name__ == "__main__":
    sys.exit(main())
