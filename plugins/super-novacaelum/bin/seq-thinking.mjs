// seq-thinking.mjs — starts the sequential-thinking MCP server on every OS.
// Source: Nova Caelum (Apache-2.0).
//
// Claude Code spawns a plugin .mcp.json command without a shell, and on
// Windows `npx` is npx.cmd, which cannot be spawned that way. `node` is a real
// executable everywhere, so .mcp.json runs this file, which runs npx (through
// the shell on Windows only) and hands it this process's stdio.
import { spawn } from "node:child_process";

const npx = "npx -y @modelcontextprotocol/server-sequential-thinking";
const child = process.platform === "win32"
  ? spawn(npx, { stdio: "inherit", shell: true })
  : spawn("npx", npx.split(" ").slice(1), { stdio: "inherit" });

child.on("error", (err) => {
  console.error(`seq-thinking: could not start npx (${err.message}); is Node.js installed?`);
  process.exit(1);
});
child.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
