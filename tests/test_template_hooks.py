"""Unit tests for the technical-cofounder starter workspace: init_workspace.py
and the guardrail hooks under plugins/base-novacaelum/hooks/.

Standard library only.
"""
import json
import os
import re
import shutil
import subprocess
import sys
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


def _bash():
    """bash as Claude Code runs these hooks: Git Bash on Windows. Never the
    System32 bash.exe (WSL), which Windows' process search finds first."""
    if os.name != "nt":
        return "bash"
    git = shutil.which("git")
    for parent in Path(git).resolve().parents if git else ():
        if (parent / "bin" / "bash.exe").is_file():
            return str(parent / "bin" / "bash.exe")
    return "bash"


BASH = _bash()


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
        [BASH, (HOOKS_DIR / name).as_posix()],
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
            self.assertTrue((target / "core_text" / "user.md").is_file())
            self.assertTrue((target / "core_text" / "setup.json").is_file())
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
            self.assertTrue((target / "core_text" / "user.md").is_file())

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


STEP_IDS = [s["id"] for s in json.loads((PLUGIN_ROOT / "setup" / "steps.json").read_text(encoding="utf-8"))["steps"]]
SUPER_KEY = "super-novacaelum@technical-cofounder"


class SessionPreloadTests(unittest.TestCase):
    """session-preload.sh in a temp project, with HOME pinned to a temp dir so
    the machine's own ~/.claude/settings.json never leaks into a result."""

    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)

    def preload(self):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR")}
        env.update(CLAUDE_PROJECT_DIR=str(self.project), HOME=str(self.home))
        r = subprocess.run([BASH, (HOOKS_DIR / "session-preload.sh").as_posix()], input="{}", capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def write(self, rel, text, base=None):
        path = (base or self.project) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def settings(self, rel, enabled, base=None, **extra):
        self.write(rel, json.dumps({"enabledPlugins": enabled, **extra}), base)

    def record(self, done=(), choices=None):
        steps = {s: {"status": "done" if s in done else "pending", "at": None} for s in STEP_IDS}
        self.write("core_text/setup.json", json.dumps({"schema_version": 1, "steps": steps, "choices": choices or {}}))

    def stack(self, out):
        return dict(re.findall(r"(?m)^- (base-novacaelum|super-novacaelum|hyperspace-engine): (.+?)\s*$", out))

    def test_core_text_profile(self):
        self.write("core_text/user.md", "# core-profile-marker\n")
        out = self.preload()
        self.assertIn("core-profile-marker", out)
        self.assertIn("## Tech primer (live)", out)
        self.assertIn("/base-novacaelum:ask", out)

    def test_core_text_wins_over_legacy(self):
        self.write("core_text/user.md", "# core-profile-marker\n")
        self.write("user.md", "# legacy-profile-marker\n")
        out = self.preload()
        self.assertIn("core-profile-marker", out)
        self.assertNotIn("legacy-profile-marker", out)

    def test_legacy_root_profile_with_one_move_note(self):
        self.write("user.md", "# legacy-profile-marker\n")
        out = self.preload()
        self.assertIn("legacy-profile-marker", out)
        notes = [ln for ln in out.splitlines() if "core_text/" in ln and "move" in ln.lower()]
        self.assertEqual(len(notes), 1, out)
        self.assertIn("/base-novacaelum:ask", out)

    def test_no_profile_points_to_setup(self):
        out = self.preload()
        self.assertIn("/base-novacaelum:setup", out)
        self.assertIn("/base-novacaelum:ask", out)
        self.assertIn("## Tech primer (live)", out)

    def test_setup_progress_line(self):
        self.write("core_text/user.md", "# p\n")
        self.record(done=("guide", "prerequisites", "editor"))
        want = f'Setup: 3 of {len(STEP_IDS)} steps done — say "continue setup" to pick up where you left off.'
        self.assertIn(want, self.preload().splitlines())

    def test_no_progress_line_when_nothing_pending(self):
        self.write("core_text/user.md", "# p\n")
        self.record(done=STEP_IDS)
        self.assertFalse([ln for ln in self.preload().splitlines() if ln.startswith("Setup:")])

    def test_stack_defaults(self):
        self.assertEqual(self.stack(self.preload()), {
            "base-novacaelum": "present", "super-novacaelum": "not chosen", "hyperspace-engine": "not chosen"})

    def test_super_expected_but_missing(self):
        self.record(choices={"super": "yes"})
        self.assertEqual(self.stack(self.preload())["super-novacaelum"], "expected but missing")

    def test_super_present_at_each_scope(self):
        for rel, base in ((".claude/settings.json", None), (".claude/settings.local.json", None), (".claude/settings.json", "home")):
            with self.subTest(rel=rel, base=base):
                for f in (self.project / ".claude", self.home / ".claude"):
                    shutil.rmtree(f, ignore_errors=True)
                self.settings(rel, {SUPER_KEY: True}, self.home if base else None)
                out = self.preload()
                self.assertEqual(self.stack(out)["super-novacaelum"], "present")
                self.assertNotIn("without-super.md", out)

    def test_super_disabled_is_not_present(self):
        self.record(choices={"super": "yes"})
        self.settings(".claude/settings.json", {SUPER_KEY: False})
        self.assertEqual(self.stack(self.preload())["super-novacaelum"], "expected but missing")

    def test_hyperspace_present(self):
        self.write(".hyperspace/config.toml", "x = 1\n")
        self.assertEqual(self.stack(self.preload())["hyperspace-engine"], "present")

    def test_without_super_pointer_resolves(self):
        lines = [ln for ln in self.preload().splitlines() if "without-super.md" in ln]
        self.assertEqual(len(lines), 1)
        path = re.search(r"(/\S*/reference/without-super\.md)", lines[0]).group(1)
        self.assertTrue(Path(path).is_file(), path)

    def test_prints_no_settings_value(self):
        marker = "planted" + uuid.uuid4().hex[:8]
        self.settings(".claude/settings.json", {f"{marker}-plugin@m": True}, env={"X_API_KEY": marker}, model=marker)
        self.settings(".claude/settings.json", {f"{marker}-user@m": True}, self.home, env={"Y_TOKEN": marker})
        self.assertNotIn(marker, self.preload())

    def test_malformed_settings_and_record_fail_open(self):
        self.write("core_text/user.md", "# p\n")
        self.write(".claude/settings.json", "{not json")
        self.write("core_text/setup.json", "{not json")
        out = self.preload()
        self.assertEqual(self.stack(out)["base-novacaelum"], "present")
        self.assertIn("/base-novacaelum:ask", out)

    def test_size_budget(self):
        self.write("core_text/user.md", (TEMPLATE_DIR / "core_text" / "user.md").read_text(encoding="utf-8"))
        self.record(done=("guide",), choices={"super": "yes"})
        body = "Decided to keep the retry in the client; the server already times out at 30s. " * 4
        for i in range(3):
            self.write(f"worklog/entries/2026-09-2{i}T10-00-00-entry-{i}.md",
                       f"---\ndate: 2026-09-2{i}T10:00:00Z\nauthor: technical-cofounder\nsummary: entry {i}\ntags: [a, b]\n---\n\n{body}\n")
        out = self.preload()
        self.assertLess(len(out.encode("utf-8")), 6000)


sys.path.insert(0, str(REPO_ROOT))
from tests.test_he_bridge import IMPORT_FIRST, MIRROR_REBUILT, NO_STORE, RECENT_OK, FakeHE  # noqa: E402

BLOCK_RE = re.compile(r"(?m)^## Recent worklog")


class HyperspacePreloadTests(unittest.TestCase):
    """session-preload.sh with Hyperspace Engine present (its CLI stubbed by
    FakeHE), reusing SessionPreloadTests' temp project, pinned HOME and runner."""

    setUp = SessionPreloadTests.setUp
    preload = SessionPreloadTests.preload
    write = SessionPreloadTests.write
    stack = SessionPreloadTests.stack

    def set_up(self, view="obsidian", owner=None, entries=0):
        self.write("core_text/user.md", "# p\n")
        return FakeHE(self.project, owner=owner, view=view, entries=entries)

    def test_he_first_preload_runs_the_handshake_once(self):
        fake = self.set_up(entries=2)
        fake.respond("import", IMPORT_FIRST)
        fake.respond("mirror", MIRROR_REBUILT)
        fake.respond("recent", RECENT_OK)
        out = self.preload()
        self.assertIn('worklog_owner = "technical-cofounder"', fake.config())
        self.assertIn('worklog_mirror_dir = "worklog/entries"', fake.config())
        self.assertNotIn("handshake", out)
        config = fake.config()
        self.preload()
        self.assertEqual(fake.config(), config)
        verbs = [c[3] for c in fake.calls()]
        self.assertEqual((verbs.count("import"), verbs.count("mirror")), (1, 1))

    def test_he_owned_block_comes_from_the_cli(self):
        fake = self.set_up(owner="technical-cofounder", entries=2)
        row = dict(json.loads(RECENT_OK)["entries"][0], detailed="Decided to keep the retry in the client. " * 60)
        fake.respond("recent", json.dumps({"ok": True, "entries": [row] * 3}))
        self.write("core_text/user.md", (TEMPLATE_DIR / "core_text" / "user.md").read_text(encoding="utf-8"))
        out = self.preload()
        self.assertEqual(len(BLOCK_RE.findall(out)), 1, out)
        self.assertIn("## Recent worklog — last 3", out)
        self.assertIn("Shipped the worklog CLI.", out)
        self.assertNotIn("2026090", out, "the markdown files are not the source in this mode")
        self.assertEqual(len([ln for ln in out.splitlines() if "gear*" in ln]), 1)
        self.assertEqual(self.stack(out)["hyperspace-engine"], "present · worklog: hyperspace (owned by TC preload)")
        self.assertLess(len(out.encode("utf-8")), 6000)

    def test_he_owning_the_preload_means_no_tc_block(self):
        self.set_up(owner="hyperspace-engine", entries=1)
        out = self.preload()
        self.assertEqual(BLOCK_RE.findall(out), [])
        self.assertEqual(self.stack(out)["hyperspace-engine"], "present")

    def test_he_failed_handshake_is_one_line_and_no_tc_block(self):
        fake = self.set_up(entries=1)
        fake.respond("import", NO_STORE, 3)
        out = self.preload()
        self.assertEqual(len([ln for ln in out.splitlines() if "handshake" in ln]), 1)
        self.assertEqual(BLOCK_RE.findall(out), [])
        self.assertNotIn("worklog_owner", fake.config())

    def test_he_not_set_up_claims_nothing(self):
        fake = FakeHE(self.project, entries=1)
        before = fake.config()
        out = self.preload()
        self.assertIn("/base-novacaelum:setup", out)
        self.assertEqual(fake.config(), before)
        self.assertEqual(fake.calls(), [])


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
