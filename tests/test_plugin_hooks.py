"""Every command in hooks.json, run the way Claude Code runs it: under
`bash -c`, CLAUDE_PLUGIN_ROOT in the environment, the event's JSON on stdin.

Running the .sh files directly (tests/test_template_hooks.py) cannot see what
breaks on a Windows checkout: CRLF line endings that turn `set -euo pipefail`
into `$'\\r': command not found`, or a command line the shell cannot start.

An exit code of 0 is also what a guardrail that silently does nothing returns.
So the retry breaker and the word-budget hook are driven here and judged on
what they printed: with jq on PATH, with jq only in the tools folder the
install script uses, and with no jq anywhere.
Standard library only.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugins" / "technical-cofounder"
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


def write_tool(path, text):
    """A stand-in program: a shell script, written as bytes and made runnable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))  # bytes: a CRLF shebang does not start
    path.chmod(0o755)
    return path


def path_without(scratch, *tools):
    """PATH with the named tools taken out of it. A directory that holds one
    beside the shell's own tools (/usr/bin on macOS) is replaced by a folder
    of links, made under `scratch`, to everything else in it; on Windows such
    a tool has a folder of its own, and that folder is dropped."""
    names = {*tools, *(f"{tool}.exe" for tool in tools)}
    kept = []
    for entry in os.environ["PATH"].split(os.pathsep):
        folder = Path(entry)
        if not entry or not folder.is_dir():
            continue
        if not any((folder / name).exists() for name in names):
            kept.append(entry)
        elif os.name != "nt":
            shadow = Path(tempfile.mkdtemp(prefix="path-", dir=scratch))
            for tool in folder.iterdir():
                if tool.name not in names:
                    (shadow / tool.name).symlink_to(tool)
            kept.append(str(shadow))
    return os.pathsep.join(kept)


def run_hook(command, event, project, data, session="hooktest", fields=None, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k != "TC_CONCISION"}
    env.update(CLAUDE_PLUGIN_ROOT=str(PLUGIN_ROOT), CLAUDE_PROJECT_DIR=project, CLAUDE_PLUGIN_DATA=data)
    env.update(env_extra or {})
    # The command travels in the environment: a double quote in a Windows command
    # line does not reach bash intact, and the command's own quotes are the point.
    env["TC_HOOK_COMMAND"] = command
    payload = {"session_id": session, "hook_event_name": event, "cwd": project, **(EVENT_FIELDS[event] if fields is None else fields)}
    return subprocess.run(
        [BASH, "-c", "eval $TC_HOOK_COMMAND"], input=json.dumps(payload).encode("utf-8"), capture_output=True, env=env
    )


def hook_command(event, script):
    """The one command hooks.json runs on `event` that names `script`."""
    (command,) = [hook["command"] for group in HOOKS[event] for hook in group["hooks"] if script in hook["command"]]
    return command


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


# Stable phrases from what each hook prints.
STOP_MESSAGE = "CIRCUIT BREAKER — BLOCKED"
BUDGET_NOTICE = "RESPONSE BUDGET: <=300 words"
SKIP_LINE = "skipping this invocation"
THRESHOLD = 5  # identical failures in a row before the breaker stops the tool
FAILING_CALL = {"tool_name": "Bash", "tool_input": {"command": "frobnicate --all"}}
FAILED = {**FAILING_CALL, "error": "command not found: frobnicate"}
PROMPT = {"prompt": "add a retry to the upload function"}

# A minimal jq, for a machine that has none: it answers the calls the retry
# breaker and the word-budget hook make (and lib/rule-disclosure.sh for them),
# on the one-line JSON these tests send, and refuses anything else.
JQ_STAND_IN = r"""#!/bin/bash
field() { sed -n "s/.*\"$1\": *\"\([^\"]*\)\".*/\1/p"; }
case "$1" in
    --version) echo "jq-stand-in" ;;
    -e) [ "$2" = "." ] || { cat >/dev/null; exit 3; }
        grep -q '^[[:space:]]*{.*}[[:space:]]*$' ;;
    -r) case "$2" in
            ".hook_event_name // empty"|".tool_name // empty"|".session_id // empty"|".error // empty"|".prompt // empty")
                name="${2#.}"
                field "${name% // empty}" ;;
            *) cat >/dev/null; exit 3 ;;
        esac ;;
    -nc) [ "$2 $3 $5 $6" = "--arg event --arg ctx" ] || exit 3
        ctx="${7//\\/\\\\}"
        ctx="${ctx//\"/\\\"}"
        printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}\n' "$4" "$ctx" ;;
    *) cat >/dev/null; exit 3 ;;
esac
"""


def _runs(program):
    try:
        return subprocess.run([str(program), "--version"], stdin=subprocess.DEVNULL, capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def real_jq_into(tools):
    """Put this machine's jq in `tools`: a copy, or a link where a copy does not
    start (macOS kills a copy of the jq it ships; a Windows launcher only works
    where it was installed). False when there is no jq or neither runs."""
    real = shutil.which("jq")
    if not real:
        return False
    tools.mkdir(parents=True, exist_ok=True)
    target = tools / ("jq.exe" if os.name == "nt" else "jq")
    shutil.copyfile(real, target)
    target.chmod(0o755)
    if _runs(target):
        return True
    target.unlink()
    if os.name != "nt":
        target.symlink_to(Path(real).resolve())
        if _runs(target):
            return True
        target.unlink()
    return False


class GuardrailsActTests(unittest.TestCase):
    """The retry breaker and the word-budget hook, run through their hooks.json
    commands and judged on what they print. Hook state (TMPDIR), HOME and the
    session id are this test's own, so nothing on this machine decides a result."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        for name in ("project", "data", "state", "home", "no-tools"):
            (self.tmp / name).mkdir()
        self.session = f"acts-{uuid.uuid4().hex}"
        self.base = {"TMPDIR": str(self.tmp / "state"), "HOME": str(self.tmp / "home")}
        self.stripped = None  # PATH without jq, built once per test

    # ── where jq is ───────────────────────────────────────────────────────
    def jq_on_path(self):
        """The machine's own PATH when it has a jq, else the stand-in in front."""
        if shutil.which("jq"):
            return {**self.base, "NC_TOOLS_DIR": str(self.tmp / "no-tools")}
        stand_in = write_tool(self.tmp / "on-path" / "jq", JQ_STAND_IN).parent
        return {**self.base, "PATH": os.pathsep.join([str(stand_in), os.environ["PATH"]]), "NC_TOOLS_DIR": str(self.tmp / "no-tools")}

    def no_jq_path(self):
        if self.stripped is None:
            self.stripped = path_without(self.tmp, "jq")
            r = subprocess.run([BASH, "-c", "command -v jq"], capture_output=True, text=True, env={**os.environ, "PATH": self.stripped})
            self.assertNotEqual(r.returncode, 0, f"jq is still reachable at {r.stdout!r}; the test would prove nothing")
        return self.stripped

    def jq_only_in_the_tools_folder(self, kind):
        """PATH has no jq; NC_TOOLS_DIR has one: the stand-in, or this machine's
        real jq put there (None when there is none, or it won't run from there)."""
        tools = self.tmp / f"tools-{kind}"
        if kind == "stand-in":
            write_tool(tools / "jq", JQ_STAND_IN)
        elif not real_jq_into(tools):
            return None
        return {**self.base, "PATH": self.no_jq_path(), "NC_TOOLS_DIR": str(tools)}

    def jq_nowhere(self):
        return {**self.base, "PATH": self.no_jq_path(), "NC_TOOLS_DIR": str(self.tmp / "no-tools")}

    # ── driving the hooks ─────────────────────────────────────────────────
    def run_as(self, event, script, fields, env, session=None):
        r = run_hook(hook_command(event, script), event, str(self.tmp / "project"), str(self.tmp / "data"),
                     session=session or self.session, fields=fields, env_extra=env)
        return r.returncode, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")

    def failing_calls(self, env, session=None):
        """THRESHOLD calls that fail the same way, as Claude Code reports each:
        the check before the tool runs, then the failure. Returns, per call,
        what the check and the failure report printed."""
        seen = []
        for _ in range(THRESHOLD):
            before = self.run_as("PreToolUse", "circuit-breaker.sh", FAILING_CALL, env, session)
            after = self.run_as("PostToolUseFailure", "circuit-breaker.sh", FAILED, env, session)
            seen.append((before, after))
        return seen

    def next_attempt(self, env, session=None):
        return self.run_as("PreToolUse", "circuit-breaker.sh", FAILING_CALL, env, session)

    def assert_breaker_stops_after_the_fifth_failure(self, env, session=None):
        for n, (before, after) in enumerate(self.failing_calls(env, session), start=1):
            for code, out, err in (before, after):
                self.assertEqual(code, 0, f"call {n}: {err}")
                self.assertNotIn(STOP_MESSAGE, out + err, f"stopped at call {n}, before the fifth failure was in")
                self.assertNotIn(SKIP_LINE, err, f"call {n}: the hook did not act")
            if n == 3:
                self.assertIn("3 consecutive failures of the same kind", after[1], "the warning at the third failure")
        code, out, err = self.next_attempt(env, session)
        self.assertEqual(code, 2, f"the attempt after five identical failures was let through; stderr: {err}")
        self.assertIn(STOP_MESSAGE, err)
        self.assertIn('tool "Bash" has failed the same way 5 times in a row', err)

    def assert_budget_notice(self, env, session=None):
        code, out, err = self.run_as("UserPromptSubmit", "concision-budget.sh", PROMPT, env, session)
        self.assertEqual(code, 0, err)
        self.assertIn(BUDGET_NOTICE, out, f"the hook did not act; stderr: {err}")

    # ── jq on PATH ────────────────────────────────────────────────────────
    def test_the_breaker_prints_its_stop_message_after_the_fifth_identical_failure(self):
        self.assert_breaker_stops_after_the_fifth_failure(self.jq_on_path())

    def test_the_word_budget_hook_prints_its_notice(self):
        self.assert_budget_notice(self.jq_on_path())

    # ── jq only where the install script puts it ──────────────────────────
    def test_both_still_act_with_jq_only_in_the_tools_folder(self):
        ran = []
        for kind in ("stand-in", "real"):
            env = self.jq_only_in_the_tools_folder(kind)
            if env is None:
                continue
            ran.append(kind)
            with self.subTest(jq=kind):
                session = f"{self.session}-{kind}"
                self.assert_breaker_stops_after_the_fifth_failure(env, session)
                self.assert_budget_notice(env, session)
        self.assertIn("stand-in", ran)

    # ── no jq anywhere ────────────────────────────────────────────────────
    def test_with_jq_nowhere_both_say_they_are_skipping_and_exit_0(self):
        env = self.jq_nowhere()
        for n, (before, after) in enumerate(self.failing_calls(env), start=1):
            for code, out, err in (before, after):
                self.assertEqual((code, out.strip()), (0, ""), f"call {n}: {err}")
                self.assertIn(SKIP_LINE, err)
        code, out, err = self.next_attempt(env)
        self.assertEqual((code, out.strip()), (0, ""), err)
        self.assertIn(SKIP_LINE, err)
        self.assertNotIn(STOP_MESSAGE, err)
        code, out, err = self.run_as("UserPromptSubmit", "concision-budget.sh", PROMPT, env)
        self.assertEqual((code, out.strip()), (0, ""), err)
        self.assertIn(SKIP_LINE, err)


if __name__ == "__main__":
    unittest.main()
