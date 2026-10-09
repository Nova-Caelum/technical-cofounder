"""Unit tests for the project drive map on the Technical Cofounder side.

The map is Hyperspace Engine's (its `bin/drive_map.py tree`); this plugin only
triggers it and points at it:

  * the starter layout the setup plugin lays down (`reference/`, `work/`,
    `worklog/_entry-template.md`, `.drivemap.toml`);
  * bin/drive_map_pointer.py, which finds the engine's script, runs it with the
    project's own Hyperspace interpreter and prints ONE pointer line;
  * the session briefing's one call to it;
  * hooks/drive_map_write.py, the PreToolUse `Write` hook that adds one line of
    context for a new file, never blocks and stays silent for an existing one;
  * the one line in the agents' rules.

The engine is stubbed here: a `bin/drive_map.py` that records its argv and writes
a map, installed where Claude Code puts a plugin (a fake plugins folder with an
installed_plugins.json). An engine without `tree` is stubbed the same way. The
real engine is exercised when NC_TEST_ENGINE_DIR names a Hyperspace Engine
checkout; CI has none until an engine release carries `tree`, and says so by
skipping that class. Standard library only.
"""
import ast
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tests.test_plugin_hooks import path_without, write_tool

try:
    import tomllib
except ImportError:  # Python < 3.11: the toml assertions skip
    tomllib = None

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN = REPO_ROOT / "plugins" / "technical-cofounder"
SETUP = REPO_ROOT / "plugins" / "technical-cofounder-setup"
POINTER = PLUGIN / "bin" / "drive_map_pointer.py"
WRITE_HOOK = PLUGIN / "hooks" / "drive_map_write.py"
PRELOAD = PLUGIN / "hooks" / "session-preload.sh"
INIT = SETUP / "bin" / "init_workspace.py"
HOOKS = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]

MAP = "core_text/drive-map.md"
POINTER_LINE = re.compile(r"^Drive map: core_text/drive-map\.md \((\d+) folders?\) — read it before creating a file\.$")
NEW_FILE_LINE = "New file: check core_text/drive-map.md for where it belongs."
AGENT_RULE = "Before you create a new file or folder, read `core_text/drive-map.md` and put it where the map says it belongs."

# What the engine's `drive_map.py tree <root> --out <file>` does, as far as this
# plugin relies on it: it writes the map to --out and says
# "wrote <path> (N folders, M files, L lines)". Verified against the real engine
# by RealEngineTests.
STUB_ENGINE = '''\
import json, sys
from pathlib import Path
args = sys.argv[1:]
Path(__file__).with_name("argv.json").write_text(json.dumps(args))
out = Path(args[args.index("--out") + 1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("# Drive map\\n\\n## Tree\\n\\n" + "\\n".join("- `f%d.md`" % i for i in range(400)) + "\\n")
print("wrote %s (7 folders, 12 files, 31 lines)" % out)
'''
# An engine release from before `tree`: the same argparse refusal the real one gives.
OLD_ENGINE = '''\
import sys
sys.stderr.write("usage: drive_map.py [-h] {write,check} ...\\ndrive_map.py: error: argument cmd: invalid choice: 'tree' (choose from 'write', 'check')\\n")
sys.exit(2)
'''
SLOW_ENGINE = "import time\ntime.sleep(60)\n"
# What the real `tree` does that matters for churn: it stamps every run with a new time, keeps the text people
# wrote after the dash from the file it writes over, lists the map file when that file exists (or is where it
# writes), and lists the project's folders. The stamp is a counter, so two runs never share one.
STAMPING_ENGINE = '''\
import json, re, sys
from pathlib import Path
args = sys.argv[1:]
Path(__file__).with_name("argv.json").write_text(json.dumps(args))
root, out = Path(args[1]).resolve(), Path(args[args.index("--out") + 1])
counter = Path(__file__).with_name("runs.txt")
runs = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(runs))
out.parent.mkdir(parents=True, exist_ok=True)  # the real one makes the folder before it walks, so a first map lists its own folder
kept = {}
if out.exists():
    for line in out.read_text(encoding="utf-8").splitlines():
        found = re.match(r"^- `([^`]+)` — (.*)$", line)
        if found:
            kept[found.group(1)] = found.group(2)
paths = sorted(str(p.relative_to(root).as_posix()) + "/" for p in root.rglob("*") if p.is_dir() and not p.relative_to(root).parts[0].startswith("."))
if (root / "core_text" / "drive-map.md").exists() or root in out.resolve().parents:
    paths.append("core_text/drive-map.md")
body = ["- `%s`%s" % (n, " — " + kept[n] if n in kept else "") for n in paths]
out.write_text("\\n".join(["# Drive map", "", "> Generated 2026-10-08 12:%02d UTC. **%d folders, 0 files** under `proj/`." % (runs, len(paths)), "", "## Tree", "", *body]) + "\\n", encoding="utf-8")
print("wrote %s (%d folders, 0 files, %d lines)" % (out, len(paths), len(body) + 6))
'''


def load_pointer():
    """bin/drive_map_pointer.py as a module; the test that needs it fails, not the whole file, when it is absent."""
    if not POINTER.is_file():
        raise AssertionError(f"{POINTER.relative_to(REPO_ROOT)} does not exist")
    spec = importlib.util.spec_from_file_location("drive_map_pointer", POINTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bash():
    """Git Bash, which is what Claude Code runs hooks in on Windows."""
    git = shutil.which("git") if os.name == "nt" else None
    for parent in Path(git).resolve().parents if git else ():
        if (parent / "bin" / "bash.exe").is_file():
            return str(parent / "bin" / "bash.exe")
    return "bash"


BASH = _bash()


def clean_env(home, **extra):
    """This machine's environment with nothing of Claude Code's own in it."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("CLAUDE") and k not in ("NC_TEST_ENGINE_DIR",)}
    env.update(HOME=str(home), USERPROFILE=str(home), PYTHONDONTWRITEBYTECODE="1")
    env.update(extra)
    return env


class Machine:
    """One scratch machine: a project with a real Hyperspace environment, a fake
    Claude Code plugins folder, and a HOME that is not this machine's."""

    def __init__(self, test):
        self.base = Path(tempfile.mkdtemp())
        test.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.home = self.base / "home"
        self.home.mkdir()
        self.project = self.base / "proj"
        self.project.mkdir()
        self.plugins = self.base / "plugins"
        self.engine_dir = self.plugins / "cache" / "nova-caelum" / "hyperspace-engine" / "0.2.0"

    def environment(self, with_pip=False):
        """A real venv where the project's Hyperspace environment goes: bin/python on
        Mac and Linux, Scripts/python.exe on Windows."""
        venv.EnvBuilder(with_pip=with_pip, symlinks=os.name != "nt").create(self.project / ".hyperspace" / "env")

    def engine(self, script=STUB_ENGINE, scope="project", project_path=None, id_="hyperspace-engine@nova-caelum"):
        """Install `script` as the engine's bin/drive_map.py and record it as Claude Code does."""
        (self.engine_dir / "bin").mkdir(parents=True, exist_ok=True)
        (self.engine_dir / "bin" / "drive_map.py").write_text(script, encoding="utf-8")
        entry = {"scope": scope, "installPath": str(self.engine_dir), "version": "0.2.0"}
        if scope == "project":
            entry["projectPath"] = str(project_path or self.project)
        record = self.plugins / "installed_plugins.json"
        known = json.loads(record.read_text(encoding="utf-8"))["plugins"] if record.exists() else {}
        known.setdefault(id_, []).append(entry)
        record.write_text(json.dumps({"version": 2, "plugins": known}), encoding="utf-8")

    def env(self, **extra):
        return clean_env(self.home, CLAUDE_CODE_PLUGIN_CACHE_DIR=str(self.plugins),
                         CLAUDE_PROJECT_DIR=str(self.project), **extra)

    def pointer(self, verb="preload", **extra):
        return subprocess.run([sys.executable, str(POINTER), verb, str(self.project)], capture_output=True,
                              text=True, encoding="utf-8", env=self.env(**extra), timeout=120)

    def argv(self):
        return json.loads((self.engine_dir / "bin" / "argv.json").read_text(encoding="utf-8"))

    @property
    def map(self):
        return self.project / "core_text" / "drive-map.md"


class PointerTests(unittest.TestCase):
    """bin/drive_map_pointer.py: find the engine, run `tree`, say one line."""

    def setUp(self):
        self.m = Machine(self)
        self.m.environment()

    def assertQuiet(self, done, why):
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout, "", "a failure must put nothing in the session's context")
        lines = [ln for ln in done.stderr.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, done.stderr)
        self.assertIn("drive-map", lines[0])
        self.assertIn(why, lines[0])

    # ── the happy path ────────────────────────────────────────────────────
    def test_it_writes_the_map_with_the_engines_tree_mode_and_says_one_line(self):
        self.m.engine()
        done = self.m.pointer()
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.splitlines()
        self.assertEqual(len(lines), 1, done.stdout)
        found = POINTER_LINE.match(lines[0])
        self.assertTrue(found, lines[0])
        self.assertEqual(found.group(1), "7", "the folder count is the engine's own")
        self.assertEqual(self.m.argv(), ["tree", str(self.m.project), "--out", str(self.m.map)])
        self.assertTrue(self.m.map.is_file())

    def test_it_never_prints_the_map_itself(self):
        self.m.engine()
        done = self.m.pointer()
        self.assertGreater(len(self.m.map.read_text(encoding="utf-8").splitlines()), 100)
        self.assertLess(len(done.stdout), 200, done.stdout)
        self.assertNotIn("f399.md", done.stdout)

    def test_the_pointer_line_is_not_given_for_a_map_that_was_not_written(self):
        self.m.engine("print('wrote nothing (3 folders, 1 files, 4 lines)')\n")
        self.assertQuiet(self.m.pointer(), "no map")

    # ── finding the engine ────────────────────────────────────────────────
    def test_locate_reads_installed_plugins_json_for_this_project(self):
        self.m.engine()
        done = self.m.pointer("locate")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(Path(done.stdout.strip()), self.m.engine_dir / "bin" / "drive_map.py")

    def test_an_install_for_another_project_is_not_ours(self):
        self.m.engine(project_path=self.m.base / "elsewhere")
        done = self.m.pointer()
        self.assertQuiet(done, "not found")
        self.assertFalse(self.m.map.exists())

    def test_a_user_scope_install_serves_every_project(self):
        self.m.engine(scope="user")
        self.assertRegex(self.m.pointer().stdout, POINTER_LINE)

    def test_it_looks_where_its_own_plugin_was_installed_when_no_folder_is_named(self):
        """No CLAUDE_CODE_PLUGIN_CACHE_DIR: the team plugin sits at <plugins>/cache/<catalog>/<name>/<version>,
        and the plugins folder is three levels up."""
        self.m.engine()
        team = self.m.plugins / "cache" / "nova-caelum" / "technical-cofounder" / "0.3.0"
        (team / "bin").mkdir(parents=True)
        shutil.copyfile(POINTER, team / "bin" / "drive_map_pointer.py")
        env = clean_env(self.m.home, CLAUDE_PLUGIN_ROOT=str(team))
        done = subprocess.run([sys.executable, str(team / "bin" / "drive_map_pointer.py"), "preload", str(self.m.project)],
                              capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        self.assertRegex(done.stdout.strip(), POINTER_LINE)

    # ── failing quietly ───────────────────────────────────────────────────
    def test_no_engine_installed_is_one_log_line_and_nothing_else(self):
        self.assertQuiet(self.m.pointer(), "not found")

    def test_an_engine_without_tree_mode_is_one_log_line_and_no_pointer(self):
        self.m.engine(OLD_ENGINE)
        self.assertQuiet(self.m.pointer(), "tree")
        self.assertFalse(self.m.map.exists())

    def test_a_project_with_no_hyperspace_environment_is_one_log_line(self):
        shutil.rmtree(self.m.project / ".hyperspace")
        self.m.engine()
        self.assertQuiet(self.m.pointer(), "environment")
        self.assertFalse((self.m.engine_dir / "bin" / "argv.json").exists(), "nothing may be run without it")

    def test_an_engine_that_hangs_is_given_up_on(self):
        self.m.engine(SLOW_ENGINE)
        module = load_pointer()
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.m.env(), clear=True), redirect_stdout(out), redirect_stderr(err):
            code = module.preload(self.m.project, seconds=1)
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("seconds", err.getvalue())
        self.assertEqual(len(err.getvalue().strip().splitlines()), 1, err.getvalue())

    def test_an_unreadable_installed_plugins_json_is_one_log_line(self):
        self.m.engine()
        (self.m.plugins / "installed_plugins.json").write_text("{not json", encoding="utf-8")
        self.assertQuiet(self.m.pointer(), "not found")

    def test_the_project_environment_runs_it_not_the_system_python(self):
        """tomllib is 3.11+; the system python3 can be older. The engine's own environment is not."""
        self.m.engine("import sys, json, pathlib\npathlib.Path(__file__).with_name('who.txt').write_text(sys.prefix)\n"
                      "out = pathlib.Path(sys.argv[sys.argv.index('--out') + 1]); out.parent.mkdir(exist_ok=True)\n"
                      "out.write_text('x'); print('wrote x (2 folders, 0 files, 1 lines)')\n")
        self.m.pointer()
        who = (self.m.engine_dir / "bin" / "who.txt").read_text(encoding="utf-8")
        self.assertEqual(os.path.realpath(who), os.path.realpath(self.m.project / ".hyperspace" / "env"))


class NoChurnTests(unittest.TestCase):
    """The map must not show as modified in a user's git every session: an unchanged project leaves the
    file alone (same bytes, same mtime), and only a real change rewrites it."""

    LONG_AGO = 1_000_000_000  # an mtime nothing written just now can share

    def setUp(self):
        self.m = Machine(self)
        self.m.environment()
        self.m.engine(STAMPING_ENGINE)

    def age(self):
        os.utime(self.m.map, (self.LONG_AGO, self.LONG_AGO))
        return self.m.map.read_bytes()

    def test_two_runs_with_no_folder_change_leave_the_file_untouched(self):
        self.assertRegex(self.m.pointer().stdout, POINTER_LINE)
        first = self.age()
        done = self.m.pointer()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.m.map.read_bytes(), first, "the bytes changed")
        self.assertEqual(self.m.map.stat().st_mtime, self.LONG_AGO, "the file was rewritten")

    def test_the_pointer_line_is_printed_on_every_run_even_when_the_file_is_left_alone(self):
        for _ in range(3):
            self.assertRegex(self.m.pointer().stdout.strip(), POINTER_LINE)

    def test_adding_a_folder_rewrites_it(self):
        self.m.pointer()
        before = self.age()
        (self.m.project / "work" / "app").mkdir(parents=True)
        self.assertRegex(self.m.pointer().stdout, POINTER_LINE)
        after = self.m.map.read_bytes()
        self.assertNotEqual(after, before)
        self.assertIn(b"work/app/", after)
        self.assertNotEqual(self.m.map.stat().st_mtime, self.LONG_AGO)

    def test_removing_a_folder_rewrites_it(self):
        (self.m.project / "work").mkdir()
        self.m.pointer()
        self.age()
        (self.m.project / "work").rmdir()
        self.m.pointer()
        self.assertNotIn(b"work/", self.m.map.read_bytes())

    def test_text_after_the_dash_survives_a_rewrite(self):
        (self.m.project / "reference").mkdir()
        self.m.pointer()
        self.m.map.write_text(self.m.map.read_text(encoding="utf-8").replace(
            "- `reference/`", "- `reference/` — what the user brings"), encoding="utf-8")
        (self.m.project / "work").mkdir()  # a change, so the file is rewritten
        self.m.pointer()
        text = self.m.map.read_text(encoding="utf-8")
        self.assertIn("- `reference/` — what the user brings", text)
        self.assertIn("- `work/`", text)

    def test_the_first_map_lists_itself_so_the_second_run_finds_nothing_to_change(self):
        self.m.pointer()
        self.assertIn("core_text/drive-map.md", self.m.map.read_text(encoding="utf-8"))

    def test_the_first_run_writes_the_map_and_later_runs_write_a_temporary_file_outside_the_project(self):
        self.m.pointer()
        self.assertEqual(self.m.argv()[3], str(self.m.map))
        self.age()
        self.m.pointer()
        later = Path(self.m.argv()[3])
        self.assertNotEqual(later, self.m.map)
        self.assertNotIn(self.m.project.resolve(), later.resolve().parents, "a temp file in the project would be listed in the map")
        self.assertFalse(later.exists(), "the temporary file is cleaned up")

    def test_a_failing_run_leaves_the_existing_map_as_it_was(self):
        self.m.pointer()
        first = self.age()
        (self.m.engine_dir / "bin" / "drive_map.py").write_text(OLD_ENGINE, encoding="utf-8")  # the same install, now without tree
        done = self.m.pointer()
        self.assertEqual((done.returncode, done.stdout), (0, ""))
        self.assertEqual(self.m.map.read_bytes(), first)
        self.assertEqual(self.m.map.stat().st_mtime, self.LONG_AGO)


class BriefingTests(unittest.TestCase):
    """The session briefing's one call: the pointer line in the briefing, a failure that costs nothing."""

    def setUp(self):
        self.m = Machine(self)
        self.m.environment()
        (self.m.project / "core_text").mkdir()
        (self.m.project / "core_text" / "user.md").write_text("# profile-marker\n", encoding="utf-8")

    def briefing(self):
        done = subprocess.run([BASH, str(PRELOAD)], input="{}", capture_output=True, text=True, encoding="utf-8",
                              env=self.m.env(), timeout=300)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done

    def test_the_briefing_runs_the_engine_and_carries_one_pointer_line(self):
        self.m.engine()
        done = self.briefing()
        pointers = [ln for ln in done.stdout.splitlines() if ln.startswith("Drive map:")]
        self.assertEqual(len(pointers), 1, done.stdout)
        self.assertRegex(pointers[0], POINTER_LINE)
        self.assertIn("profile-marker", done.stdout)
        self.assertNotIn("f399.md", done.stdout, "the map itself is never printed")
        self.assertTrue(self.m.map.is_file())

    def test_a_missing_engine_leaves_the_briefing_as_it_was_and_logs_once(self):
        done = self.briefing()
        self.assertNotIn("Drive map:", done.stdout)
        self.assertIn("profile-marker", done.stdout)
        self.assertEqual(done.stderr.count("drive-map"), 1, done.stderr)

    def test_a_project_not_yet_set_up_gets_no_map(self):
        self.m.engine()
        (self.m.project / "core_text" / "user.md").unlink()
        done = self.briefing()
        self.assertNotIn("Drive map:", done.stdout)
        self.assertFalse(self.m.map.exists(), "setup has not laid the project down yet")

    def test_an_engine_without_tree_mode_does_not_break_the_briefing(self):
        self.m.engine(OLD_ENGINE)
        done = self.briefing()
        self.assertNotIn("Drive map:", done.stdout)
        self.assertIn("## Tech primer (live)", done.stdout)


class WriteHookTests(unittest.TestCase):
    """hooks/drive_map_write.py: one line for a new file, nothing else, never a block."""

    def setUp(self):
        self.m = Machine(self)
        (self.m.project / "core_text").mkdir()
        self.m.map.write_text("# Drive map\n", encoding="utf-8")
        (self.m.project / "notes.md").write_text("old", encoding="utf-8")

    def event(self, rel, content="CONTENT-MARKER", tool="Write", absolute=None):
        path = absolute if absolute is not None else str(self.m.project / rel)
        return {"session_id": "s", "hook_event_name": "PreToolUse", "cwd": str(self.m.project),
                "tool_name": tool, "tool_input": {"file_path": path, "content": content}}

    def run_hook(self, event, raw=None, **env):
        return subprocess.run([sys.executable, str(WRITE_HOOK)], input=raw if raw is not None else json.dumps(event),
                              capture_output=True, text=True, encoding="utf-8",
                              env=self.m.env(**env), timeout=60)

    def test_a_new_file_gets_one_line_of_context_and_no_decision(self):
        done = self.run_hook(self.event("work/app/main.py"))
        self.assertEqual(done.returncode, 0, done.stderr)
        body = json.loads(done.stdout)
        self.assertEqual(body, {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": NEW_FILE_LINE}})
        self.assertNotIn("permissionDecision", done.stdout)

    def test_an_existing_file_is_silent(self):
        done = self.run_hook(self.event("notes.md"))
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))

    def test_it_never_echoes_what_was_being_written(self):
        done = self.run_hook(self.event("a.md", content="SECRET-SHAPED-MARKER sk-live-123"))
        self.assertNotIn("SECRET-SHAPED-MARKER", done.stdout + done.stderr)
        self.assertNotIn("a.md", done.stdout)

    def test_a_path_outside_the_project_is_silent(self):
        done = self.run_hook(self.event("x", absolute=str(self.m.base / "elsewhere" / "x.md")))
        self.assertEqual((done.returncode, done.stdout), (0, ""))

    def test_a_project_with_no_map_is_silent(self):
        self.m.map.unlink()
        self.assertEqual(self.run_hook(self.event("new.md")).stdout, "")

    def test_the_engines_own_folders_and_hidden_folders_are_silent(self):
        for rel in ("hyperspace/runs/a-run/notes/n.md", ".claude/rules/new.md", ".hyperspace/x.md"):
            with self.subTest(rel=rel):
                self.assertEqual(self.run_hook(self.event(rel)).stdout, "")

    def test_garbage_in_is_silent_and_exits_zero(self):
        for raw in ("", "not json", "[]", json.dumps({"tool_name": "Write"}),
                    json.dumps({"tool_input": {"file_path": 7}}), json.dumps({"tool_input": {}})):
            with self.subTest(raw=raw):
                done = self.run_hook(None, raw=raw)
                self.assertEqual((done.returncode, done.stdout), (0, ""))

    def test_another_tool_is_silent(self):
        self.assertEqual(self.run_hook(self.event("work/x.py", tool="Edit")).stdout, "")

    def test_it_imports_only_the_standard_library(self):
        """hooks/run-system-python.sh runs it with the computer's own Python, which has none of the project's packages."""
        stdlib = getattr(sys, "stdlib_module_names", None)
        if stdlib is None:
            self.skipTest("sys.stdlib_module_names needs Python 3.10+")
        tree = ast.parse(WRITE_HOOK.read_text(encoding="utf-8"))
        imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and not n.level}
        self.assertTrue(imported, "found no imports; the check proves nothing")
        self.assertEqual(sorted(imported - set(stdlib)), [])


class WriteHookRegistrationTests(unittest.TestCase):
    """The declared command, run the way Claude Code runs it: under bash. It runs with this
    computer's own Python and never with the project's: a downloaded folder can ship a file at
    .hyperspace/env/bin/python, and this hook fires on every Write in every folder."""

    def groups(self):
        return [g for g in HOOKS.get("PreToolUse", []) if g.get("matcher") == "Write"]

    def test_hooks_json_registers_one_write_hook_and_keeps_the_circuit_breaker(self):
        (group,) = self.groups()
        (hook,) = group["hooks"]
        self.assertEqual(hook["type"], "command")
        self.assertIn("hooks/drive_map_write.py", hook["command"])
        self.assertIn("hooks/run-system-python.sh", hook["command"])
        self.assertNotIn(".hyperspace", hook["command"])
        self.assertNotIn("CLAUDE_PROJECT_DIR", hook["command"])
        wildcard = [g for g in HOOKS["PreToolUse"] if g.get("matcher") == "*"]
        self.assertTrue(any("circuit-breaker.sh" in h["command"] for g in wildcard for h in g["hooks"]))

    def test_the_hook_is_python_not_shell(self):
        self.assertTrue(WRITE_HOOK.is_file())
        self.assertTrue(WRITE_HOOK.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3"))
        self.assertEqual(list((PLUGIN / "hooks").glob("*write*.sh")), [])

    def run_declared(self, m, path, **env):
        (command,) = [h["command"] for g in self.groups() for h in g["hooks"]]
        env_all = m.env(CLAUDE_PLUGIN_ROOT=str(PLUGIN), TC_HOOK_COMMAND=command, **env)
        event = {"hook_event_name": "PreToolUse", "cwd": str(m.project), "tool_name": "Write",
                 "tool_input": {"file_path": str(path), "content": "x"}}
        # the command travels in the environment so its own quotes reach bash intact
        return subprocess.run([BASH, "-c", "eval $TC_HOOK_COMMAND"], input=json.dumps(event), capture_output=True,
                              text=True, encoding="utf-8", env=env_all, timeout=60)

    @staticmethod
    def planted(m):
        """What a downloaded folder can ship at .hyperspace/env: an interpreter, in either layout, that records
        being started and exits 0. Returns the file it records to."""
        marker = m.base / "planted-interpreter-started"
        body = f'#!/bin/sh\necho "started: $0 $*" >> "{marker.as_posix()}"\nexit 0\n'
        for rel in ("bin/python", "Scripts/python.exe"):
            write_tool(m.project / ".hyperspace" / "env" / rel, body)
        return marker

    @staticmethod
    def mapped(m):
        (m.project / "core_text").mkdir()
        m.map.write_text("# Drive map\n", encoding="utf-8")

    def assertSpokeForNewFile(self, done):
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout, "the hook said nothing for a new file")
        self.assertEqual(json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"], NEW_FILE_LINE)

    def assertNeverStarted(self, marker):
        self.assertFalse(marker.exists(),
                         "the project's own interpreter was started:\n" + (marker.read_text() if marker.exists() else ""))

    def test_the_declared_command_speaks_for_a_new_file_with_the_system_python_and_never_starts_the_projects(self):
        m = Machine(self)
        marker = self.planted(m)
        self.mapped(m)
        done = self.run_declared(m, m.project / "work" / "new.py")
        self.assertNeverStarted(marker)
        self.assertSpokeForNewFile(done)
        quiet = self.run_declared(m, m.project / "core_text" / "drive-map.md")
        self.assertEqual((quiet.returncode, quiet.stdout), (0, ""))
        self.assertNeverStarted(marker)

    def test_the_declared_command_speaks_in_a_project_that_was_never_set_up(self):
        m = Machine(self)  # no .hyperspace/env: the hook needs none
        self.mapped(m)
        self.assertSpokeForNewFile(self.run_declared(m, m.project / "work" / "new.py"))

    def test_with_no_python_on_the_machine_the_declared_command_is_silent_and_never_starts_the_projects(self):
        m = Machine(self)
        marker = self.planted(m)
        self.mapped(m)
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        done = self.run_declared(m, m.project / "work" / "new.py", PATH=path_without(scratch, "python3", "python", "py"))
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertNeverStarted(marker)

    def test_the_runner_passes_arguments_and_input_through_and_fails_open(self):
        m = Machine(self)
        runner = PLUGIN / "hooks" / "run-system-python.sh"
        echo = m.base / "echo.py"
        echo.write_text("import sys\nprint(sys.argv[1:], sys.stdin.read())\n", encoding="utf-8")
        crash = m.base / "crash.py"
        crash.write_text("import sys\nsys.stderr.write('boom')\nraise SystemExit(7)\n", encoding="utf-8")

        def run(*args):
            return subprocess.run([BASH, str(runner), *map(str, args)], input="payload", capture_output=True, text=True,
                                  encoding="utf-8", env=m.env(), timeout=60)

        done = run(echo, "one", "two w")
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "['one', 'two w'] payload"))
        failed = run(crash)  # exits 7 and writes to stderr: the runner says nothing and exits 0
        self.assertEqual((failed.returncode, failed.stdout, failed.stderr), (0, "", ""))
        bare = run()  # nothing to run
        self.assertEqual((bare.returncode, bare.stdout, bare.stderr), (0, "", ""))


class StarterLayoutTests(unittest.TestCase):
    """What a fresh init_workspace project gets."""

    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.project, ignore_errors=True)
        done = subprocess.run([sys.executable, str(INIT), str(self.project), "--no-obsidian", "--no-super"],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.out = done.stdout

    def test_it_has_a_folder_for_what_the_user_brings_and_one_for_what_they_build(self):
        for folder in ("reference", "work"):
            with self.subTest(folder=folder):
                self.assertTrue((self.project / folder).is_dir())
                self.assertTrue(any((self.project / folder).iterdir()), "a folder with nothing in it does not survive a copy")

    def test_the_folders_say_what_goes_in_them(self):
        self.assertIn("bring", (self.project / "reference" / "README.md").read_text(encoding="utf-8").lower())
        self.assertIn("build", (self.project / "work" / "README.md").read_text(encoding="utf-8").lower())

    def test_the_worklog_has_an_entry_template_the_worklog_can_read(self):
        text = (self.project / "worklog" / "_entry-template.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\n"))
        head = text.split("\n---", 1)[0]
        for key in ("date:", "author:", "summary:", "tags:"):
            self.assertIn(key, head)
        self.assertFalse((self.project / "worklog" / "entries").exists(), "the template is not an entry")

    @unittest.skipIf(tomllib is None, "reading TOML needs Python 3.11")
    def test_drivemap_toml_carries_the_defaults_and_nothing_the_engine_would_not_read(self):
        data = tomllib.loads((self.project / ".drivemap.toml").read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"exclude", "cutoff", "max_depth", "budget"})
        self.assertEqual((data["max_depth"], data["budget"]), (3, 400))
        self.assertIn(".*", data["exclude"])
        self.assertIn("worklog/entries", data["cutoff"])
        self.assertTrue(all(isinstance(v, str) for v in data["exclude"] + data["cutoff"]))

    def test_the_layout_is_in_the_projects_claude_md(self):
        text = (self.project / "CLAUDE.md").read_text(encoding="utf-8")
        for needle in ("reference/", "work/", "core_text/drive-map.md", ".drivemap.toml"):
            self.assertIn(needle, text)

    def test_a_second_run_changes_nothing(self):
        done = subprocess.run([sys.executable, str(INIT), str(self.project), "--no-obsidian", "--no-super"],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertNotIn("COPIED:", done.stdout)
        self.assertIn("SKIPPED: .drivemap.toml", done.stdout)


class AgentRuleTests(unittest.TestCase):
    def test_the_builder_and_the_lead_are_told_to_read_the_map_before_creating_a_file(self):
        for name in ("engineer", "technical-cofounder"):
            with self.subTest(agent=name):
                text = (PLUGIN / "agents" / f"{name}.md").read_text(encoding="utf-8")
                self.assertEqual(text.count(AGENT_RULE), 1)


@unittest.skipUnless(os.environ.get("NC_TEST_ENGINE_DIR"), "needs a Hyperspace Engine checkout with `tree`: set NC_TEST_ENGINE_DIR")
class RealEngineTests(unittest.TestCase):
    """Local whole-path check: a fresh init_workspace project, the REAL engine's tree mode, the real pointer."""

    def machine(self):
        m = Machine(self)
        m.environment()
        subprocess.run([sys.executable, str(INIT), str(m.project), "--no-obsidian", "--no-super"], check=True,
                       capture_output=True)
        (m.project / "core_text" / "user.md").write_text("# profile\n", encoding="utf-8")
        m.engine_dir = Path(os.environ["NC_TEST_ENGINE_DIR"])
        m.plugins.mkdir()
        (m.plugins / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {
            "hyperspace-engine@nova-caelum": [{"scope": "user", "installPath": str(m.engine_dir), "version": "dev"}]}}), encoding="utf-8")
        return m

    def test_a_second_run_with_no_change_leaves_the_real_map_untouched_and_a_new_folder_rewrites_it(self):
        m = self.machine()
        self.assertRegex(m.pointer().stdout, POINTER_LINE)
        os.utime(m.map, (1_000_000_000, 1_000_000_000))
        first = m.map.read_bytes()
        self.assertRegex(m.pointer().stdout, POINTER_LINE)
        self.assertEqual(m.map.read_bytes(), first)
        self.assertEqual(m.map.stat().st_mtime, 1_000_000_000, "the file was rewritten")
        (m.project / "work" / "app").mkdir()
        self.assertRegex(m.pointer().stdout, POINTER_LINE)
        self.assertIn("work/app/", m.map.read_text(encoding="utf-8"))
        self.assertNotEqual(m.map.stat().st_mtime, 1_000_000_000)

    def test_text_after_the_dash_in_the_real_map_survives_the_temporary_file(self):
        m = self.machine()
        m.pointer()
        m.map.write_text(m.map.read_text(encoding="utf-8").replace("- `work/`", "- `work/` — what I build"), encoding="utf-8")
        (m.project / "work" / "app").mkdir()
        m.pointer()
        self.assertIn("- `work/` — what I build", m.map.read_text(encoding="utf-8"))

    def test_a_fresh_project_gets_a_map_that_honours_its_exclude_list(self):
        m = self.machine()
        (m.project / "reference" / "scratch").mkdir()
        (m.project / "reference" / "scratch" / "huge.txt").write_text("x", encoding="utf-8")
        toml = (m.project / ".drivemap.toml").read_text(encoding="utf-8")
        (m.project / ".drivemap.toml").write_text(toml.replace('exclude = [', 'exclude = ["scratch", '), encoding="utf-8")
        done = m.pointer()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertRegex(done.stdout.strip(), POINTER_LINE)
        text = m.map.read_text(encoding="utf-8")
        paths = re.findall(r"^- `([^`]+)`", text, re.M)
        for want in ("reference/", "work/", "worklog/", "worklog/_entry-template.md", "core_text/user.md", MAP):
            self.assertIn(want, paths)
        for hidden in ("reference/scratch/", "reference/scratch/huge.txt", ".drivemap.toml", ".hyperspace/", ".claude/"):
            self.assertNotIn(hidden, paths)
        print("\n".join(text.splitlines()[:30]), file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
