"""One-off CI exploration (option B): does a project-settings `env` value expand
in a plugin `.mcp.json` command? Prints `claude mcp list` for four cases:
(a) the runner as it comes, (b) a failing `python3` first on PATH (on Windows,
the Microsoft Store placeholder directory), (c) project `.claude/settings.json`
env TC_PYTHON = this interpreter with (b) still in effect, (d) process-env
TC_PYTHON as the control. Keyless; temp CLAUDE_CONFIG_DIR.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
AUTH = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN")
claude = shutil.which("claude")
tmp = Path(tempfile.mkdtemp())
repo = tmp / "repo"
shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git"))
(repo / "plugins" / "base-novacaelum" / ".mcp.json").write_text(json.dumps({"mcpServers": {"cofounder": {
    "command": "${TC_PYTHON:-python3}", "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/server.py"]}}}))
cfg = tmp / "cfg"
cfg.mkdir()
proj = tmp / "b project"
proj.mkdir()
base_env = {k: v for k, v in os.environ.items() if k not in AUTH}
base_env["CLAUDE_CONFIG_DIR"] = str(cfg)


def claude_run(*args, env=None):
    r = subprocess.run([claude, *args], cwd=proj, env=env or base_env, capture_output=True,
                       encoding="utf-8", errors="replace", timeout=240)
    print(f"$ claude {' '.join(args)}  -> exit {r.returncode}\n{r.stdout}{r.stderr}", flush=True)
    return r


print("claude:", claude, "python:", sys.executable, flush=True)
claude_run("--version")
claude_run("plugin", "marketplace", "add", str(repo))
claude_run("plugin", "install", "base-novacaelum@technical-cofounder", "--scope", "project")
state = cfg / ".claude.json"
data = json.loads(state.read_text(encoding="utf-8")) if state.is_file() else {}
for key in {str(proj), str(proj).replace("\\", "/"), str(proj.resolve()), str(proj.resolve()).replace("\\", "/")}:
    data.setdefault("projects", {}).setdefault(key, {})["hasTrustDialogAccepted"] = True
state.write_text(json.dumps(data), encoding="utf-8")

print("## (a) runner as it comes, TC_PYTHON unset", flush=True)
claude_run("mcp", "list")

if sys.platform == "win32":
    first = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WindowsApps"
    print("placeholder dir:", first, "exists:", first.is_dir(), [p.name for p in first.glob("python*")], flush=True)
else:
    first = tmp / "stub"
    first.mkdir()
    stub = first / "python3"
    stub.write_text("#!/bin/sh\necho 'placeholder python3' >&2\nexit 9\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
placeholder_env = dict(base_env, PATH=str(first) + os.pathsep + base_env["PATH"])
probe = subprocess.run(["python3", "-c", "import sys"], env=placeholder_env, capture_output=True, text=True)
print("python3 with placeholder first -> exit", probe.returncode, probe.stderr[-200:], flush=True)
print("## (b) placeholder-style python3 first on PATH, TC_PYTHON unset", flush=True)
claude_run("mcp", "list", env=placeholder_env)

settings = proj / ".claude" / "settings.json"
sdata = json.loads(settings.read_text(encoding="utf-8"))
sdata["env"] = {"TC_PYTHON": sys.executable}
settings.write_text(json.dumps(sdata, indent=2), encoding="utf-8")
print("## (c) project settings env TC_PYTHON =", sys.executable, "(placeholder still first)", flush=True)
claude_run("mcp", "list", env=placeholder_env)

print("## (d) control: process env TC_PYTHON (placeholder still first)", flush=True)
claude_run("mcp", "list", env=dict(placeholder_env, TC_PYTHON=sys.executable))

print("## super: bare npx sequential-thinking as shipped (npx pre-warmed by the workflow)", flush=True)
claude_run("plugin", "install", "super-novacaelum@technical-cofounder", "--scope", "project")
claude_run("mcp", "list")
