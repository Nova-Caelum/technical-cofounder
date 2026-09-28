"""Unit tests for verifier.py (verifier-lite). Standard library only."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_DIR = REPO_ROOT / "plugins" / "base-novacaelum" / "mcp"
sys.path.insert(0, str(MCP_DIR))

import verifier  # noqa: E402


def _criterion(statement, verification):
    return {"statement": statement, "verification": verification}


class FileStateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_exists_pass(self):
        (self.root / "a.txt").write_text("x", encoding="utf-8")
        result = verifier.evaluate_criterion(
            self.root, _criterion("exists", {"kind": "file_state", "path": "a.txt", "assertion": "exists"}), []
        )
        self.assertEqual(result["result"], "pass")

    def test_exists_fail(self):
        result = verifier.evaluate_criterion(
            self.root, _criterion("exists", {"kind": "file_state", "path": "missing.txt", "assertion": "exists"}), []
        )
        self.assertEqual(result["result"], "fail")

    def test_not_exists_pass(self):
        result = verifier.evaluate_criterion(
            self.root, _criterion("gone", {"kind": "file_state", "path": "missing.txt", "assertion": "not_exists"}), []
        )
        self.assertEqual(result["result"], "pass")

    def test_contains_pass_and_fail(self):
        (self.root / "readme.md").write_text("## Install\nsteps", encoding="utf-8")
        passing = verifier.evaluate_criterion(
            self.root,
            _criterion(
                "has install",
                {"kind": "file_state", "path": "readme.md", "assertion": "contains", "expected": "## Install"},
            ),
            [],
        )
        failing = verifier.evaluate_criterion(
            self.root,
            _criterion(
                "has uninstall",
                {"kind": "file_state", "path": "readme.md", "assertion": "contains", "expected": "## Uninstall"},
            ),
            [],
        )
        self.assertEqual(passing["result"], "pass")
        self.assertEqual(failing["result"], "fail")

    def test_contains_missing_file_is_fail_not_uncertain(self):
        result = verifier.evaluate_criterion(
            self.root,
            _criterion("has x", {"kind": "file_state", "path": "missing.md", "assertion": "contains", "expected": "x"}),
            [],
        )
        self.assertEqual(result["result"], "fail")

    def test_modified_after_pass_and_fail(self):
        target = self.root / "log.txt"
        target.write_text("entry", encoding="utf-8")
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        passing = verifier.evaluate_criterion(
            self.root,
            _criterion("changed", {"kind": "file_state", "path": "log.txt", "assertion": "modified_after", "expected": past}),
            [],
        )
        failing = verifier.evaluate_criterion(
            self.root,
            _criterion("not yet", {"kind": "file_state", "path": "log.txt", "assertion": "modified_after", "expected": future}),
            [],
        )
        self.assertEqual(passing["result"], "pass")
        self.assertEqual(failing["result"], "fail")

    def test_modified_after_malformed_expected_is_uncertain(self):
        (self.root / "log.txt").write_text("entry", encoding="utf-8")
        result = verifier.evaluate_criterion(
            self.root,
            _criterion(
                "changed", {"kind": "file_state", "path": "log.txt", "assertion": "modified_after", "expected": "not-a-date"}
            ),
            [],
        )
        self.assertEqual(result["result"], "uncertain")

    def test_path_traversal_and_absolute_and_home_refused(self):
        for bad_path in ("../outside.txt", "/etc/passwd", "~/secrets.txt"):
            result = verifier.evaluate_criterion(
                self.root,
                _criterion("bad path", {"kind": "file_state", "path": bad_path, "assertion": "exists"}),
                [],
            )
            self.assertEqual(result["result"], "uncertain", bad_path)


class CommandCheckTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_tests_check_pass_and_fail(self):
        (self.root / "test_ok.py").write_text(
            "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        (self.root / "test_bad.py").write_text(
            "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_bad(self):\n        self.assertTrue(False)\n",
            encoding="utf-8",
        )
        passing = verifier.evaluate_criterion(
            self.root, _criterion("tests pass", {"kind": "command_check", "check_id": "tests", "target": "test_ok.py"}), []
        )
        failing = verifier.evaluate_criterion(
            self.root, _criterion("tests fail", {"kind": "command_check", "check_id": "tests", "target": "test_bad.py"}), []
        )
        self.assertEqual(passing["result"], "pass")
        self.assertEqual(failing["result"], "fail")

    def test_tests_check_runs_the_verifiers_own_python(self):
        # A `python3` that is not Python (the Windows Store placeholder) must not
        # decide the verdict: the tests run with the interpreter running the verifier.
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        placeholder = fake_bin / "python3"
        placeholder.write_text("#!/bin/sh\necho 'Python was not found' >&2\nexit 9\n", encoding="utf-8")
        placeholder.chmod(0o755)
        (self.root / "test_ok.py").write_text(
            "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        with mock.patch.dict(os.environ, {"PATH": str(fake_bin) + os.pathsep + os.environ.get("PATH", "")}):
            result = verifier.evaluate_criterion(
                self.root, _criterion("tests pass", {"kind": "command_check", "check_id": "tests", "target": "test_ok.py"}), []
            )
        self.assertEqual(result["result"], "pass", result.get("evidence"))

    def test_tests_check_target_traversal_refused(self):
        result = verifier.evaluate_criterion(
            self.root, _criterion("bad target", {"kind": "command_check", "check_id": "tests", "target": "../x.py"}), []
        )
        self.assertEqual(result["result"], "uncertain")

    def test_git_diff_nonempty(self):
        subprocess.run(["git", "init", "-q"], cwd=str(self.root), check=True)
        clean = verifier.evaluate_criterion(
            self.root, _criterion("changed", {"kind": "command_check", "check_id": "git_diff_nonempty"}), []
        )
        (self.root / "new.txt").write_text("x", encoding="utf-8")
        dirty = verifier.evaluate_criterion(
            self.root, _criterion("changed", {"kind": "command_check", "check_id": "git_diff_nonempty"}), []
        )
        self.assertEqual(clean["result"], "fail")
        self.assertEqual(dirty["result"], "pass")

    def test_git_diff_nonempty_outside_a_repo_is_uncertain(self):
        result = verifier.evaluate_criterion(
            self.root, _criterion("changed", {"kind": "command_check", "check_id": "git_diff_nonempty"}), []
        )
        self.assertEqual(result["result"], "uncertain")

    def test_allowlisted_custom_command(self):
        (self.root / "verify.commands.json").write_text(
            json.dumps(
                {
                    "ok": ["python3", "-c", "import sys; sys.exit(0)"],
                    "bad": ["python3", "-c", "import sys; sys.exit(1)"],
                }
            ),
            encoding="utf-8",
        )
        ok = verifier.evaluate_criterion(self.root, _criterion("ok", {"kind": "command_check", "check_id": "ok"}), [])
        bad = verifier.evaluate_criterion(self.root, _criterion("bad", {"kind": "command_check", "check_id": "bad"}), [])
        self.assertEqual(ok["result"], "pass")
        self.assertEqual(bad["result"], "fail")

    def test_unknown_check_id_is_uncertain(self):
        result = verifier.evaluate_criterion(
            self.root, _criterion("mystery", {"kind": "command_check", "check_id": "does-not-exist"}), []
        )
        self.assertEqual(result["result"], "uncertain")


class ManualTests(unittest.TestCase):
    def test_no_attestation_is_uncertain(self):
        result = verifier.evaluate_criterion(
            Path("."), _criterion("A reviewer approved the copy", {"kind": "manual", "instruction": "read and approve"}), []
        )
        self.assertEqual(result["result"], "uncertain")

    def test_mismatched_attestation_is_uncertain(self):
        result = verifier.evaluate_criterion(
            Path("."),
            _criterion("A reviewer approved the copy", {"kind": "manual", "instruction": "read and approve"}),
            [{"statement": "something else", "attested_by": "reviewer"}],
        )
        self.assertEqual(result["result"], "uncertain")

    def test_matching_attestation_passes(self):
        result = verifier.evaluate_criterion(
            Path("."),
            _criterion("A reviewer approved the copy", {"kind": "manual", "instruction": "read and approve"}),
            [{"statement": "A reviewer approved the copy", "attested_by": "reviewer"}],
        )
        self.assertEqual(result["result"], "pass")


class OverallAndVerdictTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_criteria(self, criteria, crit_id="sample"):
        path = self.root / "criteria.json"
        path.write_text(json.dumps({"id": crit_id, "criteria": criteria}), encoding="utf-8")
        return path

    def test_overall_pass_when_all_pass(self):
        (self.root / "a.txt").write_text("x", encoding="utf-8")
        path = self._write_criteria(
            [{"statement": "exists", "verification": {"kind": "file_state", "path": "a.txt", "assertion": "exists"}}]
        )
        verdict = verifier.run_verification(str(path), root=self.root)
        self.assertEqual(verdict["overall"], "pass")

    def test_overall_fail_when_any_fails(self):
        path = self._write_criteria(
            [
                {"statement": "exists", "verification": {"kind": "file_state", "path": "missing.txt", "assertion": "exists"}},
                {"statement": "manual", "verification": {"kind": "manual", "instruction": "approve"}},
            ]
        )
        verdict = verifier.run_verification(str(path), root=self.root)
        self.assertEqual(verdict["overall"], "fail")

    def test_overall_uncertain_when_mixed_pass_and_manual(self):
        (self.root / "a.txt").write_text("x", encoding="utf-8")
        path = self._write_criteria(
            [
                {"statement": "exists", "verification": {"kind": "file_state", "path": "a.txt", "assertion": "exists"}},
                {"statement": "manual", "verification": {"kind": "manual", "instruction": "approve"}},
            ]
        )
        verdict = verifier.run_verification(str(path), root=self.root)
        self.assertEqual(verdict["overall"], "uncertain")

    def test_verdict_written_to_disk(self):
        path = self._write_criteria([{"statement": "manual", "verification": {"kind": "manual", "instruction": "approve"}}])
        verdict = verifier.run_verification(str(path), root=self.root)
        verdict_files = list((self.root / "verdicts").glob(f"{verdict['id']}-*.json"))
        self.assertEqual(len(verdict_files), 1)
        on_disk = json.loads(verdict_files[0].read_text(encoding="utf-8"))
        self.assertEqual(on_disk["overall"], verdict["overall"])

    def test_unreadable_criteria_file_is_uncertain(self):
        verdict = verifier.run_verification(str(self.root / "does-not-exist.json"), root=self.root)
        self.assertEqual(verdict["overall"], "uncertain")


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _run_cli(self, criteria, attest=None):
        criteria_path = self.root / "criteria.json"
        criteria_path.write_text(json.dumps(criteria), encoding="utf-8")
        argv = ["python3", str(MCP_DIR / "verifier.py"), str(criteria_path), "--root", str(self.root)]
        if attest is not None:
            attest_path = self.root / "attest.json"
            attest_path.write_text(json.dumps(attest), encoding="utf-8")
            argv += ["--attest", str(attest_path)]
        return subprocess.run(argv, capture_output=True, text=True)

    def test_exit_0_on_pass(self):
        (self.root / "a.txt").write_text("x", encoding="utf-8")
        result = self._run_cli(
            {"id": "x", "criteria": [{"statement": "exists", "verification": {"kind": "file_state", "path": "a.txt", "assertion": "exists"}}]}
        )
        self.assertEqual(result.returncode, 0)

    def test_exit_1_on_fail(self):
        result = self._run_cli(
            {"id": "x", "criteria": [{"statement": "exists", "verification": {"kind": "file_state", "path": "missing.txt", "assertion": "exists"}}]}
        )
        self.assertEqual(result.returncode, 1)

    def test_exit_2_on_uncertain(self):
        result = self._run_cli(
            {"id": "x", "criteria": [{"statement": "manual", "verification": {"kind": "manual", "instruction": "approve"}}]}
        )
        self.assertEqual(result.returncode, 2)

    def test_attest_flag_passes(self):
        result = self._run_cli(
            {
                "id": "x",
                "criteria": [
                    {"statement": "A reviewer approved the copy", "verification": {"kind": "manual", "instruction": "approve"}}
                ],
            },
            attest=[{"statement": "A reviewer approved the copy", "attested_by": "reviewer"}],
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
