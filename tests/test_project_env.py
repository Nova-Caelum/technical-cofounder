"""Unit tests for the cofounder MCP launch: bin/project_env.py (the project's
own Python environment, .cofounder/env), the one command .mcp.json names for
every OS, and the preload line that says when that environment is missing.

Standard library only. Real environments are created in temp projects whose
path contains a space.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "base-novacaelum"
SCRIPT = PLUGIN_ROOT / "bin" / "project_env.py"
sys.path.insert(0, str(PLUGIN_ROOT / "bin"))
sys.path.insert(0, str(REPO_ROOT))

import project_env  # noqa: E402
from tests.test_template_hooks import BASH  # noqa: E402

MCP_COMMAND = "${CLAUDE_PROJECT_DIR}/.cofounder/env/bin/python"
MCP_ARGS = ["${CLAUDE_PLUGIN_ROOT}/mcp/server.py"]


def cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True,
                          encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=300)


class Project(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.project = tmp / "a project"
        self.project.mkdir()


class CreateTests(Project):
    def test_creates_an_env_whose_portable_python_runs(self):
        r = cli(self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ENV_OK", r.stdout)
        env = self.project / ".cofounder" / "env"
        out = subprocess.run([str(env / "bin" / "python"), "-c", "import sys; print(sys.prefix)"],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(Path(out.stdout.strip()).resolve(), env.resolve())

    def test_second_run_leaves_the_env_alone(self):
        self.assertEqual(cli(self.project).returncode, 0)
        cfg = self.project / ".cofounder" / "env" / "pyvenv.cfg"
        before = cfg.stat().st_mtime_ns
        r = cli(self.project)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("already", r.stdout)
        self.assertEqual(cfg.stat().st_mtime_ns, before)

    def test_env_stays_out_of_git(self):
        cli(self.project)
        self.assertEqual((self.project / ".cofounder" / ".gitignore").read_text(encoding="utf-8"), "env/\n")

    def test_usage(self):
        self.assertEqual(cli().returncode, 2)


class WindowsLinkTests(Project):
    """The Windows branch, driven on any OS with a fake junction maker."""

    def native(self):
        exe = self.project / "env" / "Scripts" / "python.exe"
        exe.parent.mkdir(parents=True)
        exe.write_text("", encoding="utf-8")
        return self.project / "env"

    def test_posix_needs_no_link(self):
        ok, msg = project_env.link_bin_to_scripts(self.project / "env", platform="linux")
        self.assertTrue(ok, msg)

    def test_windows_links_bin_to_scripts(self):
        env = self.native()
        made = []

        def junction(target, link):
            made.append((target, link))
            shutil.copytree(target, link)  # stands in for the junction on any OS

        ok, msg = project_env.link_bin_to_scripts(env, platform="win32", create_junction=junction)
        self.assertTrue(ok, msg)
        self.assertEqual(made, [(str(env / "Scripts"), str(env / "bin"))])
        self.assertTrue((env / "bin" / "python.exe").is_file())
        ok, _ = project_env.link_bin_to_scripts(env, platform="win32", create_junction=junction)
        self.assertTrue(ok)
        self.assertEqual(len(made), 1, "an existing link is left alone")

    def test_windows_refuses_a_bin_that_is_not_the_link(self):
        env = self.native()
        (env / "bin").mkdir()
        ok, msg = project_env.link_bin_to_scripts(env, platform="win32", create_junction=lambda t, l: None)
        self.assertFalse(ok)
        self.assertIn("bin", msg)


class McpLaunchTests(Project):
    def test_mcp_json_names_the_project_env(self):
        server = json.loads((PLUGIN_ROOT / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["cofounder"]
        self.assertEqual(server["command"], MCP_COMMAND)
        self.assertEqual(server["args"], MCP_ARGS)

    def test_the_mcp_json_command_serves_initialize_after_setup(self):
        self.assertEqual(cli(self.project).returncode, 0)
        subst = {"${CLAUDE_PROJECT_DIR}": self.project.as_posix(), "${CLAUDE_PLUGIN_ROOT}": PLUGIN_ROOT.as_posix()}

        def expand(value):
            for key, val in subst.items():
                value = value.replace(key, val)
            return value

        request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2026-06-18"}}
        r = subprocess.run([expand(MCP_COMMAND), *map(expand, MCP_ARGS)], input=json.dumps(request) + "\n",
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(json.loads(r.stdout)["result"]["serverInfo"]["name"], "cofounder", r.stderr)


class PreloadLineTests(Project):
    def preload(self):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
        env.update(CLAUDE_PROJECT_DIR=str(self.project), HOME=str(self.project))
        r = subprocess.run([BASH, (PLUGIN_ROOT / "hooks" / "session-preload.sh").as_posix()], input="{}",
                           capture_output=True, encoding="utf-8", env=env, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_set_up_project_without_env_says_the_server_cannot_start(self):
        (self.project / "core_text").mkdir()
        (self.project / "core_text" / "user.md").write_text("# p\n", encoding="utf-8")
        lines = [ln for ln in self.preload().splitlines() if "cannot start" in ln]
        self.assertEqual(len(lines), 1)
        self.assertIn(".cofounder/env", lines[0])

    def test_no_line_once_the_env_exists(self):
        (self.project / "core_text").mkdir()
        (self.project / "core_text" / "user.md").write_text("# p\n", encoding="utf-8")
        self.assertEqual(cli(self.project).returncode, 0)
        self.assertNotIn("cannot start", self.preload())


if __name__ == "__main__":
    unittest.main()
