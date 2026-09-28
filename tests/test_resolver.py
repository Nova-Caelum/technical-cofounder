"""Unit tests for hooks/lib/python.sh, the plugin's one interpreter rule: the
project environment (.cofounder/env, either venv layout), then python3, then
python, then `py -3`, each EXECUTED before it is trusted.

Every candidate is a fake on a PATH that holds nothing else, so the machine's
own interpreters never decide a result. The placeholder fake behaves like the
Windows Store alias: it prints an install prompt and exits non-zero.

Standard library only.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "plugins" / "base-novacaelum" / "hooks"
LIB = HOOKS_DIR / "lib" / "python.sh"
SH = shutil.which("sh")

REAL = Path(sys.executable).as_posix()
WORKS = f'exec "{REAL}" "$@"'
PLACEHOLDER = 'while read -r _; do :; done\necho "Python was not found; run without arguments to install from the Microsoft Store" >&2\nexit 9'
PY_LAUNCHER = f'[ "$1" = -3 ] || exit 9\nshift\nexec "{REAL}" "$@"'

RESOLVE = '. "$1"; if find_python; then printf "%s|%s" "$PY" "$PY_ARG"; else printf NONE; fi'


def fake(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)
    return path


class ResolverTests(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.bin = tmp / "bin"
        self.bin.mkdir()
        self.project = tmp / "a project"
        self.project.mkdir()
        self.tmp = tmp
        self.env = {"PATH": str(self.bin), "CLAUDE_PROJECT_DIR": str(self.project)}
        for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):  # Windows needs these to start any process
            if key in os.environ:
                self.env[key] = os.environ[key]

    def resolve(self):
        r = subprocess.run([SH, "-c", RESOLVE, "sh", str(LIB)], env=self.env, capture_output=True,
                           text=True, stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def assertPicked(self, out, path, arg=""):
        picked, _, picked_arg = out.partition("|")
        self.assertEqual(Path(picked).name, path.name, out)
        self.assertEqual(Path(picked).parent.name, path.parent.name, out)
        self.assertEqual(picked_arg, arg, out)

    def test_python3_first_when_it_runs(self):
        py3 = fake(self.bin / "python3", WORKS)
        fake(self.bin / "python", WORKS)
        self.assertPicked(self.resolve(), py3)

    def test_placeholder_python3_is_skipped_for_python(self):
        fake(self.bin / "python3", PLACEHOLDER)
        py = fake(self.bin / "python", WORKS)
        self.assertPicked(self.resolve(), py)

    def test_py_launcher_last_with_dash_3(self):
        fake(self.bin / "python3", PLACEHOLDER)
        fake(self.bin / "python", PLACEHOLDER)
        launcher = fake(self.bin / "py", PY_LAUNCHER)
        self.assertPicked(self.resolve(), launcher, "-3")

    def test_project_env_wins_over_python3(self):
        fake(self.bin / "python3", WORKS)
        env_py = fake(self.project / ".cofounder" / "env" / "bin" / "python", WORKS)
        self.assertPicked(self.resolve(), env_py)

    def test_project_env_windows_layout(self):
        fake(self.bin / "python3", WORKS)
        env_py = fake(self.project / ".cofounder" / "env" / "Scripts" / "python.exe", WORKS)
        self.assertPicked(self.resolve(), env_py)

    def test_broken_project_env_falls_through(self):
        fake(self.project / ".cofounder" / "env" / "bin" / "python", PLACEHOLDER)
        py3 = fake(self.bin / "python3", WORKS)
        self.assertPicked(self.resolve(), py3)

    def test_nothing_runs(self):
        for name in ("python3", "python", "py"):
            fake(self.bin / name, PLACEHOLDER)
        self.assertEqual(self.resolve(), "NONE")

    def test_run_hook_fails_open_without_python(self):
        fake(self.bin / "python3", PLACEHOLDER)
        env = dict(self.env, HOOKS_DIR=str(self.tmp))
        r = subprocess.run([SH, "-c", '. "$1"; run_hook anything', "sh", str(LIB)], env=env,
                           capture_output=True, text=True, input="{}", timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no working Python", r.stderr)

    def test_run_hook_runs_the_module_with_stdin_intact(self):
        # The placeholder reads stdin before failing; the hook must still get it.
        fake(self.bin / "python3", PLACEHOLDER)
        fake(self.bin / "python", WORKS)
        (self.tmp / "echo_hook.py").write_text("import sys\nprint('got:' + sys.stdin.read())\n", encoding="utf-8")
        env = dict(self.env, HOOKS_DIR=str(self.tmp))
        r = subprocess.run([SH, "-c", '. "$1"; run_hook echo_hook', "sh", str(LIB)], env=env,
                           capture_output=True, text=True, input='{"prompt": "hi"}', timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), 'got:{"prompt": "hi"}')


if __name__ == "__main__":
    unittest.main()
