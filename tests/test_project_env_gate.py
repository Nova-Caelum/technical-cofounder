"""Nothing Technical Cofounder starts may run a project's .hyperspace/env that
setup did not build on this computer.

A downloaded or cloned folder can ship a file at .hyperspace/env/bin/python
(and, for Windows, bin/python.exe and Scripts/python.exe). Every place the
team plugin can start the project's environment is driven here against such a
folder, the way it really runs, and the planted interpreter writes one line to
a file outside the project each time it is started. The count must be zero:

  starter 1  the team's server: the command .mcp.json declares, started the way
             Claude Code starts it
  starter 3  the session briefing (hooks/session-preload.sh), set up or not
  E          bin/he_bridge.py preload, the briefing's worklog block
  F          bin/drive_map_pointer.py preload, the briefing's drive map
  H          the server's worklog tools, whose `root` comes from the model

An environment that setup did build and recorded (launch_env.register, which
the engine's setup calls) still starts, at each of the same places. HOME is a
scratch folder throughout, so this machine's own record decides nothing.

Last, what Anthropic's directory scanner reads: every server command is a file
inside the plugin named from ${CLAUDE_PLUGIN_ROOT}, no hook feeds a heredoc to
an interpreter held in a variable, and bin/launch_env.py is the engine's
launcher byte for byte. Standard library only.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from tests.test_health_briefing import ENGINE_LINE, SERVER_LINE, UNKNOWN_LINE  # noqa: E402
from tests.test_plugin_hooks import BASH, LAUNCH_ENV, PLUGIN_ROOT, launch_env, register_env, write_tool  # noqa: E402

PLUGINS = REPO_ROOT / "plugins"
BRIDGE = PLUGIN_ROOT / "bin" / "he_bridge.py"
POINTER = PLUGIN_ROOT / "bin" / "drive_map_pointer.py"
PRELOAD = PLUGIN_ROOT / "hooks" / "session-preload.sh"
SERVER = PLUGIN_ROOT / "mcp" / "server.py"
ENTRY = PLUGIN_ROOT / "bin" / "hyperspace-env"
ENGINE_LAUNCHER = REPO_ROOT.parent / "hyperspace-engine" / "hyperspace" / "provenance.py"
TEAM_ID, ENGINE_ID = "technical-cofounder@nova-caelum", "hyperspace-engine@nova-caelum"
PLANTED = ("bin/python", "bin/python.exe", "Scripts/python.exe")
ROOT_PREFIX = "${CLAUDE_PLUGIN_ROOT}/"

INITIALIZE = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "env-gate", "version": "1"}}}) + "\n"
# The engine's drive_map.py `tree`, as far as the drive-map rebuild relies on it: it writes
# --out and says how many folders it found. It records being run beside itself.
STUB_ENGINE = """import json, sys
from pathlib import Path
args = sys.argv[1:]
Path(__file__).with_name("argv.json").write_text(json.dumps(args))
out = Path(args[args.index("--out") + 1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("# Drive map\\n")
print("wrote %s (3 folders, 1 files, 2 lines)" % out)
"""


def server_command(spec, environ):
    """The command Claude Code starts for a stdio server: each ${NAME} filled from the
    server's environment, and on Windows an extensionless file resolved to the .cmd
    beside it (PATHEXT), which is the file Claude Code runs there."""
    def fill(text):
        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", lambda m: environ.get(m.group(1), ""), str(text))

    argv = [fill(spec["command"])] + [fill(arg) for arg in spec.get("args") or []]
    if os.name == "nt" and not Path(argv[0]).suffix and Path(argv[0] + ".cmd").is_file():
        argv[0] = os.path.normpath(argv[0] + ".cmd")
    return argv


class Scratch:
    """A folder as it can arrive from somewhere else: the team and the engine switched on
    in its own settings, set up (a profile, a store, an engine config), and a planted
    .hyperspace/env whose three interpreters write to `marker`. HOME has no record. The
    engine is installed where Claude Code records a plugin, so the drive-map rebuild
    really reaches its start."""

    def __init__(self, test):
        self.base = Path(tempfile.mkdtemp(prefix="env gate "))
        test.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.home = self.base / "home"
        self.home.mkdir()
        self.project = self.base / "a project"
        self.marker = self.base / "planted-started.log"
        self.started = self.base / "recorded-env-started.log"
        self.write(".claude/settings.json", json.dumps({"enabledPlugins": {TEAM_ID: True, ENGINE_ID: True}}))
        self.write("core_text/user.md", "# a profile\n")
        self.write(".hyperspace/graph.db", "")
        self.write(".hyperspace/config.toml", 'judge = "none"\nport = 8791\n')
        body = '#!/bin/sh\necho "started: $0 $*" >> "%s"\nexit 0\n' % self.marker.as_posix()
        for rel in PLANTED:
            write_tool(self.env / rel, body)
        self.write(".hyperspace/env/pyvenv.cfg", "home = /usr/bin\nversion = 3.12.0\n")
        self.plugins = self.base / "plugins"
        self.engine = self.plugins / "cache" / "nova-caelum" / "hyperspace-engine" / "1.0.3"
        (self.engine / "bin").mkdir(parents=True)
        (self.engine / "bin" / "drive_map.py").write_text(STUB_ENGINE, encoding="utf-8")
        installs = {ENGINE_ID: [{"scope": "project", "installPath": str(self.engine), "projectPath": str(self.project),
                                 "version": "1.0.3"}]}
        (self.plugins / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": installs}), encoding="utf-8")

    @property
    def env(self):
        return self.project / ".hyperspace" / "env"

    def write(self, rel, text):
        path = self.project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def recorded(self):
        """Swap the planted environment for one setup built: a real virtual environment,
        recorded under this HOME. A .pth file in its site-packages writes to `started`
        whenever it starts with its site-packages loaded, which every real use does."""
        shutil.rmtree(self.env)
        venv.EnvBuilder(with_pip=False, symlinks=os.name != "nt").create(self.env)
        site = next(path for path in self.env.rglob("site-packages") if path.is_dir())
        (site / "zz_env_gate.pth").write_text("import os; open(%r, 'a').write('started\\n')\n" % str(self.started),
                                              encoding="utf-8")
        register_env(self.project, self.home)

    def environ(self, **extra):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("CLAUDE") and k not in ("NC_TOOLS_DIR", "VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH")}
        env.update(HOME=str(self.home), USERPROFILE=str(self.home), CLAUDE_PROJECT_DIR=str(self.project),
                   CLAUDE_PLUGIN_ROOT=str(PLUGIN_ROOT), CLAUDE_CODE_PLUGIN_CACHE_DIR=str(self.plugins),
                   PYTHONDONTWRITEBYTECODE="1")
        env.update(extra)
        return env

    def run(self, argv, text_in=""):
        """Start a program in the project folder; its input is `text_in`, then closed."""
        return subprocess.run([str(a) for a in argv], input=text_in, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=self.environ(), cwd=str(self.project), timeout=120)

    def in_process(self):
        """This process's environment, pointed at the scratch HOME and project."""
        return mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home),
                                            "CLAUDE_PROJECT_DIR": str(self.project)})

    def team_server(self, text_in=""):
        """Starter 1: the team's server, as .mcp.json declares it and Claude Code starts it."""
        spec = json.loads((PLUGIN_ROOT / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["caelum-dev-team"]
        return self.run(server_command(spec, self.environ()), text_in)

    def briefing(self):
        """Starter 3: the session briefing, run under bash with the event on its input."""
        return self.run([BASH, PRELOAD], "{}")

    def planted_starts(self):
        return self.marker.read_text(encoding="utf-8").splitlines() if self.marker.exists() else []


def load_server():
    """The team's server, in this process: the worklog tools call he_bridge here."""
    spec = importlib.util.spec_from_file_location("env_gate_server", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Gate(unittest.TestCase):
    def setUp(self):
        self.s = Scratch(self)

    def assertNeverStarted(self):
        self.assertEqual(self.s.planted_starts(), [], "the folder's own interpreter was started")

    def refused_line(self):
        return launch_env().REFUSED_LINE


class TheTeamsServer(_Gate):
    """Starter 1."""

    def test_a_folder_that_setup_did_not_build_is_refused_and_nothing_in_it_runs(self):
        done = self.s.team_server(INITIALIZE)
        self.assertNeverStarted()
        self.assertEqual(done.returncode, 3, done.stderr)
        self.assertIn(self.refused_line(), done.stderr)
        self.assertEqual(done.stdout, "", "a refused server answers nothing")

    def test_an_environment_setup_recorded_starts_and_answers(self):
        self.s.recorded()
        done = self.s.team_server(INITIALIZE)
        self.assertEqual(done.returncode, 0, done.stderr)
        reply = json.loads(done.stdout.splitlines()[0])
        self.assertEqual(reply["result"]["serverInfo"]["name"], "caelum-dev-team")
        self.assertTrue(self.s.started.exists(), "the server did not run in the recorded environment")


class TheSessionBriefing(_Gate):
    """Starter 3, and in a set-up project E and F through it."""

    def health(self, out):
        return [line for line in out.splitlines() if line in (UNKNOWN_LINE, ENGINE_LINE, SERVER_LINE)]

    def test_a_folder_not_set_up_starts_nothing_and_names_the_repair(self):
        (self.s.project / "core_text" / "user.md").unlink()
        done = self.s.briefing()
        self.assertNeverStarted()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.health(done.stdout), [UNKNOWN_LINE], done.stdout)

    def test_a_set_up_folder_starts_nothing_and_names_the_repair(self):
        done = self.s.briefing()
        self.assertNeverStarted()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.health(done.stdout), [UNKNOWN_LINE], done.stdout)
        self.assertIn("## user.md", done.stdout)

    def test_an_environment_setup_recorded_is_started_and_reads_healthy(self):
        (self.s.project / "core_text" / "user.md").unlink()  # the health probe alone
        self.s.recorded()
        done = self.s.briefing()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.health(done.stdout), [], done.stdout)
        self.assertTrue(self.s.started.exists(), "the health probe never started the team's server")


class TheWorklogBlock(_Gate):
    """E: bin/he_bridge.py preload, which the briefing runs in a set-up project."""

    def preload(self):
        return self.s.run([sys.executable, BRIDGE, "preload", self.s.project])

    def test_a_folder_that_setup_did_not_build_is_refused_and_nothing_is_written(self):
        config = (self.s.project / ".hyperspace" / "config.toml").read_text(encoding="utf-8")
        done = self.preload()
        self.assertNeverStarted()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(self.refused_line(), done.stdout)
        self.assertEqual((self.s.project / ".hyperspace" / "config.toml").read_text(encoding="utf-8"), config)

    def test_an_environment_setup_recorded_is_started(self):
        self.s.recorded()
        done = self.preload()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn(self.refused_line(), done.stdout)
        self.assertIn("exit 1", done.stdout, "the CLI was not reached (this venv has no hyperspace package)")
        self.assertTrue(self.s.started.exists(), "the bridge never started the recorded environment")


class TheDriveMap(_Gate):
    """F: bin/drive_map_pointer.py preload, which the briefing runs in a set-up project."""

    def preload(self):
        return self.s.run([sys.executable, POINTER, "preload", self.s.project])

    def test_a_folder_that_setup_did_not_build_is_refused_quietly(self):
        done = self.preload()
        self.assertNeverStarted()
        self.assertEqual((done.returncode, done.stdout), (0, ""), done.stderr)
        lines = [ln for ln in done.stderr.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, done.stderr)
        self.assertIn("not built by setup on this computer", lines[0])
        self.assertFalse((self.s.engine / "bin" / "argv.json").exists(), "the engine's script was run")

    def test_an_environment_setup_recorded_runs_the_engine(self):
        self.s.recorded()
        done = self.preload()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.startswith("Drive map: core_text/drive-map.md (3 folders)"), done.stdout + done.stderr)
        self.assertTrue(self.s.started.exists(), "the drive map was not built by the recorded environment")


class TheWorklogTools(_Gate):
    """H: the server's worklog tools. `root` comes from the model, so a server started for
    one project can be pointed at any folder; the check runs on every call."""

    def test_a_folder_that_setup_did_not_build_is_refused_and_nothing_is_written(self):
        self.s.write(".hyperspace/config.toml", 'judge = "none"\nworklog_owner = "technical-cofounder"\n')
        server = load_server()
        with self.s.in_process():
            for name, arguments in (("worklog_append", {"summary": "x"}), ("worklog_recent", {}),
                                    ("worklog_search", {"query": "x"})):
                with self.subTest(tool=name):
                    with self.assertRaises(Exception) as caught:
                        server._call_tool(name, dict(arguments, root=str(self.s.project)))
                    self.assertIn(self.refused_line(), str(caught.exception))
        self.assertNeverStarted()
        self.assertFalse((self.s.project / "worklog").exists(), "a refused call wrote a worklog")

    def test_the_bridge_refuses_the_same_way(self):
        server = load_server()  # puts bin/ on sys.path, as the running server has it
        with self.s.in_process():
            with self.assertRaises(server.he_bridge.BridgeError) as caught:
                server.he_bridge.append(self.s.project, "x")
        self.assertNeverStarted()
        self.assertIn(self.refused_line(), str(caught.exception))

    def test_an_environment_setup_recorded_is_started(self):
        self.s.recorded()
        server = load_server()
        with self.s.in_process():
            with self.assertRaises(server.he_bridge.BridgeError) as caught:
                server.he_bridge.run_cli(self.s.project, "recent")
        self.assertIn("exit 1", str(caught.exception), "the CLI was not reached (this venv has no hyperspace package)")
        self.assertNotIn(self.refused_line(), str(caught.exception))
        self.assertTrue(self.s.started.exists(), "the bridge never started the recorded environment")


class WhatTheDirectoryScannerReads(unittest.TestCase):
    """Anthropic's directory: COMMAND_PATH_COMPUTED and UNPINNED_NPX."""

    def test_every_server_command_is_a_file_in_the_plugin_named_from_its_root(self):
        found = 0
        for manifest in sorted(PLUGINS.glob("*/.mcp.json")):
            for name, spec in json.loads(manifest.read_text(encoding="utf-8"))["mcpServers"].items():
                if "command" not in spec:
                    continue  # a remote server: nothing is started on this computer
                found += 1
                with self.subTest(plugin=manifest.parent.name, server=name):
                    command = spec["command"]
                    self.assertTrue(command.startswith(ROOT_PREFIX), command)
                    rest = command[len(ROOT_PREFIX):]
                    self.assertNotIn("${", rest)
                    self.assertNotRegex(rest, r"[$*?`\s]")
                    self.assertTrue((manifest.parent / rest).is_file(), "%s is not a file in the plugin" % rest)
        self.assertGreater(found, 0, "no server command was checked")

    def test_no_shell_script_feeds_a_heredoc_to_an_interpreter_held_in_a_variable(self):
        computed = re.compile(r'\$\{?[A-Za-z_][A-Za-z0-9_]*\}?"?[^<\n]*<<(?!<)')
        found = []
        for script in sorted(PLUGINS.rglob("*.sh")):
            for number, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
                if computed.search(line):
                    found.append("%s:%d: %s" % (script.relative_to(REPO_ROOT).as_posix(), number, line.strip()))
        self.assertEqual(found, [])

    def test_the_entry_file_is_a_posix_script_with_a_windows_twin(self):
        script = ENTRY.read_bytes()
        self.assertTrue(script.startswith(b"#!/bin/sh\n"))
        self.assertNotIn(b"\r", script)
        twin = ENTRY.with_name("hyperspace-env.cmd").read_bytes()
        lines = twin.split(b"\n")
        self.assertEqual(lines[-1], b"", "the .cmd ends with a line break")
        self.assertEqual([ln for ln in lines[:-1] if not ln.endswith(b"\r")], [], "every .cmd line ends CRLF")
        listed = subprocess.run(["git", "ls-files", "-s", "--", str(ENTRY.relative_to(REPO_ROOT).as_posix())],
                                cwd=str(REPO_ROOT), capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if listed.returncode != 0 or not listed.stdout:
            self.skipTest("not a Git checkout, or the entry file is not committed yet")
        self.assertTrue(listed.stdout.startswith("100755 "), listed.stdout)

    def test_the_launcher_is_the_engines_byte_for_byte(self):
        if not ENGINE_LAUNCHER.is_file():
            self.skipTest("no Hyperspace Engine checkout beside this one; the install walk compares the pinned release")
        self.assertEqual(LAUNCH_ENV.read_bytes(), ENGINE_LAUNCHER.read_bytes())


if __name__ == "__main__":
    unittest.main()
