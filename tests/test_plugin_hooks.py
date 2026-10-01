"""Every command in hooks.json, run the way Claude Code runs it: under
`bash -c`, CLAUDE_PLUGIN_ROOT in the environment, the event's JSON on stdin.

Running the .sh files directly (tests/test_template_hooks.py) cannot see what
breaks on a Windows checkout: CRLF line endings that turn `set -euo pipefail`
into `$'\\r': command not found`, or a command line the shell cannot start.
Standard library only.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugins" / "base-novacaelum"
HOOKS = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]

TOOL = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
EVENT_FIELDS = {
    "SessionStart": {"source": "startup"},
    "UserPromptSubmit": {"prompt": "hello"},
    "Stop": {"stop_hook_active": False, "last_assistant_message": "Done."},
    "PreToolUse": TOOL,
    "PostToolUse": {**TOOL, "tool_response": {"output": "ok"}},
    "PostToolUseFailure": {**TOOL, "error": "boom"},
}
# What bash prints when a script has CRLF endings or a CR in its shebang.
SHELL_DEBRIS = ("$'\\r'", "\r", "bad interpreter")


def _bash():
    """Git Bash, which is what Claude Code runs hooks in on Windows. A bare "bash"
    there resolves to System32's WSL launcher, which is not a shell for these."""
    git = shutil.which("git") if os.name == "nt" else None
    for parent in Path(git).resolve().parents if git else ():
        if (parent / "bin" / "bash.exe").is_file():
            return str(parent / "bin" / "bash.exe")
    return "bash"


BASH = _bash()


def run_hook(command, event, project, data):
    env = {k: v for k, v in os.environ.items() if k != "TC_CONCISION"}
    env.update(CLAUDE_PLUGIN_ROOT=str(PLUGIN_ROOT), CLAUDE_PROJECT_DIR=project, CLAUDE_PLUGIN_DATA=data)
    # The command travels in the environment: a double quote in a Windows command
    # line does not reach bash intact, and the command's own quotes are the point.
    env["TC_HOOK_COMMAND"] = command
    payload = {"session_id": "hooktest", "hook_event_name": event, "cwd": project, **EVENT_FIELDS[event]}
    return subprocess.run(
        [BASH, "-c", "eval $TC_HOOK_COMMAND"], input=json.dumps(payload).encode("utf-8"), capture_output=True, env=env
    )


class PluginHooksTests(unittest.TestCase):
    def test_every_hooks_json_command_exits_clean_under_bash(self):
        ran = 0
        for event, groups in HOOKS.items():
            for group in groups:
                for hook in group["hooks"]:
                    ran += 1
                    with self.subTest(event=event, command=hook["command"]):
                        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as data:
                            r = run_hook(hook["command"], event, project, data)
                        stderr = r.stderr.decode("utf-8", errors="replace")
                        self.assertEqual(r.returncode, 0, stderr)
                        for debris in SHELL_DEBRIS:
                            self.assertNotIn(debris, stderr)
        self.assertGreater(ran, 0, "hooks.json named no commands")


MOVED_LINE = (
    "Technical Cofounder has moved. New installs: claude plugin marketplace add Nova-Caelum/plugins, "
    "then claude plugin install technical-cofounder@nova-caelum --scope project."
)


class LegacyAddressBriefingTests(unittest.TestCase):
    """An install made from the old address keeps working and is told, once and
    near the top of the briefing, where the product moved."""

    def preload(self, project, home):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR")}
        env.update(CLAUDE_PROJECT_DIR=project, HOME=home)
        r = subprocess.run(
            [BASH, str(PLUGIN_ROOT / "hooks" / "session-preload.sh")],
            input="{}", capture_output=True, text=True, encoding="utf-8", env=env,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_moved_line_is_printed_once_near_the_top_in_both_output_paths(self):
        for label, profile in (("project not set up", False), ("project set up", True)):
            with self.subTest(path=label), tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as home:
                if profile:
                    (Path(project) / "core_text").mkdir()
                    (Path(project) / "core_text" / "user.md").write_text("# profile\n", encoding="utf-8")
                out = self.preload(project, home)
                self.assertEqual(out.count(MOVED_LINE), 1, out)
                self.assertIn(MOVED_LINE, out.splitlines()[:3], out)


if __name__ == "__main__":
    unittest.main()
