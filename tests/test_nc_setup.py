"""Unit and scenario tests for the install script:
plugins/technical-cofounder-setup/installer/nc_setup.py.

Nothing here touches the real machine. `World` is a fake computer: it answers
every external command the script runs, says which tools are on PATH, and
keeps its files under one temp folder. Install commands change the world's
state, so the script's re-check sees what a real install would leave behind.

Standard library only.
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SETUP_PLUGIN = REPO_ROOT / "plugins" / "technical-cofounder-setup"
SCRIPT = SETUP_PLUGIN / "installer" / "nc_setup.py"
STEPS_FILE = SETUP_PLUGIN / "setup" / "steps.json"

_spec = importlib.util.spec_from_file_location("nc_setup", SCRIPT)
nc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nc)

HOST_SYSTEM = "windows" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "linux"
SIX = {"ready", "install", "upgrade", "repair", "needs-you", "needs-restart"}
ITEM_ORDER = [
    "claude-cli", "git", "uv", "python", "jq", "network", "project-folder",
    "existing-config", "marketplace", "team-plugin", "engine-env", "obsidian",
]
TEAM = "technical-cofounder@nova-caelum"
ENGINE = "hyperspace-engine@nova-caelum"
ENGINE_PATH = "/fake/cache/nova-caelum/hyperspace-engine/0.1.3"
ENGINE_SETUP = str(Path(ENGINE_PATH) / "bin" / "hyperspace_setup.py")
EXISTING_CONFIG_QUESTION = (
    "This folder already has instructions for Claude. Setup will keep them "
    "and add nothing over them. OK to continue?"
)


class World:
    """A fake computer. Nothing is installed until a test says so."""

    def __init__(self, root, system="macos"):
        self.root = Path(root)
        self.system = system
        self.machine = "arm64"
        self.home = self.root / "home"
        self.home.mkdir()
        self.tools = self.root / "tools"
        self.apps = self.root / "Applications"
        (self.root / "work").mkdir()
        self.project = self.root / "work" / "my-project"
        # NC_PERSISTED_PATH is the saved PATH. It is always set here, so no
        # test ever reads the registry of the machine it runs on.
        self.env = {"PATH": "/fake/bin", "NC_PERSISTED_PATH": ""}
        self.python = "/fake/python/bin/python3.12"
        self.python_version = (3, 12, 4)
        self.missing_modules = set()
        self.on_path = {}          # tool name -> the path `which` answers
        self.tool_state = {}       # tool name -> "ok" | "broken" | "killed" | "timeout"
        self.clt = True            # Apple's command line tools present
        self.marketplaces = []
        self.plugins = []          # what `claude plugin list --json` prints
        self.env_state = {}        # project path -> "ok" | "broken" | "killed"
        self.network = (True, "HTTP 200")
        self.inert = set()         # installs that exit 0 and change nothing
        self.failing = set()       # installs that exit 1 and change nothing
        self.half_install = False  # the team arrives without its engine
        self.calls = []            # every command run
        self.cwds = []             # the folder each command ran in
        self.child_envs = []       # the environment each command got
        self.installs = []         # every command that would change the machine
        self.downloads = []
        self.log = []

    # -- what the script is given ------------------------------------------
    def overrides(self):
        return dict(
            runner=self.run, which=self.which, reach=self.reach,
            download=self.download, home=self.home, system=self.system,
            machine=self.machine, env=self.env, python=self.python,
            python_version=self.python_version, importer=self.importer,
            applications=self.apps, tools_dir=self.tools, log=self.log.append,
        )

    def which(self, name):
        return self.on_path.get(name)

    def reach(self, url, timeout):
        return self.network

    def importer(self, name):
        if name in self.missing_modules:
            raise ImportError("No module named %r" % name)

    def download(self, url, dest):
        self.installs.append("download")
        self.downloads.append(url)
        if "download" in self.failing:
            raise OSError("connection reset")
        if "download" not in self.inert:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text("fake jq\n")
            self.tool_state.setdefault("jq", "ok")

    # -- shortcuts for arranging a machine ----------------------------------
    def have(self, *names):
        for name in names:
            self.on_path[name] = "/fake/bin/" + name
            self.tool_state[name] = "ok"
        return self

    def plugin_entry(self, plugin_id, project=None, enabled=True, errors=None):
        entry = {
            "id": plugin_id, "version": "0.1.3", "scope": "project",
            "enabled": enabled, "projectPath": str(project or self.project),
            "installPath": ENGINE_PATH if plugin_id == ENGINE else "/fake/cache/team",
        }
        if errors:
            entry["errors"] = errors
        return entry

    def finished(self):
        """Everything setup installs is already here and working."""
        self.have("claude", "git", "uv", "jq")
        self.marketplaces = ["nova-caelum"]
        self.project.mkdir(parents=True, exist_ok=True)
        self.plugins = [self.plugin_entry(TEAM), self.plugin_entry(ENGINE)]
        self._build_env(self.project)
        return self

    def _build_env(self, project):
        env = Path(project) / ".hyperspace" / "env"
        if self.system == "windows":
            (env / "Scripts").mkdir(parents=True, exist_ok=True)
            (env / "Scripts" / "python.exe").write_text("fake\n")
            (env / "bin").mkdir(parents=True, exist_ok=True)
            (env / "bin" / "python.exe").write_text("fake\n")
        else:
            (env / "bin").mkdir(parents=True, exist_ok=True)
            (env / "bin" / "python").write_text("fake\n")
        self.env_state[str(project)] = "ok"

    def _land(self, name):
        exe = name + (".exe" if self.system == "windows" else "")
        target = self.home / ".local" / "bin" / exe
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fake\n")
        self.tool_state[name] = "ok"

    def _install(self, kind, effect):
        self.installs.append(kind)
        if kind in self.failing:
            return nc.Result(1, "", "%s: something went wrong" % kind)
        if kind not in self.inert:
            effect()
        return nc.Result(0, "done", "")

    # -- the one command runner the script gets -----------------------------
    def run(self, argv, cwd=None, env=None, timeout=60):
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        self.cwds.append(None if cwd is None else str(cwd))
        self.child_envs.append(env)
        name = argv[0].replace("\\", "/").rsplit("/", 1)[-1]
        if name.endswith(".exe"):
            name = name[:-4]
        rest = argv[1:]

        if name in ("bash", "sh", "powershell") and rest:
            script = rest[-1]
            if "claude.ai/install" in script:
                return self._install("claude-cli", lambda: self._land("claude"))
            if "astral.sh/uv/install" in script:
                return self._install("uv", lambda: self._land("uv"))
            return nc.Result(127, "", "unexpected shell script: " + script)

        if rest and rest[0].endswith("hyperspace_setup.py"):
            project = rest[rest.index("--dir") + 1]
            return self._install("engine-env", lambda: self._build_env(project))

        if rest == ["-c", "import hyperspace"]:
            project = argv[0].replace("\\", "/").split("/.hyperspace/")[0]
            state = self.env_state.get(str(Path(project)), "broken")
            if state == "ok":
                return nc.Result(0, "", "")
            if state == "killed":
                return nc.Result(-9, "", "")
            if state == "timeout":
                return nc.Result(124, "", "no answer within 60 seconds")
            return nc.Result(1, "", "ModuleNotFoundError: No module named 'hyperspace'")

        if name == "codesign":
            self.installs.append("codesign")
            target = rest[-1]
            for key, state in list(self.env_state.items()):
                if state == "killed" and target.startswith(os.path.realpath(key)):
                    self.env_state[key] = "ok"
            if self.tool_state.get("jq") == "killed" and target.endswith("jq"):
                self.tool_state["jq"] = "ok"
            return nc.Result(0, "", "")

        if name == "xcode-select":
            return nc.Result(0 if self.clt else 2, "/Library/Developer/CommandLineTools\n" if self.clt else "", "")

        if rest == ["--version"]:
            state = self.tool_state.get(name)
            if state == "ok":
                return nc.Result(0, "%s 1.2.3\n" % name, "")
            if state == "killed":
                return nc.Result(-9, "", "")
            if state == "timeout":
                return nc.Result(124, "", "timed out after 30s")
            return nc.Result(1, "", "%s: cannot run" % name)

        if name == "claude" and rest[:3] == ["plugin", "marketplace", "list"]:
            return nc.Result(0, json.dumps([{"name": n, "source": "github"} for n in self.marketplaces]), "")
        if name == "claude" and rest[:3] == ["plugin", "marketplace", "add"]:
            return self._install("marketplace", lambda: self.marketplaces.append("nova-caelum"))
        if name == "claude" and rest[:2] == ["plugin", "list"]:
            if "plugin-list" in self.failing:
                return nc.Result(1, "", "claude: could not read plugins")
            return nc.Result(0, json.dumps(self.plugins), "")
        if name == "claude" and rest[:2] == ["plugin", "install"]:
            def effect():
                self.plugins = [p for p in self.plugins if p["projectPath"] != str(cwd)]
                if self.half_install:
                    self.plugins.append(self.plugin_entry(
                        TEAM, cwd, errors=['Dependency "%s" is not installed' % ENGINE]))
                else:
                    self.plugins.append(self.plugin_entry(TEAM, cwd))
                    self.plugins.append(self.plugin_entry(ENGINE, cwd))
            return self._install("team-plugin", effect)

        return nc.Result(127, "", "unexpected command: " + " ".join(argv))


def snapshot(root):
    """Every file and folder under root, with size and modification time."""
    out = {}
    for path in sorted(Path(root).rglob("*")):
        st = path.lstat()
        out[path.relative_to(root).as_posix()] = (path.is_dir(), st.st_size if path.is_file() else 0, st.st_mtime_ns)
    return out


class Case(unittest.TestCase):
    system = "macos"

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.world = World(Path(self._td.name).resolve(), system=self.system)

    def call(self, *argv, world=None):
        world = world or self.world
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = nc.main([str(a) for a in argv], **world.overrides())
        text = out.getvalue()
        return code, (json.loads(text) if text.strip() else None)

    def plan(self, project=None):
        code, doc = self.call("plan", "--project", project or self.world.project)
        self.assertEqual(code, 0)
        return doc

    def row(self, item_id, project=None):
        rows = {r["id"]: r for r in self.plan(project)["items"]}
        return rows[item_id]

    def verdict(self, item_id, project=None):
        return self.row(item_id, project)["verdict"]

    def record_path(self):
        return self.world.project / "core_text" / "setup-scan.json"


# ---------------------------------------------------------------------------
# scan, plan and the record
# ---------------------------------------------------------------------------

class ScanIsReadOnly(Case):
    def test_scan_writes_nothing_on_an_empty_machine(self):
        before = snapshot(self.world.root)
        code, doc = self.call("scan", "--project", self.world.project)
        self.assertEqual(code, 0)
        self.assertEqual(snapshot(self.world.root), before)
        self.assertEqual(self.world.installs, [])
        self.assertEqual([i["id"] for i in doc["items"]], ITEM_ORDER)

    def test_scan_writes_nothing_on_a_finished_machine(self):
        self.world.finished()
        before = snapshot(self.world.root)
        code, _ = self.call("scan", "--project", self.world.project)
        self.assertEqual(code, 0)
        self.assertEqual(snapshot(self.world.root), before)
        self.assertEqual(self.world.installs, [])

    def test_scan_record_writes_only_the_record(self):
        self.world.finished()
        before = snapshot(self.world.root)
        code, doc = self.call("scan", "--project", self.world.project, "--record")
        self.assertEqual(code, 0)
        after = snapshot(self.world.root)
        added = sorted(set(after) - set(before))
        self.assertEqual(added, ["work/my-project/core_text", "work/my-project/core_text/setup-scan.json"])
        self.assertEqual(doc["recorded"], str(self.record_path()))

    def test_scan_record_needs_the_project_folder(self):
        before = snapshot(self.world.root)
        code, doc = self.call("scan", "--project", self.world.project, "--record")
        self.assertEqual(code, 0)
        self.assertEqual(snapshot(self.world.root), before)
        self.assertIsNone(doc["recorded"])

    def test_scan_record_never_writes_into_a_refused_folder(self):
        code, doc = self.call("scan", "--project", self.world.home, "--record")
        self.assertEqual(code, 0)
        self.assertFalse((self.world.home / "core_text").exists())
        self.assertIsNone(doc["recorded"])


class RecordShape(Case):
    def test_record_has_the_keys_the_briefing_reads(self):
        self.world.finished()
        self.call("scan", "--project", self.world.project, "--record")
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        for key in ("scanned_at", "platform", "restart_required", "tools", "items"):
            self.assertIn(key, record)
        self.assertRegex(record["scanned_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(record["platform"], "macos")
        self.assertIs(record["restart_required"], False)
        self.assertEqual(set(record["tools"]), {"python", "uv", "jq", "git", "claude"})
        self.assertEqual(record["tools"]["python"], self.world.python)
        self.assertEqual(record["tools"]["jq"], "/fake/bin/jq")
        self.assertEqual([i["id"] for i in record["items"]], ITEM_ORDER)
        for item in record["items"]:
            self.assertEqual(set(item), {"id", "verdict", "detail"})

    def test_a_missing_tool_is_null_in_the_record(self):
        self.world.project.mkdir(parents=True)
        self.call("scan", "--project", self.world.project, "--record")
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertIsNone(record["tools"]["jq"])
        self.assertIsNone(record["tools"]["claude"])


class PlanShape(Case):
    def test_every_item_gets_exactly_one_of_the_six_verdicts(self):
        for arrange in (lambda w: w, lambda w: w.finished()):
            world = World(Path(tempfile.mkdtemp(dir=self.world.root)))
            arrange(world)
            code, doc = self.call("plan", "--project", world.project, world=world)
            self.assertEqual(code, 0)
            self.assertEqual([r["id"] for r in doc["items"]], ITEM_ORDER)
            for row in doc["items"]:
                self.assertIn(row["verdict"], SIX)
                self.assertTrue(row["detail"].strip())
                self.assertNotIn("\n", row["detail"])

    def test_every_item_has_a_why_and_a_time_in_the_reasons_file(self):
        entries = {e["id"]: e for e in json.loads(STEPS_FILE.read_text(encoding="utf-8"))["install"]}
        self.assertEqual([i.id for i in nc.ITEMS], ITEM_ORDER)
        for item_id in ITEM_ORDER:
            self.assertIn(item_id, entries)
            self.assertTrue(entries[item_id]["why"].strip())
            self.assertIs(type(entries[item_id]["minutes"]), int)

    def test_every_plan_row_carries_its_why_and_minutes(self):
        entries = {e["id"]: e for e in json.loads(STEPS_FILE.read_text(encoding="utf-8"))["install"]}
        for row in self.plan()["items"]:
            self.assertEqual(row["why"], entries[row["id"]]["why"])
            self.assertEqual(row["minutes"], entries[row["id"]]["minutes"])
            self.assertTrue(row["title"].strip())

    def test_reasons_file_holds_the_guide_steps_beside_the_install_items(self):
        doc = json.loads(STEPS_FILE.read_text(encoding="utf-8"))
        self.assertTrue(doc["steps"], "the guide's steps live in the same file")
        for step in doc["steps"]:
            self.assertTrue(step["id"] and step["title"] and step["why"])
            self.assertIn(step["part"], (1, 2))
        self.assertTrue(doc["about"].strip())


class PlanOnWindows(Case):
    system = "windows"

    def test_git_gets_the_windows_reason(self):
        row = self.row("git")
        self.assertEqual(
            row["why"],
            "Installing Git because you're on Windows: it gives your team the command line its safety checks run in.",
        )


class Usage(Case):
    def test_bad_usage_exits_2(self):
        for argv in (
            [],
            ["scan"],
            ["frobnicate", "--project", "/x"],
            ["apply", "--project", "/x"],
            ["apply", "--project", "/x", "--item", "jq", "--all"],
            ["apply", "--project", "/x", "--item", "no-such-item"],
            ["ack", "--project", "/x"],
            ["ack", "--project", "/x", "--item", "jq"],
        ):
            with self.subTest(argv=argv):
                with contextlib.redirect_stderr(io.StringIO()):
                    code, _ = self.call(*argv)
                self.assertEqual(code, 2)
        self.assertEqual(self.world.installs, [])


# ---------------------------------------------------------------------------
# items that only look at the machine
# ---------------------------------------------------------------------------

class ProjectFolder(Case):
    def test_missing_folder_is_planned_and_existing_folder_is_ready(self):
        self.assertEqual(self.verdict("project-folder"), "install")
        self.world.project.mkdir(parents=True)
        self.assertEqual(self.verdict("project-folder"), "ready")

    def test_home_folder_is_refused(self):
        row = self.row("project-folder", self.world.home)
        self.assertEqual(row["verdict"], "needs-you")
        self.assertIn("home folder", row["detail"])

    def test_filesystem_root_is_refused(self):
        self.assertEqual(self.verdict("project-folder", "/"), "needs-you")

    def test_system_folders_are_refused(self):
        for path in ("/System", "/System/Library/x", "/usr", "/usr/local/project", "/etc", "/bin", "/Library/Stuff"):
            with self.subTest(path=path):
                row = self.row("project-folder", path)
                self.assertEqual(row["verdict"], "needs-you")
                self.assertIn("system folder", row["detail"])

    def test_top_level_folders_are_refused(self):
        for path in ("/var", "/tmp", "/opt", "/Users", "/brand-new"):
            with self.subTest(path=path):
                self.assertEqual(self.verdict("project-folder", path), "needs-you")

    def test_relative_path_is_refused(self):
        row = self.row("project-folder", "my-project")
        self.assertEqual(row["verdict"], "needs-you")
        self.assertIn("full path", row["detail"])

    def test_a_file_is_not_a_project_folder(self):
        target = self.world.root / "work" / "notes.txt"
        target.write_text("x")
        self.assertEqual(self.verdict("project-folder", target), "needs-you")

    def test_refusals_are_one_plain_sentence(self):
        for path in (self.world.home, "/", "/usr", "relative"):
            detail = self.row("project-folder", path)["detail"]
            self.assertNotIn("\n", detail)
            self.assertLess(len(detail), 200)


class ProjectFolderOnThisMachine(Case):
    """Real paths, read the way this machine reads paths."""
    system = HOST_SYSTEM

    def test_home_and_any_folder_that_contains_it_are_refused(self):
        self.assertEqual(self.verdict("project-folder", self.world.home), "needs-you")
        row = self.row("project-folder", self.world.home.parent)
        self.assertEqual(row["verdict"], "needs-you")
        self.assertIn("contains your home folder", row["detail"])

    def test_a_new_folder_beside_other_work_is_accepted_and_created(self):
        self.assertEqual(self.verdict("project-folder"), "install")
        code, doc = self.call("apply", "--project", self.world.project, "--item", "project-folder")
        self.assertEqual((code, doc["results"][0]["after"]), (0, "ready"))
        self.assertTrue(self.world.project.is_dir())

    def test_a_folder_inside_the_home_folder_is_accepted(self):
        self.assertEqual(self.verdict("project-folder", self.world.home / "projects" / "one"), "install")


class ProjectFolderOnWindows(Case):
    system = "windows"

    def test_windows_system_folders_and_drive_roots_are_refused(self):
        self.world.env.update({"SystemRoot": r"C:\Windows", "ProgramFiles": r"C:\Program Files"})
        for path in ("C:\\", r"C:\Windows", r"C:\Windows\Temp\x", r"C:\Program Files\MyProject",
                     r"c:\program files (x86)\thing", r"C:\ProgramData\x", "projects\\x"):
            with self.subTest(path=path):
                self.assertEqual(self.verdict("project-folder", path), "needs-you")

    def test_an_ordinary_windows_folder_is_accepted(self):
        self.assertEqual(self.verdict("project-folder", r"C:\Projects\my-project"), "install")


class ExistingConfig(Case):
    def test_nothing_there_is_ready(self):
        self.assertEqual(self.verdict("existing-config"), "ready")
        self.world.project.mkdir(parents=True)
        self.assertEqual(self.verdict("existing-config"), "ready")

    def test_claude_md_asks_the_one_question(self):
        self.world.project.mkdir(parents=True)
        (self.world.project / "CLAUDE.md").write_text("# mine\n")
        row = self.row("existing-config")
        self.assertEqual(row["verdict"], "needs-you")
        self.assertEqual(row["detail"], EXISTING_CONFIG_QUESTION)

    def test_a_rules_folder_asks_too(self):
        (self.world.project / ".claude" / "rules").mkdir(parents=True)
        self.assertEqual(self.verdict("existing-config"), "needs-you")

    def test_ack_turns_it_ready_and_is_remembered(self):
        self.world.project.mkdir(parents=True)
        (self.world.project / "CLAUDE.md").write_text("# mine\n")
        code, doc = self.call("ack", "--project", self.world.project, "--item", "existing-config")
        self.assertEqual(code, 0)
        self.assertEqual(doc["item"]["verdict"], "ready")
        self.assertEqual(self.verdict("existing-config"), "ready")
        self.assertEqual((self.world.project / "CLAUDE.md").read_text(), "# mine\n")
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertIn("existing-config", record["acknowledged"])

    def test_instructions_added_after_a_clean_first_record_do_not_ask_again(self):
        # Setup itself lays instructions down later; a re-scan must not then
        # ask the user about files setup put there.
        self.world.project.mkdir(parents=True)
        self.call("scan", "--project", self.world.project, "--record")
        (self.world.project / "CLAUDE.md").write_text("# laid down by setup\n")
        self.assertEqual(self.verdict("existing-config"), "ready")


class PythonItem(Case):
    def test_new_enough_python_with_its_modules_is_ready(self):
        self.assertEqual(self.verdict("python"), "ready")

    def test_old_python_needs_you(self):
        self.world.python_version = (3, 9, 6)
        row = self.row("python")
        self.assertEqual(row["verdict"], "needs-you")
        self.assertIn("3.9.6", row["detail"])

    def test_a_python_missing_a_module_needs_you(self):
        self.world.missing_modules = {"sqlite3"}
        row = self.row("python")
        self.assertEqual(row["verdict"], "needs-you")
        self.assertIn("sqlite3", row["detail"])


class Network(Case):
    def test_reachable_is_ready(self):
        self.assertEqual(self.verdict("network"), "ready")

    def test_unreachable_needs_you_and_names_the_address(self):
        self.world.network = (False, "no answer within 5 seconds")
        row = self.row("network")
        self.assertEqual(row["verdict"], "needs-you")
        self.assertIn("https://github.com", row["detail"])


class Obsidian(Case):
    def test_always_ready_with_one_of_three_details(self):
        row = self.row("obsidian")
        self.assertEqual((row["verdict"], row["detail"]), ("ready", "not installed"))
        (self.world.apps / "Obsidian.app").mkdir(parents=True)
        row = self.row("obsidian")
        self.assertEqual((row["verdict"], row["detail"]), ("ready", "installed"))
        (self.world.project / ".obsidian").mkdir(parents=True)
        row = self.row("obsidian")
        self.assertEqual((row["verdict"], row["detail"]), ("ready", "this folder is already a vault"))


class ObsidianOnWindows(Case):
    system = "windows"

    def test_found_under_local_app_data(self):
        local = self.world.root / "LocalAppData"
        (local / "Programs" / "Obsidian").mkdir(parents=True)
        self.world.env["LOCALAPPDATA"] = str(local)
        self.assertEqual(self.row("obsidian")["detail"], "installed")


# ---------------------------------------------------------------------------
# tools: Claude Code's command line, Git, uv, jq
# ---------------------------------------------------------------------------

class ClaudeCli(Case):
    def test_missing_is_install(self):
        self.assertEqual(self.verdict("claude-cli"), "install")

    def test_on_path_and_running_is_ready(self):
        self.world.have("claude")
        row = self.row("claude-cli")
        self.assertEqual(row["verdict"], "ready")
        self.assertIn("/fake/bin/claude", row["detail"])

    def test_found_in_the_per_user_folder_when_path_is_stale(self):
        self.world._land("claude")
        row = self.row("claude-cli")
        self.assertEqual(row["verdict"], "ready")
        self.assertIn(str(self.world.home / ".local" / "bin" / "claude"), row["detail"])

    def test_a_copy_that_does_not_run_is_repair(self):
        self.world.have("claude")
        self.world.tool_state["claude"] = "broken"
        self.assertEqual(self.verdict("claude-cli"), "repair")

    def test_a_copy_that_never_answers_needs_you(self):
        self.world.have("claude")
        self.world.tool_state["claude"] = "timeout"
        self.assertEqual(self.verdict("claude-cli"), "needs-you")


class ClaudeCliOnWindows(Case):
    system = "windows"

    def test_claude_exe_in_the_per_user_folder_is_ready(self):
        self.world._land("claude")
        self.assertTrue((self.world.home / ".local" / "bin" / "claude.exe").is_file())
        self.assertEqual(self.verdict("claude-cli"), "ready")


class GitOnMac(Case):
    def test_running_git_is_ready(self):
        self.world.have("git")
        self.assertEqual(self.verdict("git"), "ready")

    def test_no_command_line_tools_needs_you_with_the_one_command(self):
        self.world.on_path["git"] = "/usr/bin/git"   # Apple's stand-in, which opens a window when run
        self.world.clt = False
        row = self.row("git")
        self.assertEqual(row["verdict"], "needs-you")
        self.assertIn("xcode-select --install", row["detail"])
        self.assertNotIn(["/usr/bin/git", "--version"], self.world.calls)

    def test_git_that_never_answers_needs_you(self):
        self.world.have("git")
        self.world.tool_state["git"] = "timeout"
        self.assertEqual(self.verdict("git"), "needs-you")


class GitOnLinux(Case):
    system = "linux"

    def test_missing_git_needs_you(self):
        row = self.row("git")
        self.assertEqual(row["verdict"], "needs-you")
        self.assertIn("package manager", row["detail"])


class GitOnWindows(Case):
    system = "windows"
    STUB = r"C:\Windows\System32\bash.exe"

    def install_git(self, on_path=True):
        root = self.world.root / "ProgramFiles"
        (root / "Git" / "cmd").mkdir(parents=True)
        (root / "Git" / "bin").mkdir(parents=True)
        (root / "Git" / "cmd" / "git.exe").write_text("fake\n")
        (root / "Git" / "bin" / "bash.exe").write_text("fake\n")
        self.world.env["ProgramFiles"] = str(root)
        if on_path:
            self.world.on_path["git"] = str(root / "Git" / "cmd" / "git.exe")
            self.world.tool_state["git"] = "ok"
        return root

    def test_default_git_install_is_ready_even_though_bash_resolves_to_the_windows_stub(self):
        # Git for Windows puts only Git\cmd on PATH, so `bash` still finds
        # Windows' own stand-in. Git's bash.exe beside git.exe is what counts.
        self.install_git()
        self.world.on_path["bash"] = self.STUB
        self.assertEqual(self.verdict("git"), "ready")

    def test_git_bash_on_path_is_ready(self):
        self.world.have("git")
        self.world.on_path["bash"] = r"C:\Program Files\Git\usr\bin\bash.exe"
        self.assertEqual(self.verdict("git"), "ready")

    def test_windows_stub_bash_with_no_git_is_no_git(self):
        self.world.on_path["bash"] = self.STUB
        row = self.row("git")
        self.assertEqual(row["verdict"], "needs-you")
        self.assertIn("bootstrap.ps1", row["detail"])

    def test_a_git_with_only_the_windows_stub_for_bash_is_not_ready(self):
        self.world.have("git")
        self.world.on_path["bash"] = self.STUB
        row = self.row("git")
        self.assertEqual(row["verdict"], "needs-you")
        self.assertIn("bootstrap.ps1", row["detail"])

    # -- installed, but this session's PATH does not lead to it ---------------

    RESTART = (
        "Git is installed, but this session started before it was; close Claude Code completely, "
        "open it again, and paste the same message; if you started Claude Code from a terminal "
        "window, close that window too"
    )

    def unseen_git(self, runs=True):
        """A full Git for Windows that PATH does not lead to. Returns its
        cmd folder and its git.exe."""
        cmd = self.install_git(on_path=False) / "Git" / "cmd"
        if runs:
            self.world.tool_state["git"] = "ok"
        self.world.on_path["bash"] = self.STUB
        return str(cmd), str(cmd / "git.exe")

    def save_path(self, *folders):
        self.world.env["NC_PERSISTED_PATH"] = ";".join((r"C:\Windows\System32",) + folders)

    def test_git_kept_off_path_is_ready_and_used_where_it_is(self):
        # Git for Windows can be installed to stay off PATH. No restart ever
        # makes that one visible, so asking for one would loop forever.
        cmd, git = self.unseen_git()
        self.save_path(r"C:\Users\me\AppData\Local\Programs\Python")
        row = self.row("git")
        self.assertEqual(row["verdict"], "ready")
        self.assertIn(git, row["detail"])
        self.assertIn("used directly", row["detail"])
        self.assertIn([git, "--version"], self.world.calls)   # proven by running it, not by its file
        code, doc = self.call("scan", "--project", self.world.project)
        self.assertIs(doc["restart_required"], False)
        self.assertEqual(doc["tools"]["git"], git)

    def test_git_kept_off_path_goes_first_on_the_path_every_child_gets(self):
        # `claude plugin marketplace add` clones with whatever git its PATH
        # leads to, and that command is its own run of this script.
        cmd, git = self.unseen_git()
        self.world.have("claude")
        self.call("apply", "--project", self.world.project, "--item", "marketplace")
        add = self.world.calls.index(["/fake/bin/claude", "plugin", "marketplace", "add", nc.MARKETPLACE_SOURCE])
        self.assertEqual(self.world.child_envs[add]["PATH"].split(os.pathsep), [cmd, "/fake/bin"])

    def test_the_folder_is_put_on_path_once_however_often_git_is_checked(self):
        cmd, git = self.unseen_git()
        self.call("apply", "--project", self.world.project, "--all")
        self.call("plan", "--project", self.world.project)
        self.assertEqual(self.world.env["PATH"].split(os.pathsep), [cmd, "/fake/bin"])

    def test_git_on_the_saved_path_that_this_session_cannot_see_needs_restart(self):
        cmd, git = self.unseen_git()
        self.save_path(cmd.upper() + "\\")   # Windows ignores letter case and a trailing backslash
        row = self.row("git")
        self.assertEqual(row["verdict"], "needs-restart")
        self.assertEqual(row["detail"], self.RESTART)
        self.assertNotIn([git, "--version"], self.world.calls)
        self.assertEqual(self.world.env["PATH"], "/fake/bin")
        code, doc = self.call("scan", "--project", self.world.project)
        self.assertIs(doc["restart_required"], True)
        self.assertIsNone(doc["tools"]["git"])

    def test_the_saved_path_comes_from_the_registry_when_nothing_stands_in_for_it(self):
        cmd, git = self.unseen_git()
        del self.world.env["NC_PERSISTED_PATH"]
        with mock.patch.object(nc, "registry_path", return_value=r"C:\Windows;" + cmd):
            self.assertEqual(self.verdict("git"), "needs-restart")
        with mock.patch.object(nc, "registry_path", return_value=r"C:\Windows"):
            self.assertEqual(self.verdict("git"), "ready")

    def test_the_stand_in_wins_over_the_registry(self):
        cmd, git = self.unseen_git()
        self.save_path()
        with mock.patch.object(nc, "registry_path", side_effect=AssertionError("the registry was read")):
            self.assertEqual(self.verdict("git"), "ready")

    def test_a_git_kept_off_path_that_does_not_run_is_not_ready(self):
        cmd, git = self.unseen_git(runs=False)
        row = self.row("git")
        self.assertEqual(row["verdict"], "needs-you")
        self.assertIn(git, row["detail"])
        self.assertIn("does not run", row["detail"])
        self.assertIn("https://git-scm.com/downloads/win", row["detail"])

    def test_a_bare_git_on_path_gives_way_to_a_full_install_kept_off_path(self):
        # bootstrap.ps1 looks for an installed Git whenever the one on PATH
        # has no Git Bash, and uses it; this script has to agree.
        cmd, git = self.unseen_git()
        self.world.on_path["git"] = "/fake/bin/git"
        row = self.row("git")
        self.assertEqual(row["verdict"], "ready")
        self.assertIn(git, row["detail"])

    def test_an_unseen_install_with_no_git_bash_still_asks_for_a_restart(self):
        # Not one of the two cases above: this answer is the one it had.
        root = self.world.root / "ProgramFiles"
        (root / "Git" / "cmd").mkdir(parents=True)
        (root / "Git" / "cmd" / "git.exe").write_text("fake\n")
        self.world.env["ProgramFiles"] = str(root)
        self.world.on_path["bash"] = self.STUB
        row = self.row("git")
        self.assertEqual(row["verdict"], "needs-restart")
        self.assertEqual(row["detail"], self.RESTART)
        self.assertEqual(self.world.env["PATH"], "/fake/bin")


class FakeRegistry:
    """Stands in for the standard library's winreg module."""

    HKEY_LOCAL_MACHINE, HKEY_CURRENT_USER = "machine", "user"
    REG_SZ, REG_EXPAND_SZ = 1, 2

    def __init__(self, values):
        self.values = values   # (hive, key) -> (text, kind)
        self.asked = []

    @contextlib.contextmanager
    def OpenKey(self, hive, key):
        self.asked.append((hive, key))
        if (hive, key) not in self.values:
            raise FileNotFoundError(key)
        yield (hive, key)

    def QueryValueEx(self, handle, name):
        self.asked.append(name)
        return self.values[handle]

    def ExpandEnvironmentStrings(self, text):
        return text.replace("%SystemRoot%", r"C:\Windows")


class SavedPath(unittest.TestCase):
    MACHINE = ("machine", r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")
    USER = ("user", "Environment")

    def read(self, values):
        registry = FakeRegistry(values)
        with mock.patch.dict(sys.modules, {"winreg": registry}):
            return nc.registry_path(), registry

    def test_it_is_the_machines_path_then_the_users(self):
        text, registry = self.read({
            self.MACHINE: (r"C:\Windows\System32;C:\Program Files\Git\cmd", FakeRegistry.REG_SZ),
            self.USER: (r"C:\Users\me\.local\bin", FakeRegistry.REG_SZ),
        })
        self.assertEqual(text, r"C:\Windows\System32;C:\Program Files\Git\cmd;C:\Users\me\.local\bin")
        self.assertEqual(registry.asked, [self.MACHINE, "Path", self.USER, "Path"])

    def test_names_in_percent_signs_are_filled_in_as_powershell_does(self):
        text, _ = self.read({self.MACHINE: (r"%SystemRoot%\System32", FakeRegistry.REG_EXPAND_SZ)})
        self.assertEqual(text, r"C:\Windows\System32")

    def test_a_missing_key_is_skipped_not_an_error(self):
        text, _ = self.read({self.USER: (r"C:\Users\me\bin", FakeRegistry.REG_SZ)})
        self.assertEqual(text, r"C:\Users\me\bin")

    def test_no_registry_is_an_empty_path(self):
        with mock.patch.dict(sys.modules, {"winreg": None}):   # what `import winreg` meets off Windows
            self.assertEqual(nc.registry_path(), "")

    @unittest.skipUnless(sys.platform == "win32", "only Windows has a registry")
    def test_the_real_registry_answers_with_the_windows_folder_on_it(self):
        self.assertIn("system32", nc.registry_path().casefold())


class Uv(Case):
    def test_missing_is_install_and_present_is_ready(self):
        self.assertEqual(self.verdict("uv"), "install")
        self.world._land("uv")
        self.assertEqual(self.verdict("uv"), "ready")

    def test_uv_that_never_answers_needs_you(self):
        self.world.have("uv")
        self.world.tool_state["uv"] = "timeout"
        self.assertEqual(self.verdict("uv"), "needs-you")


class Jq(Case):
    def test_missing_is_install(self):
        self.assertEqual(self.verdict("jq"), "install")

    def test_on_path_is_ready(self):
        self.world.have("jq")
        self.assertEqual(self.verdict("jq"), "ready")

    def test_in_the_tools_folder_is_ready(self):
        self.world.tools.mkdir()
        (self.world.tools / "jq").write_text("fake\n")
        self.world.tool_state["jq"] = "ok"
        row = self.row("jq")
        self.assertEqual(row["verdict"], "ready")
        self.assertIn(str(self.world.tools / "jq"), row["detail"])

    def test_killed_on_launch_on_a_mac_is_repair(self):
        self.world.have("jq")
        self.world.tool_state["jq"] = "killed"
        self.assertEqual(self.verdict("jq"), "repair")

    def test_no_official_build_for_this_machine_needs_you(self):
        self.world.machine = "riscv64"
        self.world.system = "linux"
        row = self.row("jq")
        self.assertEqual(row["verdict"], "needs-you")
        self.assertIn("riscv64", row["detail"])

    def test_jq_that_never_answers_needs_you(self):
        self.world.have("jq")
        self.world.tool_state["jq"] = "timeout"
        self.assertEqual(self.verdict("jq"), "needs-you")


# ---------------------------------------------------------------------------
# the catalog, the team and the engine's workspace
# ---------------------------------------------------------------------------

class Marketplace(Case):
    def test_without_claude_it_waits_as_install(self):
        row = self.row("marketplace")
        self.assertEqual(row["verdict"], "install")

    def test_listed_is_ready_and_unlisted_is_install(self):
        self.world.have("claude")
        self.assertEqual(self.verdict("marketplace"), "install")
        self.world.marketplaces = ["some-other", "nova-caelum"]
        self.assertEqual(self.verdict("marketplace"), "ready")

    def test_a_similar_name_is_not_the_catalog(self):
        self.world.have("claude")
        self.world.marketplaces = ["nova-caelum-extras"]
        self.assertEqual(self.verdict("marketplace"), "install")

    def listing(self, entries):
        real = self.world.run

        def run(argv, **kw):
            if list(argv)[1:4] == ["plugin", "marketplace", "list"]:
                return nc.Result(0, json.dumps(entries), "")
            return real(argv, **kw)

        self.world.have("claude")
        self.world.run = run

    def test_the_catalog_is_known_by_its_name_whatever_address_it_was_added_from(self):
        # What `claude plugin marketplace list --json` prints for a catalog
        # added by its full address.
        self.listing([{"name": "nova-caelum", "source": "git",
                       "url": "https://github.com/Nova-Caelum/plugins.git", "installLocation": "/somewhere"}])
        self.assertEqual(self.verdict("marketplace"), "ready")

    def test_the_same_address_under_another_name_is_not_the_catalog(self):
        self.listing([{"name": "plugins", "source": "git", "url": "https://github.com/Nova-Caelum/plugins.git"}])
        self.assertEqual(self.verdict("marketplace"), "install")

    def test_an_unreadable_answer_needs_you(self):
        self.world.have("claude")
        real = self.world.run

        def garbled(argv, **kw):
            if list(argv)[1:4] == ["plugin", "marketplace", "list"]:
                return nc.Result(0, "Configured marketplaces:\n  nova-caelum\n", "")
            return real(argv, **kw)

        self.world.run = garbled
        self.assertEqual(self.verdict("marketplace"), "needs-you")


class TeamPlugin(Case):
    def arrange(self):
        self.world.have("claude")
        self.world.project.mkdir(parents=True)

    def test_waits_as_install_until_claude_and_the_folder_exist(self):
        self.assertEqual(self.verdict("team-plugin"), "install")
        self.world.have("claude")
        self.assertEqual(self.verdict("team-plugin"), "install")

    def test_both_enabled_is_ready(self):
        self.arrange()
        self.world.plugins = [self.world.plugin_entry(TEAM), self.world.plugin_entry(ENGINE)]
        self.assertEqual(self.verdict("team-plugin"), "ready")
        listing = [i for i, argv in enumerate(self.world.calls) if argv[1:] == ["plugin", "list", "--json"]]
        self.assertTrue(listing)
        self.assertEqual(self.world.cwds[listing[0]], str(self.world.project))

    def test_neither_is_install(self):
        self.arrange()
        self.assertEqual(self.verdict("team-plugin"), "install")

    def test_team_without_its_engine_is_repair(self):
        self.arrange()
        self.world.plugins = [self.world.plugin_entry(TEAM, errors=["Dependency is not installed"])]
        self.assertEqual(self.verdict("team-plugin"), "repair")

    def test_engine_without_the_team_is_repair(self):
        self.arrange()
        self.world.plugins = [self.world.plugin_entry(ENGINE)]
        self.assertEqual(self.verdict("team-plugin"), "repair")

    def test_one_switched_off_is_repair(self):
        self.arrange()
        self.world.plugins = [self.world.plugin_entry(TEAM), self.world.plugin_entry(ENGINE, enabled=False)]
        self.assertEqual(self.verdict("team-plugin"), "repair")

    def test_an_install_that_belongs_to_another_project_is_install_here(self):
        self.arrange()
        elsewhere = self.world.root / "work" / "other"
        self.world.plugins = [
            self.world.plugin_entry(TEAM, elsewhere, enabled=False),
            self.world.plugin_entry(ENGINE, elsewhere, enabled=False),
        ]
        self.assertEqual(self.verdict("team-plugin"), "install")

    def test_a_listing_that_fails_needs_you(self):
        self.arrange()
        self.world.failing.add("plugin-list")
        self.assertEqual(self.verdict("team-plugin"), "needs-you")


class EngineEnv(Case):
    def test_waits_as_install_until_it_is_built(self):
        self.assertEqual(self.verdict("engine-env"), "install")
        self.world.project.mkdir(parents=True)
        self.assertEqual(self.verdict("engine-env"), "install")

    def test_an_environment_that_imports_the_engine_is_ready(self):
        self.world.finished()
        self.assertEqual(self.verdict("engine-env"), "ready")

    def test_a_folder_that_cannot_import_the_engine_is_repair(self):
        self.world.finished()
        self.world.env_state[str(self.world.project)] = "broken"
        self.assertEqual(self.verdict("engine-env"), "repair")

    def test_an_interpreter_killed_on_launch_is_repair(self):
        self.world.finished()
        self.world.env_state[str(self.world.project)] = "killed"
        self.assertEqual(self.verdict("engine-env"), "repair")

    def test_an_empty_environment_folder_is_repair(self):
        (self.world.project / ".hyperspace" / "env").mkdir(parents=True)
        self.assertEqual(self.verdict("engine-env"), "repair")

    def test_an_environment_that_never_answers_needs_you(self):
        self.world.finished()
        self.world.env_state[str(self.world.project)] = "timeout"
        self.assertEqual(self.verdict("engine-env"), "needs-you")


class EngineEnvOnWindows(Case):
    system = "windows"

    def test_scripts_layout_with_the_bin_link_is_ready(self):
        self.world.finished()
        self.assertEqual(self.verdict("engine-env"), "ready")

    def test_missing_bin_link_is_repair(self):
        self.world.finished()
        (self.world.project / ".hyperspace" / "env" / "bin" / "python.exe").unlink()
        self.assertEqual(self.verdict("engine-env"), "repair")


class RunnerStripsTheSessionMarker(unittest.TestCase):
    def test_child_never_sees_claudecode_and_has_no_stdin(self):
        import sys
        result = nc.run_command(
            [sys.executable, "-c",
             "import os, sys; print(os.environ.get('CLAUDECODE')); print(repr(sys.stdin.read()))"],
            env=dict(os.environ, CLAUDECODE="1"), timeout=30,
        )
        self.assertEqual(result.code, 0, result.err)
        self.assertEqual(result.out.split(), ["None", "''"])

    def test_a_program_that_is_not_there_is_an_answer_not_a_crash(self):
        result = nc.run_command(["/no/such/program-for-nc-setup"])
        self.assertEqual(result.code, 127)


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

class ApplyItem(Case):
    def apply(self, item_id, project=None):
        return self.call("apply", "--project", project or self.world.project, "--item", item_id)

    def test_a_ready_item_runs_no_install_command_and_changes_no_file(self):
        self.world.finished()
        before = snapshot(self.world.root)
        for item_id in ITEM_ORDER:
            with self.subTest(item=item_id):
                code, doc = self.apply(item_id)
                self.assertEqual(code, 0)
                self.assertEqual(doc["results"], [dict(doc["results"][0], id=item_id, before="ready", after="ready", acted=False)])
        self.assertEqual(self.world.installs, [])
        self.assertEqual(snapshot(self.world.root), before)

    def test_the_recheck_decides_not_the_exit_code(self):
        # The install command exits 0 and changes nothing: that is not success.
        self.world.have("claude")
        self.world.inert.add("marketplace")
        code, doc = self.apply("marketplace")
        self.assertEqual(self.world.installs, ["marketplace"])
        result = doc["results"][0]
        self.assertTrue(result["acted"])
        self.assertNotEqual(result["after"], "ready")
        self.assertEqual(result["after"], "install")
        self.assertEqual(code, 1)
        self.assertIs(doc["failed"], True)

    def test_a_failing_command_is_reported_with_what_it_said(self):
        self.world.have("claude")
        self.world.project.mkdir(parents=True)
        self.world.failing.add("team-plugin")
        code, doc = self.apply("team-plugin")
        self.assertEqual(code, 1)
        self.assertIn("something went wrong", doc["results"][0]["detail"])

    def test_an_item_that_needs_the_user_is_left_alone(self):
        self.world.network = (False, "no answer within 5 seconds")
        code, doc = self.apply("network")
        self.assertEqual(code, 0)
        self.assertEqual(doc["results"][0]["after"], "needs-you")
        self.assertFalse(doc["results"][0]["acted"])
        self.assertIs(doc["failed"], False)
        self.assertEqual(self.world.installs, [])

    def test_claude_is_installed_and_found_without_a_fresh_path(self):
        code, doc = self.apply("claude-cli")
        self.assertEqual(code, 0)
        self.assertEqual(self.world.installs, ["claude-cli"])
        self.assertIn(["bash", "-c", "curl -fsSL https://claude.ai/install.sh | bash"], self.world.calls)
        result = doc["results"][0]
        self.assertEqual((result["before"], result["after"]), ("install", "ready"))
        self.assertIn(str(self.world.home / ".local" / "bin" / "claude"), result["detail"])
        self.assertIs(doc["restart_required"], True)

    def test_uv_is_installed_with_the_official_installer(self):
        code, doc = self.apply("uv")
        self.assertEqual(code, 0)
        self.assertIn(["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"], self.world.calls)
        self.assertEqual(doc["results"][0]["after"], "ready")
        self.assertIs(doc["restart_required"], False)

    def test_jq_is_downloaded_for_this_machine_made_runnable_and_proven(self):
        code, doc = self.apply("jq")
        self.assertEqual(code, 0)
        self.assertEqual(self.world.downloads, ["https://github.com/jqlang/jq/releases/latest/download/jq-macos-arm64"])
        target = self.world.tools / "jq"
        self.assertTrue(os.access(target, os.X_OK))
        self.assertIn([str(target), "--version"], self.world.calls)
        self.assertEqual(doc["results"][0]["after"], "ready")

    def test_jq_download_names_follow_the_machine(self):
        for system, machine, name in (
            ("macos", "amd64", "jq-macos-amd64"), ("linux", "amd64", "jq-linux-amd64"),
            ("linux", "arm64", "jq-linux-arm64"), ("windows", "amd64", "jq-windows-amd64.exe"),
        ):
            with self.subTest(system=system, machine=machine):
                world = World(Path(tempfile.mkdtemp(dir=self.world.root)), system=system)
                world.machine = machine
                world.have("git")
                code, _ = self.call("apply", "--project", world.project, "--item", "jq", world=world)
                self.assertEqual(code, 0)
                self.assertEqual(world.downloads, ["https://github.com/jqlang/jq/releases/latest/download/" + name])
                self.assertTrue((world.tools / ("jq.exe" if system == "windows" else "jq")).is_file())

    def test_a_download_that_fails_is_a_failed_item_not_a_crash(self):
        self.world.failing.add("download")
        code, doc = self.apply("jq")
        self.assertEqual(code, 1)
        self.assertIn("connection reset", doc["results"][0]["detail"])

    def test_jq_killed_on_launch_is_signed_again_once(self):
        self.world.have("jq")
        self.world.tool_state["jq"] = "killed"
        code, doc = self.apply("jq")
        self.assertEqual(code, 0)
        self.assertEqual(self.world.installs, ["codesign"])
        self.assertIn(["codesign", "--force", "-s", "-", os.path.realpath("/fake/bin/jq")], self.world.calls)
        self.assertEqual(doc["results"][0]["after"], "ready")

    def test_the_project_folder_is_created_with_its_parents(self):
        deep = self.world.root / "work" / "a" / "b" / "my-project"
        code, doc = self.apply("project-folder", deep)
        self.assertEqual(code, 0)
        self.assertTrue(deep.is_dir())
        self.assertEqual(doc["results"][0]["after"], "ready")

    def test_a_refused_folder_is_never_created_or_written_to(self):
        before = snapshot(self.world.root)
        code, doc = self.apply("project-folder", self.world.home)
        self.assertEqual(code, 0)
        self.assertEqual(doc["results"][0]["after"], "needs-you")
        self.assertEqual(snapshot(self.world.root), before)

    def test_the_catalog_comes_from_the_default_source_or_the_override(self):
        # The full address: the owner/name shorthand leaves the choice of
        # HTTPS or SSH to the machine, and a first-time user has no SSH key.
        self.world.have("claude")
        self.apply("marketplace")
        self.assertIn(
            ["/fake/bin/claude", "plugin", "marketplace", "add", "https://github.com/Nova-Caelum/plugins.git"],
            self.world.calls,
        )
        other = World(Path(tempfile.mkdtemp(dir=self.world.root)))
        other.have("claude")
        other.env["NC_MARKETPLACE_SOURCE"] = "/some/local/catalog"
        self.call("apply", "--project", other.project, "--item", "marketplace", world=other)
        self.assertIn(["/fake/bin/claude", "plugin", "marketplace", "add", "/some/local/catalog"], other.calls)

    def test_the_team_is_installed_from_the_project_folder_and_brings_the_engine(self):
        self.world.have("claude")
        self.world.project.mkdir(parents=True)
        code, doc = self.apply("team-plugin")
        self.assertEqual(code, 0)
        install = ["/fake/bin/claude", "plugin", "install", TEAM, "--scope", "project"]
        self.assertEqual(self.world.cwds[self.world.calls.index(install)], str(self.world.project))
        self.assertEqual(self.world.installs, ["team-plugin"])   # one command; the engine is its dependency
        self.assertEqual(doc["results"][0]["after"], "ready")
        self.assertIs(doc["restart_required"], True)

    def test_a_team_that_arrives_without_its_engine_is_not_ready(self):
        self.world.have("claude")
        self.world.project.mkdir(parents=True)
        self.world.half_install = True
        code, doc = self.apply("team-plugin")
        self.assertEqual(code, 1)
        self.assertEqual(doc["results"][0]["after"], "repair")

    def engine_world(self):
        self.world.finished()
        env = self.world.project / ".hyperspace" / "env"
        (env / "bin" / "python").unlink()
        (env / "bin").rmdir()
        env.rmdir()
        del self.world.env_state[str(self.world.project)]
        return env

    def test_the_engine_workspace_is_built_with_this_python_and_uv_in_front(self):
        self.engine_world()
        code, doc = self.apply("engine-env")
        self.assertEqual(code, 0)
        build = [self.world.python, ENGINE_SETUP,
                 "--dir", str(self.world.project), "--provision", "--judge", "none"]
        at = self.world.calls.index(build)
        child = self.world.child_envs[at]
        self.assertEqual(child["PATH"].split(os.pathsep)[0], os.path.dirname("/fake/bin/uv"))   # the folder holding uv
        self.assertNotIn("UV_VENV_CLEAR", child)
        self.assertEqual(self.world.cwds[at], str(self.world.project))
        self.assertEqual(doc["results"][0]["after"], "ready")
        self.assertIs(doc["restart_required"], True)

    def test_a_broken_workspace_is_rebuilt_and_keeps_the_judge_already_chosen(self):
        self.world.finished()
        self.world.env_state[str(self.world.project)] = "broken"
        (self.world.project / ".hyperspace" / "config.toml").write_text('judge = "openrouter"\nport = 8791\n')
        code, doc = self.apply("engine-env")
        self.assertEqual(code, 0)
        build = [c for c in self.world.calls if len(c) > 1 and c[1].endswith("hyperspace_setup.py")]
        self.assertEqual(len(build), 1)
        self.assertEqual(build[0][-2:], ["--judge", "openrouter"])
        child = self.world.child_envs[self.world.calls.index(build[0])]
        self.assertEqual(child.get("UV_VENV_CLEAR"), "1")   # uv will not build over an existing environment otherwise
        self.assertEqual(doc["results"][0]["before"], "repair")
        self.assertEqual(doc["results"][0]["after"], "ready")

    def test_a_workspace_python_killed_on_launch_is_signed_again_not_rebuilt(self):
        self.world.finished()
        self.world.env_state[str(self.world.project)] = "killed"
        code, doc = self.apply("engine-env")
        self.assertEqual(code, 0)
        self.assertEqual(self.world.installs, ["codesign"])
        self.assertEqual(doc["results"][0]["after"], "ready")

    def test_the_workspace_cannot_be_built_before_the_engine_is_installed(self):
        self.world.have("claude", "uv")
        self.world.project.mkdir(parents=True)
        code, doc = self.apply("engine-env")
        self.assertEqual(code, 1)
        self.assertEqual(self.world.installs, [])
        self.assertIn("install your team first", doc["results"][0]["detail"])

    def test_one_command_per_step_still_ends_with_restart_in_the_record(self):
        self.world.have("claude", "git", "uv", "jq")
        self.world.marketplaces = ["nova-caelum"]
        for item_id in ("project-folder", "team-plugin", "engine-env"):
            code, _ = self.apply(item_id)
            self.assertEqual(code, 0)
        code, doc = self.call("scan", "--project", self.world.project, "--record")
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertIs(record["restart_required"], True)
        self.assertEqual({i["verdict"] for i in record["items"]}, {"ready"})

    def test_progress_goes_to_the_log_with_the_plain_why(self):
        self.apply("jq")
        self.assertIn("Installing jq so your team's guardrails can read what's happening in a session.", self.world.log)


class ApplyAll(Case):
    FRESH_WALK = ["claude-cli", "uv", "download", "marketplace", "team-plugin", "engine-env"]

    def apply_all(self, project=None):
        return self.call("apply", "--project", project or self.world.project, "--all")

    def fresh(self):
        self.world.have("git")
        return self.world

    def test_a_fresh_machine_ends_all_ready_with_a_record(self):
        self.fresh()
        code, doc = self.apply_all()
        self.assertEqual(code, 0)
        self.assertEqual(self.world.installs, self.FRESH_WALK)
        self.assertIsNone(doc["stopped_at"])
        self.assertIs(doc["failed"], False)
        self.assertEqual([r["id"] for r in doc["results"]], ITEM_ORDER)
        self.assertEqual({r["after"] for r in doc["results"]}, {"ready"})
        self.assertTrue(self.world.project.is_dir())
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertIs(record["restart_required"], True)
        self.assertIs(doc["restart_required"], True)
        self.assertEqual({i["verdict"] for i in record["items"]}, {"ready"})
        self.assertEqual({r["verdict"] for r in self.plan()["items"]}, {"ready"})
        self.assertIsNone(self.plan()["next"])

    def test_a_second_run_installs_nothing_and_changes_no_file(self):
        self.fresh()
        self.apply_all()
        self.world.installs.clear()
        before = snapshot(self.world.root)
        code, doc = self.apply_all()
        self.assertEqual(code, 0)
        self.assertEqual(self.world.installs, [])
        self.assertEqual([r["acted"] for r in doc["results"]], [False] * len(ITEM_ORDER))
        self.assertEqual(snapshot(self.world.root), before)

    def test_it_stops_at_the_first_failure(self):
        self.fresh()
        self.world.inert.add("marketplace")
        code, doc = self.apply_all()
        self.assertEqual(code, 1)
        self.assertEqual(doc["stopped_at"], "marketplace")
        self.assertIs(doc["failed"], True)
        self.assertEqual(self.world.installs, ["claude-cli", "uv", "download", "marketplace"])
        self.assertEqual(doc["results"][-1]["id"], "marketplace")
        self.assertTrue(self.record_path().is_file())   # the re-scan still ran

    def test_it_stops_at_an_item_that_needs_the_user(self):
        self.fresh()
        self.world.network = (False, "no answer within 5 seconds")
        code, doc = self.apply_all()
        self.assertEqual(code, 0)
        self.assertEqual(doc["stopped_at"], "network")
        self.assertIs(doc["failed"], False)
        self.assertEqual(self.world.installs, ["claude-cli", "uv", "download"])
        self.assertFalse(self.world.project.exists())

    def test_it_stops_at_the_question_and_goes_on_after_a_yes(self):
        self.fresh()
        self.world.project.mkdir(parents=True)
        (self.world.project / "CLAUDE.md").write_text("# mine\n")
        code, doc = self.apply_all()
        self.assertEqual((code, doc["stopped_at"]), (0, "existing-config"))
        self.assertNotIn("marketplace", self.world.installs)
        self.call("ack", "--project", self.world.project, "--item", "existing-config")
        code, doc = self.apply_all()
        self.assertEqual((code, doc["stopped_at"]), (0, None))
        self.assertEqual((self.world.project / "CLAUDE.md").read_text(), "# mine\n")

    def test_a_refused_folder_stops_the_walk_before_anything_lands_in_it(self):
        self.fresh()
        code, doc = self.apply_all(self.world.home)
        self.assertEqual((code, doc["stopped_at"]), (0, "project-folder"))
        self.assertIsNone(doc["recorded"])
        self.assertFalse((self.world.home / "core_text").exists())
        self.assertFalse((self.world.home / ".claude").exists())

    def test_restart_required_describes_the_last_change_and_is_not_cleared_by_a_quiet_rescan(self):
        # Deliberate: a run that finds nothing new must not touch any file, and
        # it cannot know whether Claude Code was restarted since. The record
        # keeps saying "a restart was needed as of scanned_at".
        self.fresh()
        self.apply_all()
        first = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertIs(first["restart_required"], True)
        before = snapshot(self.world.root)
        code, doc = self.call("scan", "--project", self.world.project, "--record")
        self.assertEqual(code, 0)
        self.assertIs(doc["restart_required"], False)   # this run installed nothing
        self.assertEqual(snapshot(self.world.root), before)
        self.assertEqual(json.loads(self.record_path().read_text(encoding="utf-8")), first)

    def test_a_later_change_rewrites_the_record_with_its_own_restart_answer(self):
        self.fresh()
        self.apply_all()
        self.world.tool_state["jq"] = "broken"        # something breaks after the restart
        (self.world.tools / "jq").unlink()
        self.call("scan", "--project", self.world.project, "--record")
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertIs(record["restart_required"], False)
        self.assertEqual({i["id"]: i["verdict"] for i in record["items"]}["jq"], "install")

    def test_installing_only_jq_does_not_ask_for_a_restart(self):
        self.world.finished()
        del self.world.on_path["jq"]
        del self.world.tool_state["jq"]
        code, doc = self.apply_all()
        self.assertEqual(code, 0)
        self.assertEqual(self.world.installs, ["download"])
        self.assertIs(doc["restart_required"], False)
        self.assertIs(json.loads(self.record_path().read_text(encoding="utf-8"))["restart_required"], False)


class ApplyAllOnWindows(Case):
    system = "windows"

    def test_it_stops_at_git_that_needs_a_restart(self):
        # Git was installed after this session started: its folder is on the
        # saved PATH and not on this session's.
        root = self.world.root / "ProgramFiles"
        (root / "Git" / "cmd").mkdir(parents=True)
        (root / "Git" / "bin").mkdir(parents=True)
        (root / "Git" / "cmd" / "git.exe").write_text("fake\n")
        (root / "Git" / "bin" / "bash.exe").write_text("fake\n")
        self.world.env["ProgramFiles"] = str(root)
        self.world.env["NC_PERSISTED_PATH"] = str(root / "Git" / "cmd")
        code, doc = self.call("apply", "--project", self.world.project, "--all")
        self.assertEqual((code, doc["stopped_at"]), (0, "git"))
        self.assertEqual(doc["results"][-1]["after"], "needs-restart")
        self.assertIs(doc["restart_required"], True)
        self.assertEqual(self.world.installs, ["claude-cli"])
        self.assertIn(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
             "irm https://claude.ai/install.ps1 | iex"],
            self.world.calls,
        )


# ---------------------------------------------------------------------------
# when something goes wrong inside the script itself
# ---------------------------------------------------------------------------

class NeverReadyOnAnError(Case):
    def test_a_check_that_blows_up_is_needs_you_and_the_rest_still_run(self):
        self.world.have("claude", "git", "uv", "jq")
        real = self.world.run

        def flaky(argv, **kw):
            if str(argv[0]).endswith("uv"):
                raise RuntimeError("uv went sideways")
            return real(argv, **kw)

        self.world.run = flaky
        rows = {r["id"]: r for r in self.plan()["items"]}
        self.assertEqual(rows["uv"]["verdict"], "needs-you")
        self.assertIn("uv went sideways", rows["uv"]["detail"])
        self.assertEqual(rows["git"]["verdict"], "ready")
        self.assertEqual(rows["jq"]["verdict"], "ready")

    def test_a_fix_that_blows_up_is_a_failed_item_with_the_reason(self):
        def broken_download(url, dest):
            raise RuntimeError("disk on fire")

        self.world.download = broken_download
        code, doc = self.call("apply", "--project", self.world.project, "--item", "jq")
        self.assertEqual(code, 1)
        self.assertEqual(doc["results"][0]["after"], "install")
        self.assertIn("disk on fire", doc["results"][0]["detail"])

    def test_an_unexpected_error_still_prints_one_json_document_and_exits_1(self):
        with mock.patch.object(nc, "STEPS_FILE", self.world.root / "no-such-steps.json"):
            with contextlib.redirect_stderr(io.StringIO()):
                code, doc = self.call("plan", "--project", self.world.project)
        self.assertEqual(code, 1)
        self.assertEqual(doc["command"], "plan")
        self.assertIn("no-such-steps.json", doc["error"])

    def test_a_record_that_cannot_be_written_is_an_error_not_a_silent_success(self):
        self.world.finished()
        (self.world.project / "core_text").write_text("a file where the folder should be")
        with contextlib.redirect_stderr(io.StringIO()):
            code, doc = self.call("scan", "--project", self.world.project, "--record")
        self.assertEqual(code, 1)
        self.assertIn("error", doc)


class OldPythonGetsAPlainAnswer(unittest.TestCase):
    """The script must still start on a Python older than 3.11, so the python
    item can say so in one sentence instead of dying on a syntax error."""

    def test_the_python_check_runs_and_refuses_on_an_old_interpreter(self):
        old = None
        for candidate in ("/usr/bin/python3", "/usr/bin/python3.9", "/usr/bin/python3.10"):
            if not os.path.exists(candidate):
                continue
            probe = subprocess.run([candidate, "-c", "import sys; print(sys.version_info >= (3, 11))"],
                                   capture_output=True, text=True, stdin=subprocess.DEVNULL)
            if probe.returncode == 0 and probe.stdout.strip() == "False":
                old = candidate
                break
        if old is None:
            self.skipTest("no interpreter older than 3.11 on this machine")
        code = (
            "import importlib.util, sys\n"
            "spec = importlib.util.spec_from_file_location('nc_setup', sys.argv[1])\n"
            "nc = importlib.util.module_from_spec(spec); spec.loader.exec_module(nc)\n"
            "print(*nc.check_python(nc.Ctx('/tmp/x')), sep='|')\n"
        )
        result = subprocess.run([old, "-c", code, str(SCRIPT)], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        verdict, _, detail = result.stdout.strip().partition("|")
        self.assertEqual(verdict, "needs-you")
        self.assertIn("3.11 or newer", detail)


if __name__ == "__main__":
    unittest.main()
