"""The session briefing names what is broken, and what each skipped setup step
costs (plugins/technical-cofounder/hooks/session-preload.sh).

Every test runs the real hook against a temp project and reads what it
printed. The project's Hyperspace environment, where a test needs one, is a
real virtual environment, so its interpreter starts the same way on every
system. HOME and the tools folder are temp folders, so nothing on this machine
decides a result. Standard library only.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from tests.test_plugin_hooks import BASH, PLUGIN_ROOT, PYTHON_NAMES, path_without, write_tool  # noqa: E402

SETUP_RECORD = REPO_ROOT / "plugins" / "technical-cofounder-setup" / "bin" / "setup_record.py"

ENGINE_LINE = ("Hyperspace Engine isn't set up in this project yet, so the task graph and the worklog tools are off. "
               'Fix: run /technical-cofounder-setup:start (or say "set up hyperspace").')
SERVER_LINE = "The team's worklog server could not start, so worklog tools are off. Fix: run /technical-cofounder-setup:start."
JQ_LINE = "jq isn't installed, so the retry breaker and the word-budget checks are off. Fix: run /technical-cofounder-setup:start."
PYTHON_LINE = "No Python was found, so the plugin overview could not be read. Fix: run /technical-cofounder-setup:start."
HEALTH_LINES = (ENGINE_LINE, SERVER_LINE, JQ_LINE, PYTHON_LINE)
HEADING = "## Health"
CONTINUE_LINE = 'Say "continue setup" to pick any of these up.'
TIME_LIMIT = 10  # seconds: the hook must be done by then, whatever is broken

# Enough of jq for the briefing, which only asks whether one runs.
JQ_STAND_IN = "#!/bin/bash\necho jq-stand-in\n"
SERVER_EXITS = "import sys\nsys.exit(1)\n"
SERVER_TALKS_NONSENSE = "print('not a reply', flush=True)\n"
SERVER_HANGS = "import time\ntime.sleep(120)\n"


def snapshot(root):
    """Every path under root with its size and modification time."""
    return {str(p.relative_to(root)): (p.is_dir(), p.lstat().st_size, p.lstat().st_mtime_ns) for p in sorted(root.rglob("*"))}


class HealthBriefingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.shared, ignore_errors=True)
        cls.env_template = cls.shared / "env"
        venv.EnvBuilder(with_pip=False, symlinks=os.name != "nt").create(cls.env_template)
        if os.name == "nt":
            # On Windows the engine keeps its interpreter in env\Scripts and
            # links env\bin to it, because env/bin/python is what the team's
            # server is started with.
            shutil.copytree(cls.env_template / "Scripts", cls.env_template / "bin")
        cls.no_jq = path_without(cls.shared, "jq")
        cls.no_python = path_without(cls.shared, *PYTHON_NAMES, "py")

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project, self.home = self.tmp / "project", self.tmp / "home"
        self.project.mkdir()
        self.home.mkdir()
        self.tools = write_tool(self.tmp / "tools" / "jq", JQ_STAND_IN).parent
        self.empty = self.tmp / "no-tools"
        self.empty.mkdir()

    # ── fixtures ──────────────────────────────────────────────────────────
    def workspace(self):
        """A Hyperspace environment whose interpreter really runs."""
        shutil.copytree(self.env_template, self.project / ".hyperspace" / "env", symlinks=True)

    def plugin_with_server(self, source):
        """A copy of the plugin whose server is `source`."""
        copy = self.tmp / "plugin"
        shutil.copytree(PLUGIN_ROOT, copy, ignore=shutil.ignore_patterns("__pycache__"))
        (copy / "mcp" / "server.py").write_text(source, encoding="utf-8")
        return copy

    def record(self, steps):
        path = self.project / "core_text" / "setup.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema_version": 1, "steps": steps, "choices": {}}), encoding="utf-8")

    def brief(self, plugin=PLUGIN_ROOT, cwd=None, **env_extra):
        """Run the hook; it must exit 0 inside the time limit whatever it finds.
        An environment name given as None is left out altogether."""
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR", "NC_TOOLS_DIR")}
        env.update({"CLAUDE_PROJECT_DIR": str(self.project), "CLAUDE_PLUGIN_ROOT": str(plugin), "HOME": str(self.home),
                    "NC_TOOLS_DIR": str(self.tools), **env_extra})
        env = {k: v for k, v in env.items() if v is not None}
        started = time.monotonic()
        r = subprocess.run([BASH, str(plugin / "hooks" / "session-preload.sh")], input="{}", capture_output=True,
                           text=True, encoding="utf-8", env=env, timeout=120, cwd=cwd)
        took = time.monotonic() - started
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(took, TIME_LIMIT, f"the briefing took {took:.1f}s")
        return r.stdout

    def faults(self, out):
        return [ln for ln in out.splitlines() if ln in HEALTH_LINES]

    def assert_faults(self, out, *expected):
        self.assertEqual(self.faults(out), list(expected), out)
        self.assertEqual(out.splitlines().count(HEADING), 1 if expected else 0, out)

    # ── what is broken ────────────────────────────────────────────────────
    def test_no_engine_workspace_is_named_once_and_alone(self):
        self.assert_faults(self.brief(), ENGINE_LINE)

    def test_a_workspace_whose_interpreter_does_not_run_is_the_same_fault(self):
        write_tool(self.project / ".hyperspace" / "env" / "bin" / "python", "#!/bin/bash\nexit 1\n")
        write_tool(self.project / ".hyperspace" / "env" / "Scripts" / "python.exe", "#!/bin/bash\nexit 1\n")
        self.assert_faults(self.brief(), ENGINE_LINE)

    def test_a_server_that_exits_at_once_is_named(self):
        self.workspace()
        self.assert_faults(self.brief(self.plugin_with_server(SERVER_EXITS)), SERVER_LINE)

    def test_a_server_that_answers_with_something_else_is_named(self):
        self.workspace()
        self.assert_faults(self.brief(self.plugin_with_server(SERVER_TALKS_NONSENSE)), SERVER_LINE)

    def test_a_server_that_never_answers_is_named_inside_the_time_limit(self):
        self.workspace()
        self.assert_faults(self.brief(self.plugin_with_server(SERVER_HANGS)), SERVER_LINE)

    def test_missing_jq_is_named(self):
        self.workspace()
        self.assert_faults(self.brief(PATH=self.no_jq, NC_TOOLS_DIR=str(self.empty)), JQ_LINE)

    def test_a_healthy_project_prints_no_health_block(self):
        self.workspace()
        out = self.brief()
        self.assert_faults(out)
        self.assertNotIn(HEADING, out)
        self.assertIn("## Tech primer (live)", out)

    def test_faults_are_listed_in_order_one_line_each(self):
        self.assert_faults(self.brief(PATH=self.no_jq, NC_TOOLS_DIR=str(self.empty)), ENGINE_LINE, JQ_LINE)

    def test_no_python_at_all_is_one_plain_line(self):
        out = self.brief(PATH=self.no_python)
        self.assert_faults(out, ENGINE_LINE, PYTHON_LINE)
        self.assertNotIn("Tech primer", out, "a heading with nothing under it")

    def test_with_no_python_on_path_the_workspace_interpreter_reads_the_overview(self):
        # The last resort: nothing on PATH runs, the project's own interpreter
        # does. Nothing is broken, so nothing is reported.
        self.workspace()
        out = self.brief(PATH=self.no_python)
        self.assert_faults(out)
        self.assertIn("- technical-cofounder: present", out)

    def test_the_project_is_the_current_folder_when_claude_code_names_none(self):
        # The hook falls back to the current folder; the search for an
        # interpreter has to look in the same project the rest of it reads.
        self.workspace()
        out = self.brief(cwd=self.project, CLAUDE_PROJECT_DIR=None, PATH=self.no_python)
        self.assert_faults(out)
        self.assertIn("- technical-cofounder: present", out)

    def test_every_fault_line_names_the_fix(self):
        for line in HEALTH_LINES:
            self.assertIn("Fix: run /technical-cofounder-setup:start", line)
        self.assertIn('say "set up hyperspace"', ENGINE_LINE)

    def test_the_block_comes_before_the_profile_and_the_worklog(self):
        (self.project / "core_text").mkdir()
        (self.project / "core_text" / "user.md").write_text("# profile-marker\n", encoding="utf-8")
        out = self.brief()
        self.assert_faults(out, ENGINE_LINE)
        self.assertLess(out.index(HEADING), out.index("## user.md"))
        self.assertLess(out.index(HEADING), out.index("## Recent worklog"))

    def test_the_block_is_there_before_the_project_is_set_up_too(self):
        out = self.brief()
        self.assertLess(out.index(HEADING), out.index("## Tech primer (live)"))

    def test_the_briefing_writes_nothing(self):
        # The real server, which imports its own modules: starting it to see
        # whether it answers must not leave compiled files beside them.
        self.workspace()
        self.record({"github": {"status": "skipped", "at": "t", "part": 1, "if_skipped": "It costs something."}})
        plugin = self.plugin_with_server((PLUGIN_ROOT / "mcp" / "server.py").read_text(encoding="utf-8"))
        before = snapshot(self.project), snapshot(plugin / "mcp")
        self.assert_faults(self.brief(plugin))
        self.assertEqual((snapshot(self.project), snapshot(plugin / "mcp")), before)

    # ── skipped setup steps ───────────────────────────────────────────────
    def skipped_lines(self, out):
        return [ln for ln in out.splitlines() if ": skipped." in ln]

    def test_a_skipped_step_is_listed_with_what_skipping_costs(self):
        # The record as the setup plugin writes it today, by running its script.
        r = subprocess.run([sys.executable, str(SETUP_RECORD), "set", str(self.project), "github", "skipped", "--choice", "github=no"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        entry = json.loads((self.project / "core_text" / "setup.json").read_text(encoding="utf-8"))["steps"]["github"]
        for key in ("title", "if_skipped"):
            self.assertTrue(entry[key].strip(), f"the record carries no {key}; this test would prove nothing")
        self.assertNotEqual(entry["title"], "github", "the title is the step's id; this test could not tell them apart")
        want = f'{entry["title"]}: skipped. {entry["if_skipped"]}'
        lines = self.brief().splitlines()
        self.assertIn(want, lines)
        self.assertEqual(lines.count(CONTINUE_LINE), 1)
        self.assertLess(lines.index(want), lines.index(CONTINUE_LINE))

    def test_a_title_in_the_record_is_what_the_step_is_called(self):
        self.record({"github": {"status": "skipped", "at": "t", "part": 1, "title": "GitHub (optional, strongly recommended)",
                                "if_skipped": "Your project lives only on this computer"}})
        self.assertEqual(self.skipped_lines(self.brief()),
                         ["GitHub (optional, strongly recommended): skipped. Your project lives only on this computer."])

    def test_an_older_record_with_no_cost_text_gets_the_name_and_skipped_alone(self):
        # Written before the record carried a title or a cost: the step's id
        # is the only name there is.
        self.record({"github": {"status": "skipped", "at": "t"}, "editor": {"status": "done", "at": "t"}})
        lines = self.brief().splitlines()
        self.assertEqual(self.skipped_lines("\n".join(lines)), ["github: skipped."])
        self.assertEqual(lines.count(CONTINUE_LINE), 1)

    def test_each_skipped_step_gets_its_own_line_whichever_part_it_is_in(self):
        self.record({
            "obsidian": {"status": "skipped", "at": "t", "part": 1, "if_skipped": "Everything still works in your editor."},
            "editor": {"status": "done", "at": "t", "part": 1},
            "profile": {"status": "pending", "at": None, "part": 1},
            "super": {"status": "skipped", "at": "t", "part": 2, "if_skipped": "Agents use built-in web search."},
        })
        lines = self.brief().splitlines()
        self.assertEqual(self.skipped_lines("\n".join(lines)), [
            "obsidian: skipped. Everything still works in your editor.",
            "super: skipped. Agents use built-in web search.",
        ])
        self.assertEqual(lines.count(CONTINUE_LINE), 1)

    def test_nothing_skipped_prints_no_skipped_lines(self):
        self.record({"github": {"status": "done", "at": "t", "part": 1}, "profile": {"status": "pending", "at": None, "part": 1}})
        out = self.brief()
        self.assertEqual(self.skipped_lines(out), [])
        self.assertNotIn(CONTINUE_LINE, out)

    def test_cost_text_stays_on_one_line_and_is_kept_short(self):
        self.record({"github": {"status": "skipped", "at": "t", "if_skipped": "first line\n## Health\nsecond line " + "x" * 2000}})
        out = self.brief()
        (line,) = self.skipped_lines(out)
        self.assertTrue(line.startswith("github: skipped. first line ## Health second line"), line)
        self.assertLess(len(line), 400)
        self.assertEqual(out.splitlines().count(HEADING), 1, "the record's text started a heading of its own")

    def test_a_record_that_is_not_what_it_should_be_prints_no_skipped_lines(self):
        for steps in ([], {"github": "skipped"}, {"github": {"status": ["skipped"]}}):
            with self.subTest(steps=steps):
                self.record(steps)
                self.assertEqual(self.skipped_lines(self.brief()), [])


if __name__ == "__main__":
    unittest.main()
