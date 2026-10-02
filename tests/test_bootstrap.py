"""Tests for the two first-step scripts:
plugins/technical-cofounder-setup/installer/bootstrap.sh and bootstrap.ps1.

bootstrap.sh runs for real here, against a temp HOME and a PATH whose first
folder holds stand-in programs, so nothing is installed and nothing outside
the temp folder is touched. bootstrap.ps1 runs only on Windows; elsewhere its
text is checked for syntax Windows PowerShell 5.1 does not have.

Standard library only.
"""
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALLER = REPO_ROOT / "plugins" / "technical-cofounder-setup" / "installer"
BOOTSTRAP_SH = INSTALLER / "bootstrap.sh"
BOOTSTRAP_PS1 = INSTALLER / "bootstrap.ps1"

LAST_LINE = re.compile(r"^BOOTSTRAP=(OK python=\S.*|NEEDS_RESTART reason=\S.*|NEEDS_YOU reason=\S.*)$")
UV_INSTALL = "curl -LsSf https://astral.sh/uv/install.sh | sh"
WINDOWS = sys.platform == "win32"
BASE_PATH = "/usr/bin:/bin"
# A Claude Code started from a terminal window keeps that window's old PATH,
# so closing Claude Code alone is not a restart.
TERMINAL_TOO = "If you started Claude Code from a terminal window, close that window too."
REOPEN = "Close Claude Code completely, open it again, and paste the same message. " + TERMINAL_TOO
RESTART_AFTER_INSTALL = "Git was installed. " + REOPEN
RESTART_STALE_SESSION = "Git is installed, but this session started before it was. " + REOPEN


def snapshot(root):
    out = {}
    for path in sorted(Path(root).rglob("*")):
        st = path.lstat()
        out[str(path.relative_to(root))] = (st.st_size if path.is_file() else 0, st.st_mtime_ns)
    return out


@unittest.skipIf(WINDOWS, "bootstrap.sh is the macOS and Linux first step")
class Sh(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name).resolve()
        self.home = self.root / "home"
        self.shims = self.root / "shims"
        self.home.mkdir()
        self.shims.mkdir()
        self.shim("git", 'echo "git version 2.99.0"')

    def shim(self, name, body):
        path = self.shims / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return path

    def fake_uv(self, python=None):
        """A stand-in uv that records what it was asked and answers like the
        real one."""
        found = 'echo "%s"' % python if python else "exit 2"
        return self.shim("uv", (
            'echo "uv $*" >> "%s"\n'
            'case "$*" in\n'
            '  "--version") echo "uv 0.0.0" ;;\n'
            '  "python install 3.12") exit 0 ;;\n'
            '  "python find 3.12") %s ;;\n'
            '  *) exit 64 ;;\n'
            'esac'
        ) % (self.root / "uv.log", found))

    def fake_python(self, proof_exit=0):
        """A stand-in interpreter: answers the proof, records anything else."""
        return self.shim("python3.12", (
            'if [ "$1" = "-c" ]; then echo "3.12.0 (stand-in)"; exit %d; fi\n'
            'echo "$*" >> "%s"\n'
            'echo \'{"ran": "nc_setup"}\''
        ) % (proof_exit, self.root / "python.log"))

    def run_sh(self, *args):
        env = {"PATH": "%s:%s" % (self.shims, BASE_PATH), "HOME": str(self.home),
               "NC_TOOLS_DIR": str(self.root / "tools")}
        return subprocess.run(
            ["bash", str(BOOTSTRAP_SH), *args], env=env, capture_output=True, text=True,
            stdin=subprocess.DEVNULL, timeout=120,
        )

    def last_line(self, result):
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertTrue(lines, result.stderr)
        self.assertRegex(lines[-1], LAST_LINE)
        return lines[-1]

    def require_no_real_uv(self):
        if shutil.which("uv", path=BASE_PATH):
            self.skipTest("this machine has uv in a system folder")

    # -- dry run: decisions only ---------------------------------------------

    def test_dry_run_without_uv_decides_to_install_it(self):
        self.require_no_real_uv()
        before = snapshot(self.root)
        result = self.run_sh("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bootstrap: would run: " + UV_INSTALL, result.stderr)
        self.assertIn("python install 3.12", result.stderr)
        self.assertEqual(self.last_line(result), "BOOTSTRAP=OK python=dry-run")
        self.assertEqual(snapshot(self.root), before)

    def test_dry_run_with_uv_skips_installing_it(self):
        uv = self.fake_uv()
        result = self.run_sh("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(UV_INSTALL, result.stderr)
        self.assertIn("bootstrap: uv is already here: %s" % uv, result.stderr)
        self.assertIn("bootstrap: would run: %s python install 3.12" % uv, result.stderr)
        self.assertRegex(self.last_line(result), r"^BOOTSTRAP=OK python=")

    def test_dry_run_finds_uv_in_the_per_user_folder(self):
        self.require_no_real_uv()
        local = self.home / ".local" / "bin"
        local.mkdir(parents=True)
        uv = local / "uv"
        uv.write_text("#!/bin/sh\nexit 0\n")
        uv.chmod(0o755)
        result = self.run_sh("--dry-run")
        self.assertNotIn(UV_INSTALL, result.stderr)
        self.assertIn("bootstrap: uv is already here: %s" % uv, result.stderr)

    def test_an_old_python3_on_path_is_never_trusted(self):
        marker = self.root / "python3-was-run"
        self.shim("python3", 'touch "%s"; echo "Python 3.9.6"' % marker)
        self.shim("python", 'touch "%s"; echo "Python 3.9.6"' % marker)
        uv = self.fake_uv()
        result = self.run_sh("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bootstrap: would run: %s python install 3.12" % uv, result.stderr)
        self.assertFalse(marker.exists(), "bootstrap ran the python3 on PATH")

    def test_dry_run_changes_nothing_and_does_not_start_the_install_script(self):
        self.fake_uv(python=self.fake_python())
        (self.root / "uv.log").write_text("")
        before = snapshot(self.root)
        result = self.run_sh("--dry-run", "plan", "--project", "/some/where")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("would run: nc_setup.py plan --project /some/where", result.stderr)
        self.assertFalse((self.root / "python.log").exists())
        self.assertNotIn("python install", (self.root / "uv.log").read_text())
        after = snapshot(self.root)
        after.pop("uv.log"), before.pop("uv.log")   # the stand-in's own notebook
        self.assertEqual(after, before)

    # -- the last line ---------------------------------------------------------

    def test_last_line_is_always_one_of_the_three_forms(self):
        self.require_no_real_uv()
        self.last_line(self.run_sh("--dry-run"))                  # OK, uv missing
        self.fake_uv(python=self.fake_python())
        self.last_line(self.run_sh("--dry-run"))                  # OK, uv present
        self.assertEqual(self.last_line(self.run_sh()), "BOOTSTRAP=OK python=%s" % (self.shims / "python3.12"))
        self.fake_python(proof_exit=1)
        self.assertRegex(self.last_line(self.run_sh()), r"^BOOTSTRAP=NEEDS_YOU reason=")
        self.shim("git", "exit 1")
        self.assertRegex(self.last_line(self.run_sh("--dry-run")), r"^BOOTSTRAP=NEEDS_YOU reason=")

    def test_progress_lines_carry_the_prefix_and_stay_off_stdout(self):
        self.fake_uv(python=self.fake_python())
        result = self.run_sh()
        self.assertEqual(result.stdout.strip().splitlines(), ["BOOTSTRAP=OK python=%s" % (self.shims / "python3.12")])
        progress = [line for line in result.stderr.splitlines() if line.strip()]
        self.assertTrue(progress)
        for line in progress:
            self.assertTrue(line.startswith("bootstrap: "), line)

    # -- real runs against stand-ins --------------------------------------------

    def test_git_that_does_not_run_stops_with_needs_you(self):
        self.shim("git", "exit 1")
        self.shim("xcode-select", "exit 2")
        result = self.run_sh()
        self.assertEqual(result.returncode, 3)
        line = self.last_line(result)
        self.assertTrue(line.startswith("BOOTSTRAP=NEEDS_YOU reason="))
        if sys.platform == "darwin":
            self.assertIn("xcode-select --install", line)
        self.assertFalse((self.root / "uv.log").exists())

    def test_real_run_installs_python_through_uv_then_proves_it(self):
        python = self.fake_python()
        self.fake_uv(python=python)
        result = self.run_sh()
        self.assertEqual(result.returncode, 0, result.stderr)
        log = (self.root / "uv.log").read_text().splitlines()
        self.assertEqual(log, ["uv python install 3.12", "uv python find 3.12"])
        self.assertEqual(self.last_line(result), "BOOTSTRAP=OK python=%s" % python)
        self.assertFalse((self.root / "python.log").exists())   # no arguments: the install script is not started

    def test_arguments_are_passed_through_to_the_install_script(self):
        python = self.fake_python()
        self.fake_uv(python=python)
        result = self.run_sh("plan", "--project", "/some/where with space")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.root / "python.log").read_text().strip(),
            "%s plan --project /some/where with space" % (INSTALLER / "nc_setup.py"),
        )
        lines = result.stdout.strip().splitlines()
        self.assertEqual(lines[0], "BOOTSTRAP=OK python=%s" % python)
        self.assertEqual(lines[1:], ['{"ran": "nc_setup"}'])

    def test_a_python_that_fails_its_proof_is_needs_you(self):
        self.fake_uv(python=self.fake_python(proof_exit=1))
        result = self.run_sh("plan", "--project", "/x")
        self.assertEqual(result.returncode, 3)
        self.assertTrue(self.last_line(result).startswith("BOOTSTRAP=NEEDS_YOU reason="))
        self.assertFalse((self.root / "python.log").exists())

    def test_a_uv_install_that_leaves_no_uv_is_needs_you(self):
        self.require_no_real_uv()
        self.shim("curl", "exit 22")
        result = self.run_sh()
        self.assertEqual(result.returncode, 3)
        self.assertIn("uv", self.last_line(result))

    @unittest.skipUnless(sys.platform == "darwin", "only macOS kills an unsigned interpreter on launch")
    def test_a_python_killed_on_launch_is_signed_once_and_tried_again(self):
        signed = self.root / "signed"
        python = self.shim("python3.12", (
            'if [ ! -f "%s" ]; then kill -9 $$; fi\n'
            'echo "3.12.0 (stand-in)"'
        ) % signed)
        self.shim("codesign", 'echo "codesign $*" >> "%s"; touch "%s"' % (self.root / "codesign.log", signed))
        self.fake_uv(python=python)
        result = self.run_sh()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "codesign.log").read_text().strip(), "codesign --force -s - %s" % python)
        self.assertEqual(self.last_line(result), "BOOTSTRAP=OK python=%s" % python)

    def test_uv_that_cannot_say_where_python_is_stops(self):
        self.fake_uv(python=None)
        result = self.run_sh()
        self.assertEqual(result.returncode, 3)
        self.assertTrue(self.last_line(result).startswith("BOOTSTRAP=NEEDS_YOU reason="))


@unittest.skipIf(WINDOWS, "shellcheck runs where bootstrap.sh runs")
class ShLint(unittest.TestCase):
    @unittest.skipUnless(shutil.which("shellcheck"), "shellcheck is not installed")
    def test_shellcheck_is_clean(self):
        result = subprocess.run(["shellcheck", str(BOOTSTRAP_SH)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_it_runs_under_the_bash_a_mac_ships_with(self):
        text = BOOTSTRAP_SH.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#!/usr/bin/env bash\n"))
        for newer in ("declare -A", "mapfile", "readarray", "${!", "&>>", "|&"):
            self.assertNotIn(newer, text)


class Ps1Text(unittest.TestCase):
    """Runs everywhere: the script must stay inside what Windows PowerShell
    5.1 can read."""

    @classmethod
    def setUpClass(cls):
        cls.raw = BOOTSTRAP_PS1.read_bytes()
        cls.text = cls.raw.decode("utf-8")

    def test_exists_and_is_not_empty(self):
        self.assertGreater(len(self.text.strip()), 200)

    def test_is_plain_ascii(self):
        # Windows PowerShell 5.1 reads a file with no byte-order mark in the
        # system code page, so anything beyond ASCII can change meaning.
        self.assertTrue(self.raw.isascii())

    def test_has_no_syntax_newer_than_5_1(self):
        for newer in ("&&", "||", "??", "?.", "-Parallel", "ForEach-Object -Parallel"):
            self.assertNotIn(newer, self.text)
        # No ternary: the script contains no question mark at all.
        self.assertNotIn("?", self.text)

    def test_carries_the_three_last_line_forms_and_exit_codes(self):
        for needle in ("BOOTSTRAP=OK python=", "BOOTSTRAP=NEEDS_RESTART reason=", "BOOTSTRAP=NEEDS_YOU reason=",
                       "exit 3", "exit 4"):
            self.assertIn(needle, self.text)

    def test_names_the_exact_commands(self):
        for needle in (
            "winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements",
            "irm https://astral.sh/uv/install.ps1 | iex",
            "python install 3.12",
            "python find 3.12",
            "import sys, tomllib, sqlite3, venv; print(sys.version)",
        ):
            self.assertIn(needle, self.text)

    def test_every_sentence_that_asks_for_a_restart_says_to_close_the_terminal_window_too(self):
        self.assertIn("'%s'" % RESTART_AFTER_INSTALL, self.text)
        self.assertIn("'%s'" % RESTART_STALE_SESSION, self.text)
        asking = [line for line in self.text.splitlines() if "lose Claude Code completely" in line]
        self.assertEqual(len(asking), 3)   # the two above, and Git that has to be installed by hand
        for line in asking:
            self.assertIn("close that window too", line)

    def test_output_is_set_to_utf8_before_anything_else_runs(self):
        # A Windows account name with an accent otherwise arrives garbled in
        # the python= path. A session with no console cannot have its
        # encoding set, and must not fail on that: hence the try.
        code = "\n".join(
            line for line in self.text.splitlines() if line.strip() and not line.lstrip().startswith("#")
        )
        after_param = code.split("param([switch]$DryRun)\n", 1)[1]
        block = re.match(r"try \{\n(.*?)\n\} catch \{ ?\}\n", after_param, re.S)
        self.assertIsNotNone(block, after_param[:120])
        for target in ("$OutputEncoding = ", "[Console]::OutputEncoding = "):
            with self.subTest(target=target):
                self.assertIn(target, block.group(1))
        self.assertIn("UTF8Encoding", block.group(1))

    def test_the_python_path_is_printed_with_forward_slashes_and_used_unchanged(self):
        self.assertIn("""Write-Output "BOOTSTRAP=OK python=$($python.Replace('\\', '/'))\"""", self.text)
        self.assertNotIn('"BOOTSTRAP=OK python=$python"', self.text)
        for use in ("& $python -c $Proof", "& $python (Join-Path $PSScriptRoot 'nc_setup.py') @SetupArgs"):
            with self.subTest(use=use):
                self.assertIn(use, self.text)

    def test_a_failed_uv_install_names_antivirus_and_where_to_get_uv_by_hand(self):
        reasons = [line for line in self.text.splitlines() if "uv could not be installed" in line]
        self.assertEqual(len(reasons), 1)
        for needle in ("Check the internet connection", "antivirus", "https://docs.astral.sh/uv/",
                       "before pasting the message again."):
            with self.subTest(needle=needle):
                self.assertIn(needle, reasons[0])


def run_powershell(*args, env, creationflags=0):
    """Windows PowerShell on bootstrap.ps1, its output read as UTF-8."""
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BOOTSTRAP_PS1), *args],
        env=env, capture_output=True, encoding="utf-8", errors="replace",
        stdin=subprocess.DEVNULL, timeout=120, creationflags=creationflags,
    )


@unittest.skipUnless(WINDOWS, "bootstrap.ps1 is the Windows first step")
class Ps1DryRun(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name).resolve()
        self.empty = self.root / "empty"
        self.empty.mkdir()
        self.profile = self.root / "profile"
        self.profile.mkdir()

    def path_without_git(self):
        """This machine's PATH minus every folder that holds git.exe, and
        minus every folder that holds a bash.exe other than Windows' own."""
        kept = []
        for folder in os.environ.get("PATH", "").split(os.pathsep):
            if not folder:
                continue
            here = Path(folder)
            if (here / "git.exe").is_file():
                continue
            if (here / "bash.exe").is_file() and "system32" not in folder.lower():
                continue
            kept.append(folder)
        return os.pathsep.join(kept)

    def run_ps(self, path=None, program_files=None, persisted_path=None, creationflags=0):
        env = dict(os.environ)
        if path is not None:
            env["PATH"] = path
        folder = str(program_files or self.empty)
        env.update({
            "ProgramFiles": folder, "ProgramW6432": folder, "ProgramFiles(x86)": folder,
            "LOCALAPPDATA": str(self.empty), "USERPROFILE": str(self.profile),
        })
        env.pop("XDG_BIN_HOME", None)
        env.pop("NC_PERSISTED_PATH", None)
        if persisted_path:
            env["NC_PERSISTED_PATH"] = persisted_path
        result = run_powershell("-DryRun", env=env, creationflags=creationflags)
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertTrue(lines, result.stderr)
        self.assertRegex(lines[-1], LAST_LINE)
        return result, lines[-1]

    def test_git_hidden_from_path_decides_to_install_it_and_ends_needs_restart(self):
        result, last = self.run_ps(path=self.path_without_git())
        self.assertEqual(result.returncode, 4, result.stdout)
        self.assertIn("Git", result.stdout)
        self.assertRegex(result.stdout, r"bootstrap: would (run: winget install --id Git\.Git|download)")
        self.assertEqual(last, "BOOTSTRAP=NEEDS_RESTART reason=" + RESTART_AFTER_INSTALL)

    def test_bash_under_system32_with_no_git_is_no_git(self):
        stub = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "bash.exe"
        if not stub.is_file():
            self.skipTest("this Windows has no System32 bash.exe")
        path = self.path_without_git()
        self.assertIn("system32", shutil.which("bash", path=path).lower())
        result, last = self.run_ps(path=path)
        self.assertEqual(result.returncode, 4, result.stdout)
        self.assertNotIn("Git is already here", result.stdout)
        self.assertTrue(last.startswith("BOOTSTRAP=NEEDS_RESTART reason="))

    def test_git_present_is_skipped(self):
        if not shutil.which("git"):
            self.skipTest("this machine has no Git")
        result, last = self.run_ps()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("bootstrap: Git is already here", result.stdout)
        self.assertNotIn("winget install", result.stdout)
        self.assertTrue(last.startswith("BOOTSTRAP=OK python="))

    def fake_git_install(self, under=None):
        root = (under or self.root) / "ProgramFiles"
        (root / "Git" / "cmd").mkdir(parents=True)
        (root / "Git" / "bin").mkdir(parents=True)
        (root / "Git" / "cmd" / "git.exe").write_bytes(b"")
        (root / "Git" / "bin" / "bash.exe").write_bytes(b"")
        return root

    def test_git_installed_but_not_yet_visible_asks_for_a_restart_without_reinstalling(self):
        root = self.fake_git_install()
        result, last = self.run_ps(
            path=self.path_without_git(), program_files=root,
            persisted_path=str(root / "Git" / "cmd"),
        )
        self.assertEqual(result.returncode, 4, result.stdout)
        self.assertNotIn("winget install", result.stdout)
        self.assertEqual(last, "BOOTSTRAP=NEEDS_RESTART reason=" + RESTART_STALE_SESSION)

    def test_git_installed_but_never_on_path_is_used_where_it_is(self):
        root = self.fake_git_install()
        result, last = self.run_ps(path=self.path_without_git(), program_files=root)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("winget install", result.stdout)
        self.assertIn("bootstrap: Git is already here", result.stdout)
        self.assertTrue(last.startswith("BOOTSTRAP=OK python="))

    def test_a_folder_name_with_an_accent_is_printed_as_utf8(self):
        root = self.fake_git_install(under=self.root / "José")
        result, last = self.run_ps(path=self.path_without_git(), program_files=root)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("bootstrap: Git is already here: %s (" % (root / "Git" / "cmd" / "git.exe"), result.stdout)

    def test_a_session_with_no_console_still_ends_with_its_last_line(self):
        # There is no console whose encoding could be set. That must cost
        # nothing: no error on the way, and the last line as always.
        if not shutil.which("git"):
            self.skipTest("this machine has no Git")
        result, last = self.run_ps(creationflags=subprocess.DETACHED_PROCESS)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr.strip(), "")
        self.assertTrue(last.startswith("BOOTSTRAP=OK python="))


# What uv does, as far as bootstrap.ps1 asks: it prints the path of the
# Python it found as UTF-8, which is what the real one writes to a pipe.
UV_STAND_IN = '''\
import sys
args = sys.argv[1:]
with open(%r, "a", encoding="utf-8") as log:
    log.write(" ".join(args) + "\\n")
if args == ["python", "install", "3.12"]:
    sys.exit(0)
if args == ["python", "find", "3.12"]:
    sys.stdout.buffer.write((%r + "\\n").encode("utf-8"))
    sys.exit(0)
sys.exit(64)
'''


@unittest.skipUnless(WINDOWS, "bootstrap.ps1 is the Windows first step")
class Ps1RealRun(unittest.TestCase):
    """bootstrap.ps1 run for real on Windows PowerShell, through to its last
    line, against a stand-in uv, so nothing is installed. The Python that uv
    "finds" is a real one under a folder with an accent in its name, the way
    a Windows account name can have one."""

    def setUp(self):
        if not shutil.which("git"):
            self.skipTest("this machine has no Git")
        self._td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name).resolve()
        self.shims = self.root / "shims"
        self.shims.mkdir()
        home = self.root / "José"
        venv.create(home / "python", with_pip=False)
        self.python = home / "python" / "Scripts" / "python.exe"
        self.log = self.root / "uv.log"
        (self.shims / "uv_stand_in.py").write_text(
            UV_STAND_IN % (str(self.log), str(self.python)), encoding="utf-8")
        (self.shims / "uv.cmd").write_text(
            '@echo off\n"%s" "%%~dp0uv_stand_in.py" %%*\nexit /b %%ERRORLEVEL%%\n' % sys.executable,
            encoding="ascii", newline="\r\n")

    def test_a_python_under_a_folder_with_an_accent_is_found_proven_and_printed_with_forward_slashes(self):
        self.assertTrue(self.python.is_file())
        env = dict(os.environ)
        env["PATH"] = str(self.shims) + os.pathsep + env.get("PATH", "")
        env.pop("XDG_BIN_HOME", None)
        result = run_powershell(env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8").splitlines(),
                         ["python install 3.12", "python find 3.12"])
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(lines[-1], "BOOTSTRAP=OK python=" + str(self.python).replace("\\", "/"))
        self.assertIn("bootstrap: Python is ready: %s" % sys.version.split()[0], result.stdout)


if __name__ == "__main__":
    unittest.main()
