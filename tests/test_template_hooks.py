"""Unit tests for the technical-cofounder starter workspace: init_workspace.py
and the guardrail hooks under plugins/base-novacaelum/hooks/.

Standard library only.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "base-novacaelum"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
BIN_DIR = PLUGIN_ROOT / "bin"
TEMPLATE_DIR = PLUGIN_ROOT / "template"

FIVE_RULES = {
    "frame-discipline.md",
    "anti-hallucination.md",
    "act-and-disclose.md",
    "eliminate-first.md",
    "anti-truncation.md",
}


def init_into(target):
    return subprocess.run(
        ["python3", str(BIN_DIR / "init_workspace.py"), str(target)],
        capture_output=True, text=True,
    )


def run_hook(name, payload, env_extra=None, raw_input=None):
    env = os.environ.copy()
    env.pop("TC_CONCISION", None)
    if env_extra:
        env.update(env_extra)
    stdin_text = raw_input if raw_input is not None else json.dumps(payload)
    return subprocess.run(
        ["bash", str(HOOKS_DIR / name)],
        input=stdin_text,
        capture_output=True, text=True, env=env,
    )


class InitWorkspaceTests(unittest.TestCase):
    def test_copies_into_empty_project(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            r = init_into(target)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((target / "CLAUDE.md").is_file())
            self.assertTrue((target / "user.md").is_file())
            self.assertTrue((target / "worklog" / "README.md").is_file())
            rules_dir = target / ".claude" / "rules"
            present = {p.name for p in rules_dir.glob("*.md")}
            self.assertEqual(present, FIVE_RULES)
            self.assertIn("COPIED: CLAUDE.md", r.stdout)

    def test_never_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            marker = "# pre-existing project CLAUDE.md — do not touch\n"
            (target / "CLAUDE.md").write_text(marker)
            r = init_into(target)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((target / "CLAUDE.md").read_text(), marker)
            self.assertIn("SKIPPED: CLAUDE.md", r.stdout)
            self.assertNotIn("COPIED: CLAUDE.md", r.stdout)
            # everything else still lands
            self.assertTrue((target / "user.md").is_file())

    def test_second_run_is_fully_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            init_into(target)
            r2 = init_into(target)
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertNotIn("COPIED:", r2.stdout)
            self.assertIn("SKIPPED: CLAUDE.md", r2.stdout)

    def test_bad_usage_exits_nonzero(self):
        r = subprocess.run(["python3", str(BIN_DIR / "init_workspace.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


class RulesPackTests(unittest.TestCase):
    def test_five_rules_present_with_source_and_license(self):
        rules_dir = TEMPLATE_DIR / ".claude" / "rules"
        present = {p.name for p in rules_dir.glob("*.md")}
        self.assertEqual(present, FIVE_RULES)
        for name in FIVE_RULES:
            text = (rules_dir / name).read_text()
            self.assertIn("Source:", text, name)
            self.assertIn("License: MIT", text, name)

    def test_no_owner_or_internal_system_references(self):
        # Light guard, layered on top of scripts/leak-scan.py --tree: these
        # rules must read as standalone, not as excerpts of a private system.
        # Built from fragments (like scripts/leak-scan.py's own PATTERNS) so
        # this test file never contains the literal blocked strings and
        # passes its own leak scan.
        blocked = [
            "Dan" + "iel",
            "Agent" + "Secret" + "Base",
            "NovaCaelum" + "_Obs",
            "_agent" + "OS",
            "Task" + " Graph",
            "agent" + "_registry",
        ]
        rules_dir = TEMPLATE_DIR / ".claude" / "rules"
        for name in FIVE_RULES:
            text = (rules_dir / name).read_text()
            for term in blocked:
                self.assertNotIn(term, text, f"{name} contains blocked term {term!r}")


class HookSampleAndMalformedInputTests(unittest.TestCase):
    """Every hook exits 0 on a realistic sample payload and on malformed
    stdin. concision-stop.sh's deliberate block path is covered separately
    below (it also exits 0, but the meaningful assertion is the block
    decision it produces, not just the exit code)."""

    SAMPLES = {
        "session-preload.sh": {"session_id": "sess-1", "hook_event_name": "SessionStart", "source": "startup"},
        "concision-budget.sh": {"session_id": "sess-1", "hook_event_name": "UserPromptSubmit", "prompt": "quick check: is the server up?"},
        "concision-contract.sh": {"session_id": "sess-1", "hook_event_name": "UserPromptSubmit", "prompt": "walk me through the plan"},
        "concision-stop.sh": {"session_id": "sess-1", "hook_event_name": "Stop", "last_assistant_message": "Done.", "stop_hook_active": False},
        "circuit-breaker.sh": {"session_id": "sess-1", "hook_event_name": "PreToolUse", "tool_name": "Bash"},
    }

    def test_sample_payload_exits_0(self):
        for name, payload in self.SAMPLES.items():
            with self.subTest(hook=name):
                r = run_hook(name, payload)
                self.assertEqual(r.returncode, 0, f"{name} stderr: {r.stderr}")

    def test_malformed_stdin_exits_0(self):
        for name in self.SAMPLES:
            with self.subTest(hook=name):
                r = run_hook(name, None, raw_input="{not json")
                self.assertEqual(r.returncode, 0, f"{name} stderr: {r.stderr}")

    def test_empty_stdin_exits_0(self):
        for name in self.SAMPLES:
            with self.subTest(hook=name):
                r = run_hook(name, None, raw_input="")
                self.assertEqual(r.returncode, 0, f"{name} stderr: {r.stderr}")

    def test_tc_concision_off_disables_the_trio(self):
        for name in ("concision-budget.sh", "concision-contract.sh", "concision-stop.sh"):
            with self.subTest(hook=name):
                r = run_hook(name, self.SAMPLES[name], env_extra={"TC_CONCISION": "off"})
                self.assertEqual(r.returncode, 0)
                self.assertEqual(r.stdout.strip(), "")


class ConcisionBudgetBandTests(unittest.TestCase):
    def test_brief_marker_gives_120_band(self):
        r = run_hook("concision-budget.sh", {"session_id": str(uuid.uuid4()), "hook_event_name": "UserPromptSubmit", "prompt": "quick check on the build"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("<=120 words", r.stdout)

    def test_depth_marker_gives_650_band(self):
        r = run_hook("concision-budget.sh", {"session_id": str(uuid.uuid4()), "hook_event_name": "UserPromptSubmit", "prompt": "walk me through the whole plan"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("<=650 words", r.stdout)

    def test_plain_prompt_gives_default_300_band(self):
        r = run_hook("concision-budget.sh", {"session_id": str(uuid.uuid4()), "hook_event_name": "UserPromptSubmit", "prompt": "add a retry to the upload function"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("<=300 words", r.stdout)


class ConcisionStopBlockPathTests(unittest.TestCase):
    def test_over_700_words_blocks(self):
        payload = {
            "session_id": str(uuid.uuid4()),
            "hook_event_name": "Stop",
            "last_assistant_message": " ".join(["word"] * 800),
            "stop_hook_active": False,
        }
        r = run_hook("concision-stop.sh", payload)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"decision":"block"', r.stdout.replace(" ", ""))

    def test_short_response_does_not_block(self):
        payload = {
            "session_id": str(uuid.uuid4()),
            "hook_event_name": "Stop",
            "last_assistant_message": "Done, see the file.",
            "stop_hook_active": False,
        }
        r = run_hook("concision-stop.sh", payload)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('"decision":"block"', r.stdout.replace(" ", ""))

    def test_stop_hook_active_suppresses_block_on_retry(self):
        payload = {
            "session_id": str(uuid.uuid4()),
            "hook_event_name": "Stop",
            "last_assistant_message": " ".join(["word"] * 800),
            "stop_hook_active": True,
        }
        r = run_hook("concision-stop.sh", payload)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('"decision":"block"', r.stdout.replace(" ", ""))


class CircuitBreakerTests(unittest.TestCase):
    """Controller finding: an earlier version keyed blocking on PreToolUse
    ATTEMPT counts, which false-fired on ordinary parallel tool dispatch
    (N PreToolUse events land before any PostToolUse, because the calls run
    concurrently). This version counts only real failures
    (PostToolUseFailure), so these two behaviors must both hold."""

    def _isolated_env(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        env = os.environ.copy()
        env["TMPDIR"] = tmp
        return tmp, env

    def test_parallel_pretooluse_then_all_successes_never_blocks(self):
        tmp, env = self._isolated_env()
        session_id = str(uuid.uuid4())
        # Simulate N tool calls dispatched in parallel: every PreToolUse
        # fires before any PostToolUse lands, exactly like concurrent
        # dispatch does. None of them may increment a failure counter or
        # block, because nothing has failed.
        for _ in range(5):
            r = run_hook("circuit-breaker.sh", {"session_id": session_id, "hook_event_name": "PreToolUse", "tool_name": "Bash"}, env_extra=env)
            self.assertEqual(r.returncode, 0, r.stderr)
        for _ in range(5):
            r = run_hook("circuit-breaker.sh", {"session_id": session_id, "hook_event_name": "PostToolUse", "tool_name": "Bash"}, env_extra=env)
            self.assertEqual(r.returncode, 0, r.stderr)
        # A further attempt after all that concurrent success must still
        # not be blocked.
        r = run_hook("circuit-breaker.sh", {"session_id": session_id, "hook_event_name": "PreToolUse", "tool_name": "Bash"}, env_extra=env)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_five_identical_failures_block_the_next_attempt(self):
        tmp, env = self._isolated_env()
        session_id = str(uuid.uuid4())
        for _ in range(5):
            r = run_hook(
                "circuit-breaker.sh",
                {"session_id": session_id, "hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "error": "command not found: frobnicate"},
                env_extra=env,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
        r = run_hook("circuit-breaker.sh", {"session_id": session_id, "hook_event_name": "PreToolUse", "tool_name": "Bash"}, env_extra=env)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("BLOCKED", r.stderr)

    def test_a_success_resets_the_failure_streak(self):
        tmp, env = self._isolated_env()
        session_id = str(uuid.uuid4())
        for _ in range(4):
            run_hook(
                "circuit-breaker.sh",
                {"session_id": session_id, "hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "error": "command not found: frobnicate"},
                env_extra=env,
            )
        # success resets the streak before it reaches the threshold
        run_hook("circuit-breaker.sh", {"session_id": session_id, "hook_event_name": "PostToolUse", "tool_name": "Bash"}, env_extra=env)
        run_hook(
            "circuit-breaker.sh",
            {"session_id": session_id, "hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "error": "command not found: frobnicate"},
            env_extra=env,
        )
        r = run_hook("circuit-breaker.sh", {"session_id": session_id, "hook_event_name": "PreToolUse", "tool_name": "Bash"}, env_extra=env)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_no_session_id_never_blocks(self):
        tmp, env = self._isolated_env()
        for _ in range(6):
            run_hook(
                "circuit-breaker.sh",
                {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "error": "command not found: frobnicate"},
                env_extra=env,
            )
        r = run_hook("circuit-breaker.sh", {"hook_event_name": "PreToolUse", "tool_name": "Bash"}, env_extra=env)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
