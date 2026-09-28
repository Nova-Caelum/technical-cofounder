"""Unit tests for super-novacaelum's sequential-thinking launcher,
bin/seq-thinking.mjs.

A plugin .mcp.json command is spawned without a shell, so on Windows a bare
`npx` (npx.cmd) cannot start. `node` is a real executable on every OS, so
.mcp.json runs the launcher with node and the launcher spawns npx. Here a fake
npx on PATH echoes its argv and stdin, so the tests prove the argv, the stdio
pass-through and the exit code without touching the network.

Standard library only; skipped when node is not installed.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SUPER_ROOT = REPO_ROOT / "plugins" / "super-novacaelum"
LAUNCHER = SUPER_ROOT / "bin" / "seq-thinking.mjs"
NODE = shutil.which("node")

FAKE_NPX_JS = """
const readline = require("node:readline");
console.log(JSON.stringify(process.argv.slice(2)));
const rl = readline.createInterface({ input: process.stdin });
rl.on("line", (line) => {
  if (line === "bye") process.exit(7);
  console.log("echo:" + line);
});
"""


class McpJsonTests(unittest.TestCase):
    def test_sequential_thinking_runs_the_node_launcher(self):
        servers = json.loads((SUPER_ROOT / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
        self.assertEqual(servers["sequential-thinking"], {
            "command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/bin/seq-thinking.mjs"]})


@unittest.skipIf(NODE is None, "node is not installed")
class LauncherTests(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        (tmp / "fake_npx.js").write_text(FAKE_NPX_JS, encoding="utf-8")
        if os.name == "nt":
            (tmp / "npx.cmd").write_text('@node "%~dp0fake_npx.js" %*\r\n', encoding="utf-8")
        else:
            npx = tmp / "npx"
            npx.write_text('#!/bin/sh\nexec node "$(dirname "$0")/fake_npx.js" "$@"\n', encoding="utf-8")
            npx.chmod(0o755)
        self.env = dict(os.environ, PATH=str(tmp) + os.pathsep + os.environ.get("PATH", ""))

    def launch(self, stdin):
        return subprocess.run([NODE, str(LAUNCHER)], input=stdin, capture_output=True, text=True,
                              env=self.env, timeout=60)

    def test_spawns_npx_with_the_server_package(self):
        r = self.launch("")
        self.assertEqual(r.stdout.splitlines()[0], '["-y","@modelcontextprotocol/server-sequential-thinking"]', r.stderr)

    def test_pipes_stdio_through_both_ways(self):
        r = self.launch('{"jsonrpc":"2.0","id":1,"method":"ping"}\n')
        self.assertIn('echo:{"jsonrpc":"2.0","id":1,"method":"ping"}', r.stdout.splitlines(), r.stderr)

    def test_exit_code_passes_through(self):
        self.assertEqual(self.launch("bye\n").returncode, 7)


if __name__ == "__main__":
    unittest.main()
