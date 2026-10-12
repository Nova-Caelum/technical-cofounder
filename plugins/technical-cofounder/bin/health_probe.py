#!/usr/bin/env python3
"""health_probe.py -- the session briefing's check of the project's Hyperspace
environment and the team's server.

Source: Nova Caelum (2026). License: MIT.

    python3 health_probe.py <project> <plugin root>

Prints one word for hooks/session-preload.sh's Health block:
    engine   there is no .hyperspace/env, or its interpreter does not run
    unknown  there is one, but setup did not build it on this computer (or
             built it before setup kept a record), so nothing in it was started
    server   it runs, but the team's server does not answer an initialize
             request with it
    ok       otherwise

launch_env.py (beside this file) is asked first, and nothing from the project
is started unless it answers ok. What is started then goes through it, the way
.mcp.json starts the team's server: this Python, -I, launch_env.py run --. Each
program gets its input closed (the server gets its one request, then end of
input) and 5 seconds. Writes no file. Standard library only.
"""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:  # launch_env.py sits beside this file
    sys.path.insert(0, _HERE)
import launch_env  # noqa: E402

LIMIT = 5  # seconds, for each program started here


def runs(argv, env):
    """True when it starts and exits clean, None when it never comes back."""
    try:
        done = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=LIMIT, env=env)
    except subprocess.TimeoutExpired:
        return None
    except OSError:
        return False
    return done.returncode == 0


def answers(argv, env):
    """True when the team's server, started with argv, answers one initialize
    request. The reply is read on a thread, so a server that never answers
    cannot hold this script past LIMIT."""
    request = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                          "clientInfo": {"name": "session-briefing", "version": "1"}}}
    try:
        server = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, env=env)
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


def state(project, plugin):
    status, _, _ = launch_env.verify(project)
    if status == launch_env.MISSING:
        return "engine"
    if status != launch_env.OK:
        return "unknown"
    # PYTHONDONTWRITEBYTECODE: a probe leaves no file behind.
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project, PYTHONDONTWRITEBYTECODE="1")
    launch = [sys.executable, "-I", str(Path(__file__).resolve().with_name("launch_env.py")), "run", "--"]
    if not runs(launch + ["-S", "-c", ""], env):  # one that fails or hangs
        return "engine"
    return "ok" if answers(launch + [os.path.join(plugin, "mcp", "server.py")], env) else "server"


if __name__ == "__main__":
    sys.stdout.write(state(*sys.argv[1:3]))
    sys.stdout.flush()
    os._exit(0)  # the reader thread may still be waiting on a server that never answered
