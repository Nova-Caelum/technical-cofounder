#!/usr/bin/env python3
"""The plugins as the REAL Claude Code binary runs them, on this OS.

CI runs this on ubuntu, macos and windows. Keyless and unauthenticated:
`claude plugin marketplace add`, `plugin install`, `mcp list` and
`--init-only` need no account. Everything happens in a temp CLAUDE_CONFIG_DIR
and a temp project whose path holds a space.

  1. install base-novacaelum at project scope from this checkout
  2. before setup: `claude mcp list` shows `cofounder` NOT connected (its
     interpreter, .cofounder/env, does not exist yet), and `claude
     --init-only` runs the SessionStart hook, which prints the preload
  3. the interpreter ladder: with a failing `python3` first on PATH (on
     Windows, the Microsoft Store placeholders), the hook still runs
  4. setup: bin/project_env.py creates .cofounder/env; init_workspace.py
     adds the starter workspace
  5. after setup: `cofounder` is `✔ Connected` (also with the failing
     `python3` first), the preload prints the set-up block, and a worklog
     entry with non-ASCII text round-trips through the server as .mcp.json
     starts it
  6. every hooks.json command runs as Claude Code would run it (sh -c, or
     Git Bash on Windows) on a realistic payload
  7. super-novacaelum installed: `sequential-thinking` is `✔ Connected`, and
     the HTTP servers are listed

Prints every claude output verbatim; exits 1 if any check fails.
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "plugins" / "base-novacaelum"
AUTH = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN")
CONNECTED = re.compile(r"(✔|√)\s*Connected")
HOOK_OK = "Hook SessionStart:startup (SessionStart) success"
PRIMER = "## Tech primer (live)"
WINDOWS = sys.platform == "win32"
FAILS = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""), flush=True)
    if not ok:
        FAILS.append(name)


def run(argv, *, env, cwd, input_text=None, timeout=300):
    try:
        return subprocess.run(argv, cwd=str(cwd), env=env, input=input_text, capture_output=True,
                              stdin=subprocess.DEVNULL if input_text is None else None,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, None, "", f"{type(exc).__name__}: {exc}")


class Claude:
    def __init__(self, exe, env, cwd):
        self.exe, self.env, self.cwd = exe, env, cwd

    def __call__(self, *args, env=None):
        r = run([self.exe, *args], env=env or self.env, cwd=self.cwd)
        print(f"$ claude {' '.join(args)}  (exit {r.returncode})\n{r.stdout}{r.stderr}".rstrip() + "\n", flush=True)
        return r

    def server_line(self, name, env=None):
        out = self("mcp", "list", env=env).stdout
        return next((ln for ln in out.splitlines() if f":{name}:" in ln), "")

    def preload(self, log, env=None):
        """--init-only, then the debug log's SessionStart hook lines."""
        self("--debug-file", str(log), "--init-only", env=env)
        text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        lines = [ln for ln in text.splitlines() if "SessionStart" in ln and "Hook" in ln]
        for line in lines:
            print(line[:4000], flush=True)
        return "\n".join(lines)


def failing_python_first(env, tmp):
    """PATH with failing interpreters first. Windows: the Store placeholders
    (python3.exe, python.exe), so the ladder reaches `py -3`. Elsewhere: a
    `python3` that exits 9 and a `python` that works."""
    if WINDOWS:
        first = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WindowsApps"
        check("Store placeholders present", (first / "python3.exe").exists() and (first / "python.exe").exists(), str(first))
    else:
        first = tmp / "placeholder"
        first.mkdir()
        for name, body in (("python3", "echo 'placeholder python3' >&2\nexit 9"), ("python", f'exec "{sys.executable}" "$@"')):
            stub = first / name
            stub.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
            stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return dict(env, PATH=str(first) + os.pathsep + env["PATH"])


def hook_shell():
    """The shell Claude Code runs a shell-form hook in: sh on macOS and Linux,
    Git Bash on Windows (never System32's bash.exe, which is WSL)."""
    if not WINDOWS:
        return [shutil.which("sh") or "/bin/sh", "-c"]
    git = Path(shutil.which("git")).resolve()
    bash = next(p / "bin" / "bash.exe" for p in git.parents if (p / "bin" / "bash.exe").is_file())
    return [str(bash), "-c"]


def every_hook(env, project):
    hooks = json.loads((BASE / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
    shell = hook_shell()
    state = project.parent / "hook-state"
    state.mkdir(exist_ok=True)
    henv = dict(env, CLAUDE_PLUGIN_ROOT=BASE.as_posix(), CLAUDE_PROJECT_DIR=str(project), TMPDIR=str(state))
    session = "runtime-probe-session"
    payloads = {
        "SessionStart": {"session_id": session, "hook_event_name": "SessionStart", "source": "startup"},
        "UserPromptSubmit": {"session_id": session, "hook_event_name": "UserPromptSubmit", "prompt": "quick check: is it up?"},
        "Stop": {"session_id": session, "hook_event_name": "Stop", "last_assistant_message": " ".join(["word"] * 800), "stop_hook_active": False},
        "PreToolUse": {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": "Bash"},
        "PostToolUse": {"session_id": session, "hook_event_name": "PostToolUse", "tool_name": "Bash"},
        "PostToolUseFailure": {"session_id": session, "hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "error": "boom — ✓"},
    }
    expect = {"session-preload.sh": PRIMER, "concision-budget.sh": "RESPONSE BUDGET: <=120 words",
              "concision-contract.sh": "MINIMAL SUFFICIENT OUTPUT CONTRACT",
              "concision-stop.sh": '{"decision":"block"', "circuit-breaker.sh": ""}
    for event, groups in hooks.items():
        for group in groups:
            for hook in group["hooks"]:
                name = hook["command"].split("/")[-1]
                command = hook["command"].replace("${CLAUDE_PLUGIN_ROOT}", BASE.as_posix())
                r = run([*shell, command], env=henv, cwd=project, input_text=json.dumps(payloads[event]), timeout=120)
                ok = r.returncode == 0 and expect[name] in r.stdout
                check(f"hook {event}: {name}", ok, f"exit {r.returncode}; {r.stderr.strip()[:200]}")
    # the circuit breaker blocks the sixth call after five identical failures
    breaker = next(h["command"] for g in hooks["PreToolUse"] for h in g["hooks"]).replace("${CLAUDE_PLUGIN_ROOT}", BASE.as_posix())
    for _ in range(5):
        run([*shell, breaker], env=henv, cwd=project, input_text=json.dumps(payloads["PostToolUseFailure"]))
    r = run([*shell, breaker], env=henv, cwd=project, input_text=json.dumps(payloads["PreToolUse"]))
    check("hook circuit-breaker blocks after 5 identical failures", r.returncode == 2 and "BLOCKED" in r.stderr, f"exit {r.returncode}")


def worklog_round_trip(project):
    """tools/call worklog_append through the command .mcp.json names, with no
    UTF-8 help from the environment, then read the entry back."""
    server = json.loads((BASE / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["cofounder"]
    subst = lambda v: v.replace("${CLAUDE_PROJECT_DIR}", project.as_posix()).replace("${CLAUDE_PLUGIN_ROOT}", BASE.as_posix())
    summary = "runtime probe — naïve café ✓"
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "worklog_append", "arguments": {"summary": summary, "root": str(project)}}}
    proc = subprocess.run([subst(server["command"]), *map(subst, server["args"])], env=env, capture_output=True,
                          input=(json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"), timeout=60)
    reply = proc.stdout.decode("utf-8", "replace")
    print(f"worklog_append reply: {reply.strip()[:300]}", flush=True)
    sys.path.insert(0, str(BASE / "mcp"))
    import worklog  # noqa: PLC0415

    entries = worklog.recent(project, 1)
    check("worklog entry lands, UTF-8 intact", bool(entries) and entries[0]["summary"] == summary,
          entries[0]["summary"] if entries else "no entry")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    exe = shutil.which("claude")
    if exe is None:
        check("claude on PATH", False)
        return 1
    tmp = Path(tempfile.mkdtemp())
    project = tmp / "tc project"
    project.mkdir()
    (tmp / "config").mkdir()
    env = {k: v for k, v in os.environ.items() if k not in AUTH}
    env["CLAUDE_CONFIG_DIR"] = str(tmp / "config")
    claude = Claude(exe, env, project)
    placeholder_env = failing_python_first(env, tmp)

    claude("--version")
    add = claude("plugin", "marketplace", "add", str(ROOT))
    inst = claude("plugin", "install", "base-novacaelum@technical-cofounder", "--scope", "project")
    check("install at project scope", add.returncode == 0 and inst.returncode == 0)

    print("## before setup", flush=True)
    line = claude.server_line("cofounder")
    check("cofounder listed, not connected before setup", bool(line) and not CONNECTED.search(line), line)
    hook = claude.preload(tmp / "before.log")
    check("preload before setup", HOOK_OK in hook and PRIMER in hook and "/base-novacaelum:setup" in hook)
    print("## before setup, failing python3 first on PATH", flush=True)
    line = claude.server_line("cofounder", env=placeholder_env)
    check("cofounder listed, not connected (placeholder first)", bool(line) and not CONNECTED.search(line), line)
    hook = claude.preload(tmp / "placeholder.log", env=placeholder_env)
    check("preload runs past a failing python3", HOOK_OK in hook and PRIMER in hook)

    print("## setup", flush=True)
    r = run([sys.executable, str(BASE / "bin" / "project_env.py"), str(project)], env=env, cwd=project)
    print(r.stdout + r.stderr, flush=True)
    check("project_env ENV_OK", r.returncode == 0 and "ENV_OK" in r.stdout)
    r = run([sys.executable, str(BASE / "bin" / "init_workspace.py"), str(project), "--no-obsidian", "--no-super"],
            env=env, cwd=project, input_text="")
    check("init_workspace", r.returncode == 0, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr)

    print("## after setup", flush=True)
    line = claude.server_line("cofounder")
    check("cofounder connected after setup", bool(CONNECTED.search(line)), line)
    line = claude.server_line("cofounder", env=placeholder_env)
    check("cofounder connected after setup (placeholder first)", bool(CONNECTED.search(line)), line)
    hook = claude.preload(tmp / "after.log")
    check("preload after setup", HOOK_OK in hook and PRIMER in hook and "session preload" in hook
          and "cannot start" not in hook)
    worklog_round_trip(project)

    print("## every hooks.json command", flush=True)
    every_hook(env, project)

    print("## super-novacaelum", flush=True)
    inst = claude("plugin", "install", "super-novacaelum@technical-cofounder", "--scope", "project")
    out = claude("mcp", "list").stdout
    lines = {name: next((ln for ln in out.splitlines() if f":{name}:" in ln), "") for name in
             ("sequential-thinking", "context7", "exa", "browserbase")}
    check("super installed", inst.returncode == 0)
    check("sequential-thinking connected", bool(CONNECTED.search(lines["sequential-thinking"])), lines["sequential-thinking"])
    check("super HTTP servers listed", all(lines[n] for n in ("context7", "exa", "browserbase")))

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"RUNTIME {'FAIL ' + str(FAILS) if FAILS else 'PASS'}", flush=True)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
