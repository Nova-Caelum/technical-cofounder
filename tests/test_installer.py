"""Unit tests for the setup installer's branch behavior:
plugins/base-novacaelum/bin/init_workspace.py's --obsidian/--no-obsidian
and --super/--no-super flags, and its no-overwrite guarantee across every
combination.

Standard library only.
"""
import itertools
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "base-novacaelum"
BIN_DIR = PLUGIN_ROOT / "bin"
SCRIPT = BIN_DIR / "init_workspace.py"

FIVE_RULES = {
    "frame-discipline.md",
    "anti-hallucination.md",
    "act-and-disclose.md",
    "eliminate-first.md",
    "anti-truncation.md",
}

SUPER_INSTALL_CMD = "claude plugin install super-novacaelum@technical-cofounder --scope project"
BRANCHES = list(itertools.product([True, False], repeat=2))  # (obsidian, super)


def run_init(target, obsidian, super_, extra_args=None):
    args = [
        "python3", str(SCRIPT), str(target),
        "--obsidian" if obsidian else "--no-obsidian",
        "--super" if super_ else "--no-super",
    ]
    if extra_args:
        args.extend(extra_args)
    return subprocess.run(args, capture_output=True, text=True, stdin=subprocess.DEVNULL)


class FourBranchTests(unittest.TestCase):
    """Every combination of --obsidian|--no-obsidian x --super|--no-super
    produces its expected result, scripted as a dry run into an empty temp
    project."""

    def test_all_four_branches(self):
        for obsidian, super_ in BRANCHES:
            with self.subTest(obsidian=obsidian, super_=super_):
                with tempfile.TemporaryDirectory() as td:
                    target = Path(td)
                    r = run_init(target, obsidian, super_)
                    self.assertEqual(r.returncode, 0, r.stderr)

                    # base files always land
                    self.assertTrue((target / "CLAUDE.md").is_file())
                    self.assertTrue((target / "user.md").is_file())
                    self.assertTrue((target / "worklog" / "README.md").is_file())
                    rules_dir = target / ".claude" / "rules"
                    present = {p.name for p in rules_dir.glob("*.md")}
                    self.assertEqual(present, FIVE_RULES)

                    obsidian_dir = target / ".obsidian"
                    worklog_base = target / "worklog" / "worklog.base"
                    if obsidian:
                        self.assertTrue(obsidian_dir.is_dir())
                        self.assertTrue((obsidian_dir / "core-plugins.json").is_file())
                        self.assertTrue((obsidian_dir / "community-plugins.json").is_file())
                        self.assertTrue(worklog_base.is_file())
                    else:
                        self.assertFalse(obsidian_dir.exists())
                        self.assertFalse(worklog_base.exists())

                    if super_:
                        self.assertIn(SUPER_INSTALL_CMD, r.stdout)
                        self.assertIn("super-setup", r.stdout)
                    else:
                        self.assertNotIn(SUPER_INSTALL_CMD, r.stdout)
                        self.assertNotIn("super-setup", r.stdout)

                    self.assertIn(
                        f"INIT_SUMMARY obsidian={str(obsidian).lower()} super={str(super_).lower()}",
                        r.stdout,
                    )

    def test_super_command_carries_scope_project(self):
        with tempfile.TemporaryDirectory() as td:
            r = run_init(Path(td), obsidian=False, super_=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("--scope project", r.stdout)


class NoOverwriteAcrossBranchesTests(unittest.TestCase):
    """A project that already has files keeps them, on every branch."""

    def test_pre_existing_claude_md_kept_on_every_branch(self):
        for obsidian, super_ in BRANCHES:
            with self.subTest(obsidian=obsidian, super_=super_):
                with tempfile.TemporaryDirectory() as td:
                    target = Path(td)
                    marker = "# pre-existing project CLAUDE.md — do not touch\n"
                    (target / "CLAUDE.md").write_text(marker)
                    r = run_init(target, obsidian, super_)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertEqual((target / "CLAUDE.md").read_text(), marker)
                    self.assertIn("SKIPPED: CLAUDE.md", r.stdout)
                    self.assertNotIn("COPIED: CLAUDE.md", r.stdout)

    def test_second_run_same_branch_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            run_init(target, obsidian=True, super_=False)
            r2 = run_init(target, obsidian=True, super_=False)
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertNotIn("COPIED:", r2.stdout)
            self.assertIn("SKIPPED: CLAUDE.md", r2.stdout)


class NoFlagsNonInteractiveTests(unittest.TestCase):
    """A bare, non-interactive invocation (no flags, no tty) never blocks
    on input and defaults both switches to off."""

    def test_no_flags_non_tty_defaults_and_completes(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            r = subprocess.run(
                ["python3", str(SCRIPT), str(target)],
                capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=10,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("INIT_SUMMARY obsidian=false super=false", r.stdout)
            self.assertIn("DEFAULTED", r.stdout)
            self.assertFalse((target / ".obsidian").exists())

    def test_bad_usage_exits_nonzero(self):
        r = subprocess.run(["python3", str(SCRIPT)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
