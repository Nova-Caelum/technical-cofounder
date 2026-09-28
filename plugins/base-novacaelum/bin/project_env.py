#!/usr/bin/env python3
"""The project's own Python environment, <project>/.cofounder/env.

Usage:
    <python> project_env.py <project-dir>

The cofounder MCP server is started by Claude Code with no shell, and
.mcp.json has no per-platform field, so .mcp.json names ONE interpreter path
that must hold on every OS: ${CLAUDE_PROJECT_DIR}/.cofounder/env/bin/python.
This script makes it true. It creates the environment with the standard
library's venv module and installs nothing into it (no pip); it can see the
interpreter's own site-packages, so the verifier's `tests` check imports what
it always could. On Windows a venv keeps its interpreter at
Scripts\\python.exe, so env\\bin becomes a directory junction to env\\Scripts
(junctions need no administrator rights or Developer Mode), and every Windows
spawner resolves the extensionless env/bin/python to python.exe.

It then runs env/bin/python to prove it, keeps the environment out of git
(.cofounder/.gitignore), and prints `ENV_OK <path>` or `ENV_FAIL <reason>`.
An environment whose env/bin/python already runs is left alone.

Exit codes: 0 ok, 1 failed, 2 usage. Standard library only.
"""
import os
import subprocess
import sys
import venv
from pathlib import Path

WINDOWS = "win32"


def portable_python(env):
    """env/bin/python — the spelling .mcp.json and the skills use on every OS."""
    return Path(env) / "bin" / "python"


def runs(python):
    try:
        return subprocess.run([str(python), "-c", "import sys"], stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _create_junction(target, link):
    """An NTFS directory junction link -> target: CPython's own
    _winapi.CreateJunction, else `mklink /J`."""
    try:
        import _winapi

        _winapi.CreateJunction(target, link)
        return
    except (ImportError, AttributeError):
        pass
    proc = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", link, target], capture_output=True, text=True)
    if proc.returncode != 0:
        raise OSError(proc.stderr.strip() or proc.stdout.strip() or f"mklink exited {proc.returncode}")


def link_bin_to_scripts(env, platform=None, create_junction=_create_junction):
    """Make env/bin/python reach the venv's interpreter. Returns (ok, message)
    and never raises. POSIX: nothing to do. Windows: env/bin becomes a junction
    to env/Scripts; a bin that already holds python.exe is left alone."""
    if (platform or sys.platform) != WINDOWS:
        return True, "env/bin is the venv's own layout"
    env = Path(env)
    scripts, bin_dir = env / "Scripts", env / "bin"
    if not (scripts / "python.exe").is_file():
        return False, f"cannot link env/bin: {scripts / 'python.exe'} does not exist"
    if (bin_dir / "python.exe").is_file():
        return True, f"{bin_dir} already reaches python.exe"
    if os.path.lexists(bin_dir):
        return False, f"{bin_dir} exists but holds no python.exe; remove it and run this again"
    try:
        create_junction(str(scripts), str(bin_dir))
    except OSError as exc:
        return False, f"could not create the junction {bin_dir} -> {scripts}: {exc}"
    if not (bin_dir / "python.exe").is_file():
        return False, f"the junction {bin_dir} -> {scripts} does not reach python.exe"
    return True, f"junction {bin_dir} -> {scripts}"


def create(project):
    """(ok, message) for <project>/.cofounder/env."""
    home = Path(project).expanduser().resolve() / ".cofounder"
    env = home / "env"
    python = portable_python(env)
    if runs(python):
        return True, f"{python.as_posix()} already runs"
    try:
        home.mkdir(parents=True, exist_ok=True)
        ignore = home / ".gitignore"
        if not ignore.exists():
            ignore.write_text("env/\n", encoding="utf-8")
        venv.EnvBuilder(with_pip=False, system_site_packages=True, symlinks=os.name != "nt").create(env)
    except (OSError, subprocess.CalledProcessError) as exc:
        return False, f"could not create {env}: {exc}"
    ok, message = link_bin_to_scripts(env)
    if not ok:
        return False, message
    if not runs(python):
        return False, f"{python.as_posix()} was created but does not run"
    return True, f"{python.as_posix()} runs"


def main(argv):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    if len(argv) != 1:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    ok, message = create(argv[0])
    print(f"{'ENV_OK' if ok else 'ENV_FAIL'} {message}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
