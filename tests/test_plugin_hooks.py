"""Every command in hooks.json, run the way Claude Code runs it: under
`bash -c`, CLAUDE_PLUGIN_ROOT in the environment, the event's JSON on stdin.

Running the .sh files directly (tests/test_template_hooks.py) cannot see what
breaks on a Windows checkout: CRLF line endings that turn `set -euo pipefail`
into `$'\\r': command not found`, or a command line the shell cannot start.
Standard library only.
"""
import json
import os
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


def run_hook(command, event, project, data):
    env = {k: v for k, v in os.environ.items() if k != "TC_CONCISION"}
    env.update(CLAUDE_PLUGIN_ROOT=str(PLUGIN_ROOT), CLAUDE_PROJECT_DIR=project, CLAUDE_PLUGIN_DATA=data)
    payload = {"session_id": "hooktest", "hook_event_name": event, "cwd": project, **EVENT_FIELDS[event]}
    return subprocess.run(
        ["bash", "-c", command], input=json.dumps(payload).encode("utf-8"), capture_output=True, env=env
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


if __name__ == "__main__":
    unittest.main()
