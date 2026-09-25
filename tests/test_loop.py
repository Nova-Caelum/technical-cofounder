"""Tests for the local-file working loop: bin/loop_state.py and bin/node_gates.py.

Standard library only. Three layers:

  * gate unit tests: each of the four exit checks refuses the broken shapes it
    exists to catch and accepts a good one;
  * state-machine tests through the real CLI: one-way gates, the freeze and
    its double-back count, `live` conferred only by the build gate, `confirm`
    reserved for a human;
  * the whole path: a toy goal driven from `init` through every gate to
    `status: live`, closing the build through verifier-lite, in a temp dir.
    Every gate is shown a broken artifact first and must refuse it.

Regenerate the committed worked example (examples/toy-run/) with:

    python3 tests/test_loop.py --write-example
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN = REPO_ROOT / "plugins" / "base-novacaelum"
BIN = PLUGIN / "bin"
LOOP_STATE = BIN / "loop_state.py"
VERIFIER = PLUGIN / "mcp" / "verifier.py"
EXAMPLE = REPO_ROOT / "examples" / "toy-run"

sys.path.insert(0, str(BIN))
sys.path.insert(0, str(PLUGIN / "mcp"))

import node_gates  # noqa: E402
import verifier  # noqa: E402


def cli(*args):
    return subprocess.run(
        [sys.executable, str(LOOP_STATE), *[str(a) for a in args]], capture_output=True, text=True
    )


def verify(criteria_file, root):
    return subprocess.run(
        [sys.executable, str(VERIFIER), str(criteria_file), "--root", str(root)], capture_output=True, text=True
    )


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def criterion(statement, **verification):
    return {"statement": statement, "verification": verification}


def expect(proc, code, what):
    if proc.returncode != code:
        raise AssertionError(
            f"{what}: expected exit {code}, got {proc.returncode}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
        )
    return proc


# ─────────────────────────────────────────────────────────────────────────────
# The toy goal: "add a greeting". Every artifact the loop needs, good and broken.
# ─────────────────────────────────────────────────────────────────────────────

TOY_SLUG = "toy-run"

ORIGINAL_INPUT = (
    "Add a greeting to the project: a greeting.txt file holding the line "
    "\"Hello, world\", and a greet.py command that prints whatever greeting.txt says.\n"
)

PROBLEM_MD = """# Problem: toy-run

## Ask (verbatim)

Add a greeting to the project: a greeting.txt file holding the line "Hello, world", and a greet.py command that prints whatever greeting.txt says.

In one sentence: running `python3 greet.py` prints the greeting stored in `greeting.txt`.

## Path

bounded: two new files in an existing project, no interface anyone else depends on.

## Problem

A newcomer wants one command that prints a greeting, with the text kept in a file they can edit without touching code.

## Constraints

- HARD: standard library only.
- HARD: the greeting text lives in `greeting.txt`, not in the code.

## Assumptions Register

| Assumption | Confidence | Load-bearing | Verified via | Actual behavior |
|---|---|---|---|---|
| `python3 -m unittest tests/test_greet.py` imports `greet` from the project root | high | yes | ran it in the toy project | the root is on `sys.path` when unittest is started there |

## Out of scope

- Greetings in other languages (deferred at decide).
- Any command-line flags.

## Schema findings

none
"""

TESTS_GOOD = {
    "id": "toy-run-acceptance",
    "criteria": [
        criterion(
            "greeting.txt holds the greeting Hello, world",
            kind="file_state", path="greeting.txt", assertion="contains", expected="Hello, world",
        ),
        criterion(
            "WHOLE-PATH: running greet.py prints the line stored in greeting.txt",
            kind="command_check", check_id="tests", target="tests/test_greet.py",
        ),
    ],
}

# Broken: nothing walks the whole path, so every component could pass its own
# check while the command stays unwired.
TESTS_NO_WHOLE_PATH = {
    "id": "toy-run-acceptance",
    "criteria": [TESTS_GOOD["criteria"][0]],
}

DECISION_MD = """# Decision: toy-run

Tests: T1 greeting.txt holds the greeting · T2 WHOLE-PATH: greet.py prints greeting.txt

## Options

### Option A: text file plus a reader script
T1 passes · T2 passes with greet command. Standard library only: satisfies. Text in a file: satisfies.

### ~~Option B: greeting hard-coded in greet.py~~
Struck: violates "the greeting text lives in greeting.txt, not in the code".

## Decision

Option A. It passes T1 and T2 and satisfies both HARD constraints; B violates the second. Decided by: the driver, the user absent.

## Architecture

### greeting file
- **Does:** holds the greeting text.
- **Used by:** greet command reads it.
- **Depends on:** nothing.
- **Passes:** T1

### greet command
- **Does:** prints the contents of greeting.txt.
- **Used by:** a person running `python3 greet.py`.
- **Depends on:** greeting file.
- **Passes:** T2

### localized greetings — deferred → Deferred.md

### Data flow
`python3 greet.py` → greet command reads greeting file → prints the line (T2 walks this).

## Mapping

| Component | Tests | Principles | Status |
|---|---|---|---|
| greeting file | T1 | | kept-by-test |
| greet command | T2 | stdlib-only | kept-by-test |
| localized greetings | | | deferred |

## Cuts

1 deferred, 0 kept by principle; see Deferred.md.
"""

DEFERRED_MD = """# Deferred: toy-run

## Deferred

- **localized greetings** — (a) no test: checked T1..T2; (b) principles: none contradicted; reopen when: a test asks for a second language.

## Kept by principle

none

## Overbloat review

yagni: localized greetings — no test asks for it. Score: 1 finding, cut.
"""

PRINCIPLES = {
    "principles": [
        {"id": "stdlib-only", "statement": "Ship with the Python standard library and nothing else.", "state": "active"},
    ]
}

MAPPING_GOOD = {
    "tests_file": "../01_understand/tests.json",
    "deferred_file": "Deferred.md",
    "principles_file": "principles.json",
    "components": [
        {"name": "greeting file", "tests": ["T1"], "principles": []},
        {"name": "greet command", "tests": ["T2"], "principles": ["stdlib-only"]},
        {"name": "localized greetings", "tests": [], "principles": []},
    ],
}

# Broken: the whole-path test maps to no component.
MAPPING_T2_UNMAPPED = {
    **MAPPING_GOOD,
    "components": [
        {"name": "greeting file", "tests": ["T1"], "principles": []},
        {"name": "localized greetings", "tests": [], "principles": []},
    ],
}

PRD_MD = """# PRD: toy-run

## Acceptance set

- T1 file_state: greeting.txt holds the greeting Hello, world
- T2 command_check: WHOLE-PATH: running greet.py prints the line stored in greeting.txt (whole path)

## What we are building

One command, `python3 greet.py`, that prints the greeting kept in `greeting.txt`. Option A: a text file plus a reader script. HARD: standard library only. HARD: the text lives in the file.

## Components

- **greeting file**: holds the text. Passes T1.
- **greet command**: reads and prints it. Passes T2. Kept by test; cites principle stdlib-only.

## Principles

- **stdlib-only**: ship with the Python standard library and nothing else. Cited by greet command.

## v2 recap

- **localized greetings**: greetings in other languages. Reopen when: a test asks for a second language.

v1 set: greeting file, greet command

## Decisions inherited

| Decision | Source | Date |
|---|---|---|
| Option A | 02_decide/Decision.md | toy |

## Not claimed

- No flags, no languages, no packaging.

## Closeout: rules enforced only by prose

None found. Every rule above names its mechanism.
"""

CRITERIA_GREETING_FILE = {
    "id": "greeting-file",
    "criteria": [
        criterion("greeting.txt exists", kind="file_state", path="greeting.txt", assertion="exists"),
        criterion(
            "greeting.txt holds Hello, world",
            kind="file_state", path="greeting.txt", assertion="contains", expected="Hello, world",
        ),
    ],
}

CRITERIA_GREET_COMMAND = {
    "id": "greet-command",
    "criteria": [
        criterion(
            "greet.py reads its text from greeting.txt",
            kind="file_state", path="greet.py", assertion="contains", expected="greeting.txt",
        ),
        criterion(
            "WHOLE-PATH: the greet test runs greet.py and sees the greeting",
            kind="command_check", check_id="tests", target="tests/test_greet.py",
        ),
    ],
}

WORKPLAN = {
    "run": TOY_SLUG,
    "tests_file": "../01_understand/tests.json",
    "tasks": [
        {
            "id": "greeting-file",
            "title": "Add greeting.txt holding the greeting",
            "summary": "Create the text file the command will print.",
            "owner": "engineer",
            "serves": ["T1"],
            "produces": ["greeting.txt"],
            "blocked_by": [],
            "size": "minutes",
            "note": "Assert what the task changes: contains, not just exists.",
            "criteria": "criteria/greeting-file.json",
        },
        {
            "id": "greet-command",
            "title": "Add greet.py and its test",
            "summary": "A command that prints whatever greeting.txt says, and a test that runs it end to end.",
            "owner": "engineer",
            "serves": ["T2"],
            "produces": ["greet.py", "tests/test_greet.py"],
            "blocked_by": ["greeting-file"],
            "size": "under an hour",
            "note": "The test runs greet.py as a user would; it is the whole-path check.",
            "criteria": "criteria/greet-command.json",
        },
    ],
}

GREETING_TXT = "Hello, world\n"

GREET_PY = '''"""Print the greeting stored in greeting.txt."""
from pathlib import Path

GREETING_FILE = Path(__file__).resolve().parent / "greeting.txt"


def main():
    print(GREETING_FILE.read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    main()
'''

TEST_GREET_PY = '''"""End to end: run greet.py as a user would and check what it prints."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class GreetTests(unittest.TestCase):
    def test_prints_the_greeting_file(self):
        out = subprocess.run(
            [sys.executable, str(ROOT / "greet.py")], capture_output=True, text=True, check=True
        ).stdout.strip()
        self.assertEqual(out, (ROOT / "greeting.txt").read_text(encoding="utf-8").strip())
        self.assertEqual(out, "Hello, world")


if __name__ == "__main__":
    unittest.main()
'''

RECONCILIATION_MD = """# Reconciliation: toy-run

- greeting-file → done  greeting.txt, verified by verifier-lite
- greet-command → done  greet.py and tests/test_greet.py, verified by verifier-lite
"""


def drive_toy_run(workspace):
    """Drive the toy goal through the whole loop in `workspace`, the way the
    skills do it: through the CLI, one node at a time, every gate shown a
    broken artifact before a good one. Raises AssertionError on any step
    that does not behave. Returns the run directory.

    In the toy, the project under change and the run folder are the same
    directory, so the example is self-contained: verifier-lite's `--root` is
    the run folder and its verdicts land in `<run>/verdicts/`."""
    workspace = Path(workspace)
    run = workspace / TOY_SLUG
    state = run / "loop.state.json"
    write_text(run / "original_input.md", ORIGINAL_INPUT)

    expect(cli("init", "--goal", TOY_SLUG, "--input", run / "original_input.md", "--workspace", workspace), 0, "init")
    expect(cli("set-node", state, "--node", "build"), 1, "set-node build before any gate passed")
    expect(cli("set-node", state, "--node", "understand"), 0, "set-node understand")

    # understand
    write_text(run / "01_understand" / "Problem.md", PROBLEM_MD)
    tests = run / "01_understand" / "tests.json"
    write_json(tests, TESTS_NO_WHOLE_PATH)
    gate_understand = ("gate-pass", state, "--node", "understand", "--by", "driver",
                       "--tests", tests, "--artifact", run / "01_understand" / "Problem.md")
    refused = expect(cli(*gate_understand), 1, "understand gate on a set with no WHOLE-PATH criterion")
    assert "WHOLE-PATH" in refused.stderr, refused.stderr
    write_json(tests, TESTS_GOOD)
    expect(cli(*gate_understand), 0, "understand gate on the good tests")

    # decide
    expect(cli("set-node", state, "--node", "decide"), 0, "set-node decide")
    decide = run / "02_decide"
    write_text(decide / "Decision.md", DECISION_MD)
    write_text(decide / "Deferred.md", DEFERRED_MD)
    write_json(decide / "principles.json", PRINCIPLES)
    mapping = decide / "mapping.json"
    write_json(mapping, MAPPING_T2_UNMAPPED)
    gate_decide = ("gate-pass", state, "--node", "decide", "--by", "driver",
                   "--mapping", mapping, "--artifact", decide / "Decision.md")
    refused = expect(cli(*gate_decide), 1, "decide gate with T2 mapped to nothing")
    assert "T2 maps to no component" in refused.stderr, refused.stderr
    write_json(mapping, MAPPING_GOOD)
    expect(cli(*gate_decide), 0, "decide gate on the good mapping")

    # draft
    expect(cli("set-node", state, "--node", "draft"), 0, "set-node draft")
    draft = run / "03_draft"
    write_text(draft / "PRD.md", PRD_MD)
    workplan = draft / "workplan.json"
    write_json(workplan, WORKPLAN)
    write_json(draft / "criteria" / "greeting-file.json", CRITERIA_GREETING_FILE)
    gate_draft = ("gate-pass", state, "--node", "draft", "--by", "driver",
                  "--workplan", workplan, "--artifact", draft / "PRD.md")
    refused = expect(cli(*gate_draft), 1, "draft gate with a task whose criteria file is missing")
    assert "greet-command" in refused.stderr, refused.stderr
    write_json(draft / "criteria" / "greet-command.json", CRITERIA_GREET_COMMAND)
    expect(cli(*gate_draft), 0, "draft gate on the good workplan")

    # build: row 1, closed through verifier-lite
    expect(cli("set-node", state, "--node", "build"), 0, "set-node build")
    write_text(run / "greeting.txt", GREETING_TXT)
    expect(verify(draft / "criteria" / "greeting-file.json", run), 0, "verifier-lite on greeting-file")

    reconciliation = run / "RECONCILIATION.md"
    write_text(reconciliation, RECONCILIATION_MD)
    gate_build = ("gate-pass", state, "--node", "build", "--by", "driver", "--workplan", workplan,
                  "--reconciliation", reconciliation, "--verdicts", run / "verdicts")
    refused = expect(cli(*gate_build), 1, "build gate claiming greet-command done before it was verified")
    assert "greet-command" in refused.stderr, refused.stderr

    # build: row 2
    write_text(run / "greet.py", GREET_PY)
    write_text(run / "tests" / "test_greet.py", TEST_GREET_PY)
    expect(verify(draft / "criteria" / "greet-command.json", run), 0, "verifier-lite on greet-command")
    expect(cli(*gate_build), 0, "build gate after both rows verified")

    shutil.rmtree(run / "tests" / "__pycache__", ignore_errors=True)
    shutil.rmtree(run / "__pycache__", ignore_errors=True)
    return run


# ─────────────────────────────────────────────────────────────────────────────
# Gate unit tests
# ─────────────────────────────────────────────────────────────────────────────


class _TempDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class UnderstandGateTests(_TempDir):
    def check(self, data):
        path = self.root / "tests.json"
        write_json(path, data)
        return node_gates.check_understand(tests=path)

    def test_good_tests_pass(self):
        result = self.check(TESTS_GOOD)
        self.assertTrue(result.ok, result.messages)

    def test_all_manual_refused(self):
        result = self.check({"id": "x", "criteria": [
            criterion("WHOLE-PATH: a person runs it", kind="manual", instruction="run it and look"),
        ]})
        self.assertFalse(result.ok)
        self.assertTrue(any("non-manual" in m for m in result.messages), result.messages)

    def test_no_whole_path_refused(self):
        result = self.check(TESTS_NO_WHOLE_PATH)
        self.assertFalse(result.ok)
        self.assertTrue(any("WHOLE-PATH" in m for m in result.messages), result.messages)

    def test_traversal_path_refused(self):
        bad = json.loads(json.dumps(TESTS_GOOD))
        bad["criteria"][0]["verification"]["path"] = "../outside.txt"
        self.assertFalse(self.check(bad).ok)

    def test_placeholder_path_refused(self):
        bad = json.loads(json.dumps(TESTS_GOOD))
        bad["criteria"][0]["verification"]["path"] = "reports/<date>.md"
        result = self.check(bad)
        self.assertFalse(result.ok)
        self.assertTrue(any("<" in m for m in result.messages), result.messages)

    def test_unknown_kind_refused(self):
        bad = json.loads(json.dumps(TESTS_GOOD))
        bad["criteria"][0]["verification"] = {"kind": "http_readback", "endpoint_id": "x"}
        self.assertFalse(self.check(bad).ok)

    def test_contains_without_expected_refused(self):
        bad = json.loads(json.dumps(TESTS_GOOD))
        del bad["criteria"][0]["verification"]["expected"]
        self.assertFalse(self.check(bad).ok)

    def test_unreadable_refused(self):
        path = self.root / "tests.json"
        write_text(path, "{not json")
        self.assertFalse(node_gates.check_understand(tests=path).ok)


class DecideGateTests(_TempDir):
    def setUp(self):
        super().setUp()
        write_json(self.root / "01_understand" / "tests.json", TESTS_GOOD)
        decide = self.root / "02_decide"
        write_text(decide / "Deferred.md", DEFERRED_MD)
        write_json(decide / "principles.json", PRINCIPLES)
        self.mapping = decide / "mapping.json"

    def check(self, mapping):
        write_json(self.mapping, mapping)
        return node_gates.check_decide(mapping=self.mapping)

    def test_good_mapping_passes(self):
        result = self.check(MAPPING_GOOD)
        self.assertTrue(result.ok, result.messages)

    def test_unmapped_test_refused(self):
        result = self.check(MAPPING_T2_UNMAPPED)
        self.assertIn("T2 maps to no component", result.messages)

    def test_unknown_test_id_refused(self):
        bad = json.loads(json.dumps(MAPPING_GOOD))
        bad["components"][0]["tests"] = ["T1", "T9"]
        self.assertFalse(self.check(bad).ok)

    def test_unknown_principle_refused(self):
        bad = json.loads(json.dumps(MAPPING_GOOD))
        bad["components"][1]["principles"] = ["always-fast"]
        self.assertFalse(self.check(bad).ok)

    def test_retired_principle_refused(self):
        write_json(self.root / "02_decide" / "principles.json", {"principles": [
            {"id": "stdlib-only", "statement": "old", "state": "retired"},
        ]})
        result = self.check(MAPPING_GOOD)
        self.assertFalse(result.ok)
        self.assertTrue(any("retired" in m for m in result.messages), result.messages)

    def test_empty_principles_file_is_legal(self):
        write_json(self.root / "02_decide" / "principles.json", {"principles": []})
        good = json.loads(json.dumps(MAPPING_GOOD))
        good["components"][1]["principles"] = []
        self.assertTrue(self.check(good).ok)

    def test_component_neither_kept_nor_deferred_refused(self):
        bad = json.loads(json.dumps(MAPPING_GOOD))
        bad["components"].append({"name": "logging layer", "tests": [], "principles": []})
        result = self.check(bad)
        self.assertTrue(any("logging layer" in m and "unmapped" in m for m in result.messages), result.messages)

    def test_duplicate_component_refused(self):
        bad = json.loads(json.dumps(MAPPING_GOOD))
        bad["components"].append({"name": "greeting file", "tests": ["T1"], "principles": []})
        self.assertFalse(self.check(bad).ok)


class DraftGateTests(_TempDir):
    def setUp(self):
        super().setUp()
        write_json(self.root / "01_understand" / "tests.json", TESTS_GOOD)
        self.draft = self.root / "03_draft"
        write_json(self.draft / "criteria" / "greeting-file.json", CRITERIA_GREETING_FILE)
        write_json(self.draft / "criteria" / "greet-command.json", CRITERIA_GREET_COMMAND)
        self.workplan = self.draft / "workplan.json"

    def check(self, workplan):
        write_json(self.workplan, workplan)
        return node_gates.check_draft(workplan=self.workplan)

    def test_good_workplan_passes(self):
        result = self.check(WORKPLAN)
        self.assertTrue(result.ok, result.messages)

    def test_missing_criteria_file_refused(self):
        (self.draft / "criteria" / "greet-command.json").unlink()
        result = self.check(WORKPLAN)
        self.assertTrue(any("greet-command" in m for m in result.messages), result.messages)

    def test_task_without_id_refused(self):
        bad = json.loads(json.dumps(WORKPLAN))
        del bad["tasks"][0]["id"]
        self.assertFalse(self.check(bad).ok)

    def test_duplicate_task_id_refused(self):
        bad = json.loads(json.dumps(WORKPLAN))
        bad["tasks"][1]["id"] = "greeting-file"
        self.assertFalse(self.check(bad).ok)

    def test_criteria_id_must_match_task_id(self):
        write_json(self.draft / "criteria" / "greet-command.json", {**CRITERIA_GREET_COMMAND, "id": "other"})
        result = self.check(WORKPLAN)
        self.assertTrue(any("does not match" in m for m in result.messages), result.messages)

    def test_all_manual_row_refused(self):
        write_json(self.draft / "criteria" / "greet-command.json", {"id": "greet-command", "criteria": [
            criterion("a person ran it", kind="manual", instruction="run greet.py and read it"),
        ]})
        self.assertFalse(self.check(WORKPLAN).ok)

    def test_unserved_test_refused(self):
        bad = json.loads(json.dumps(WORKPLAN))
        bad["tasks"][1]["serves"] = ["T1"]
        result = self.check(bad)
        self.assertIn("T2 is served by no task", result.messages)

    def test_empty_workplan_refused(self):
        self.assertFalse(self.check({**WORKPLAN, "tasks": []}).ok)


class BuildGateTests(_TempDir):
    """Verdicts here are produced by the real verifier-lite, except where a
    test deliberately forges one."""

    def setUp(self):
        super().setUp()
        self.draft = self.root / "03_draft"
        write_json(self.root / "01_understand" / "tests.json", TESTS_GOOD)
        write_json(self.draft / "criteria" / "greeting-file.json", CRITERIA_GREETING_FILE)
        write_json(self.draft / "criteria" / "greet-command.json", CRITERIA_GREET_COMMAND)
        self.workplan = self.draft / "workplan.json"
        write_json(self.workplan, WORKPLAN)
        self.reconciliation = self.root / "RECONCILIATION.md"
        self.verdicts = self.root / "verdicts"

    def build_everything(self):
        write_text(self.root / "greeting.txt", GREETING_TXT)
        write_text(self.root / "greet.py", GREET_PY)
        write_text(self.root / "tests" / "test_greet.py", TEST_GREET_PY)

    def run_verifier(self, row, attestations=None):
        return verifier.run_verification(self.draft / "criteria" / f"{row}.json", root=self.root,
                                         attestations=attestations)

    def check(self, reconciliation=RECONCILIATION_MD, not_before=None):
        write_text(self.reconciliation, reconciliation)
        return node_gates.check_build(workplan=self.workplan, reconciliation=self.reconciliation,
                                      verdicts_dir=self.verdicts, not_before=not_before)

    def test_both_rows_verified_passes(self):
        self.build_everything()
        self.assertEqual(self.run_verifier("greeting-file")["overall"], "pass")
        self.assertEqual(self.run_verifier("greet-command")["overall"], "pass")
        result = self.check()
        self.assertTrue(result.ok, result.messages)

    def test_row_missing_from_reconciliation_refused(self):
        self.build_everything()
        self.run_verifier("greeting-file")
        self.run_verifier("greet-command")
        result = self.check("- greeting-file → done\n")
        self.assertFalse(result.ok)
        self.assertTrue(any("greet-command" in m and "no disposition" in m for m in result.messages))

    def test_done_without_verdict_refused(self):
        self.build_everything()
        self.run_verifier("greeting-file")
        result = self.check()
        self.assertFalse(result.ok)
        self.assertFalse(result.hold)

    def test_failing_verdict_refused(self):
        write_text(self.root / "greeting.txt", GREETING_TXT)
        self.run_verifier("greeting-file")
        self.assertEqual(self.run_verifier("greet-command")["overall"], "fail")
        result = self.check()
        self.assertFalse(result.ok)
        self.assertTrue(any("'fail'" in m for m in result.messages), result.messages)

    def test_undischarged_manual_criterion_holds(self):
        self.build_everything()
        manual = {**CRITERIA_GREET_COMMAND, "criteria": CRITERIA_GREET_COMMAND["criteria"] + [
            criterion("A person ran greet.py and read the greeting", kind="manual",
                      instruction="Run python3 greet.py and read what it prints"),
        ]}
        write_json(self.draft / "criteria" / "greet-command.json", manual)
        self.run_verifier("greeting-file")
        self.assertEqual(self.run_verifier("greet-command")["overall"], "uncertain")
        result = self.check()
        self.assertFalse(result.ok)
        self.assertTrue(result.hold, result.messages)
        self.assertIn("greet-command → A person ran greet.py and read the greeting", result.messages)

        attested = self.run_verifier("greet-command", attestations=[
            {"statement": "A person ran greet.py and read the greeting", "attested_by": "the user"},
        ])
        self.assertEqual(attested["overall"], "pass")
        self.assertTrue(self.check().ok)

    def test_uncertain_on_an_executable_criterion_refused_not_held(self):
        broken = {"id": "greet-command", "criteria": [
            criterion("runs a check nobody defined", kind="command_check", check_id="nonexistent"),
        ]}
        write_json(self.draft / "criteria" / "greet-command.json", broken)
        self.build_everything()
        self.run_verifier("greeting-file")
        self.assertEqual(self.run_verifier("greet-command")["overall"], "uncertain")
        result = self.check()
        self.assertFalse(result.ok)
        self.assertFalse(result.hold)

    def test_forged_verdict_for_other_criteria_refused(self):
        self.build_everything()
        self.run_verifier("greeting-file")
        write_json(self.verdicts / "greet-command-20990101T000000Z.json", {
            "id": "greet-command", "overall": "pass", "timestamp": "2099-01-01T00:00:00Z",
            "criteria": [{"statement": "something easier", "verification": {}, "result": "pass", "evidence": ""}],
        })
        result = self.check()
        self.assertFalse(result.ok)
        self.assertTrue(any("different criteria" in m for m in result.messages), result.messages)

    def test_latest_verdict_wins(self):
        write_text(self.root / "greeting.txt", GREETING_TXT)
        self.run_verifier("greeting-file")
        write_json(self.verdicts / "greet-command-20000101T000000Z.json", {
            "id": "greet-command", "overall": "fail", "timestamp": "2000-01-01T00:00:00Z",
            "criteria": [dict(c, result="fail", evidence="") for c in CRITERIA_GREET_COMMAND["criteria"]],
        })
        self.build_everything()
        self.run_verifier("greet-command")
        self.assertTrue(self.check().ok)

    def test_verdict_older_than_the_plan_does_not_count(self):
        self.build_everything()
        self.run_verifier("greeting-file")
        self.run_verifier("greet-command")
        result = self.check(not_before="2099-01-01T00:00:00+00:00")
        self.assertFalse(result.ok)
        self.assertTrue(any("before the plan" in m for m in result.messages), result.messages)

    def test_deferred_and_live_test_rows_pass_without_a_verdict(self):
        write_text(self.root / "greeting.txt", GREETING_TXT)
        self.run_verifier("greeting-file")
        result = self.check("- greeting-file → done\n- greet-command -> live-test  the user runs it\n")
        self.assertTrue(result.ok, result.messages)
        result = self.check("- greeting-file → done\n- greet-command → deferred\n")
        self.assertTrue(result.ok, result.messages)

    def test_unreadable_criteria_file_named_as_such(self):
        self.build_everything()
        self.run_verifier("greeting-file")
        self.run_verifier("greet-command")
        (self.draft / "criteria" / "greet-command.json").unlink()
        result = self.check()
        self.assertFalse(result.ok)
        self.assertTrue(any("greet-command" in m and "criteria file" in m and "unreadable" in m
                            for m in result.messages), result.messages)

    def test_unknown_row_in_reconciliation_refused(self):
        self.build_everything()
        self.run_verifier("greeting-file")
        self.run_verifier("greet-command")
        result = self.check(RECONCILIATION_MD + "- greet-comand → done\n")
        self.assertFalse(result.ok)

    def test_typo_disposition_reads_as_missing(self):
        self.build_everything()
        self.run_verifier("greeting-file")
        self.run_verifier("greet-command")
        result = self.check("- greeting-file → done\n- greet-command → finished\n")
        self.assertFalse(result.ok)


# ─────────────────────────────────────────────────────────────────────────────
# State machine through the CLI
# ─────────────────────────────────────────────────────────────────────────────


class StateMachineTests(_TempDir):
    def setUp(self):
        super().setUp()
        write_text(self.root / "ask.md", ORIGINAL_INPUT)
        expect(cli("init", "--goal", "g", "--input", self.root / "ask.md", "--workspace", self.root), 0, "init")
        self.state = self.root / "g" / "loop.state.json"
        self.run_dir = self.root / "g"

    def read(self):
        return json.loads(self.state.read_text(encoding="utf-8"))

    def pass_understand(self):
        tests = self.run_dir / "01_understand" / "tests.json"
        write_json(tests, TESTS_GOOD)
        expect(cli("set-node", self.state, "--node", "understand"), 0, "set-node understand")
        return expect(cli("gate-pass", self.state, "--node", "understand", "--by", "t", "--tests", tests), 0,
                      "understand gate")

    def test_init_writes_a_framing_state(self):
        data = self.read()
        self.assertEqual(data["status"], "framing")
        self.assertEqual(data["current_node"], "framing")
        self.assertEqual(data["original_input"], ORIGINAL_INPUT)
        self.assertEqual(data["gates"], [])

    def test_init_defaults_workspace_to_cwd(self):
        other = self.root / "elsewhere"
        other.mkdir()
        proc = subprocess.run([sys.executable, str(LOOP_STATE), "init", "--goal", "h", "--input",
                               str(self.root / "ask.md")], cwd=str(other), capture_output=True, text=True)
        expect(proc, 0, "init without --workspace")
        self.assertTrue((other / "h" / "loop.state.json").is_file())

    def test_gates_are_one_way(self):
        expect(cli("set-node", self.state, "--node", "decide"), 1, "decide before understand passed")
        self.pass_understand()
        expect(cli("set-node", self.state, "--node", "draft"), 1, "draft before decide passed")
        expect(cli("set-node", self.state, "--node", "decide"), 0, "decide after understand passed")

    def test_gate_pass_only_for_the_current_node(self):
        tests = self.run_dir / "01_understand" / "tests.json"
        write_json(tests, TESTS_GOOD)
        refused = expect(cli("gate-pass", self.state, "--node", "understand", "--by", "t", "--tests", tests), 1,
                         "gate-pass while still framing")
        self.assertIn("current node", refused.stderr)
        self.assertEqual(self.read()["gates"], [])

    def test_live_is_not_a_node(self):
        expect(cli("set-node", self.state, "--node", "live"), 2, "set-node live")
        self.assertEqual(self.read()["status"], "framing")

    def test_missing_evidence_flag_is_a_usage_error(self):
        expect(cli("set-node", self.state, "--node", "understand"), 0, "set-node understand")
        expect(cli("gate-pass", self.state, "--node", "understand", "--by", "t"), 2, "understand without --tests")

    def test_refusal_records_nothing(self):
        tests = self.run_dir / "01_understand" / "tests.json"
        write_json(tests, TESTS_NO_WHOLE_PATH)
        expect(cli("set-node", self.state, "--node", "understand"), 0, "set-node understand")
        before = self.read()
        expect(cli("gate-pass", self.state, "--node", "understand", "--by", "t", "--tests", tests), 1, "refused")
        after = self.read()
        self.assertEqual(before["gates"], after["gates"])
        self.assertEqual(before["artifacts"], after["artifacts"])

    def test_gate_freezes_its_evidence_relative_to_the_run(self):
        self.pass_understand()
        data = self.read()
        self.assertEqual([g["node"] for g in data["gates"]], ["understand"])
        self.assertIn("01_understand/tests.json", [a["path"] for a in data["artifacts"]])

    def test_edit_after_freeze_counts_one_double_back(self):
        self.pass_understand()
        tests = self.run_dir / "01_understand" / "tests.json"
        edited = json.loads(json.dumps(TESTS_GOOD))
        edited["criteria"][0]["statement"] = "greeting.txt holds a greeting"
        write_json(tests, edited)
        first = json.loads(expect(cli("check", self.state), 0, "check").stdout)
        self.assertEqual(first["doubled_back_rounds"], 1)
        self.assertEqual(len(first["mismatches"]), 1)
        second = json.loads(expect(cli("check", self.state), 0, "check again").stdout)
        self.assertEqual(second["doubled_back_rounds"], 1, "the same edit is counted once")

    def test_confirm_requires_live_and_a_human(self):
        expect(cli("confirm", self.state, "--by", "agent"), 1, "confirm while framing")
        data = self.read()
        data["status"] = "live"
        self.state.write_text(json.dumps(data), encoding="utf-8")
        refused = expect(cli("confirm", self.state, "--by", "agent"), 1, "confirm with no human authority")
        self.assertIn("human", refused.stderr)
        expect(cli("record-approval", self.state, "--human-present", "true", "--authority", "human"), 0,
               "record-approval")
        expect(cli("confirm", self.state, "--by", "the user", "--escaped", "1", "--caught", "3"), 0, "confirm")
        data = self.read()
        self.assertEqual(data["status"], "done")
        self.assertEqual(data["final_route"], "done")
        self.assertEqual(data["escape_rate"], 0.25)

    def test_kill_ends_the_run(self):
        expect(cli("record-kill", self.state, "--reason", "goal withdrawn"), 0, "record-kill")
        data = self.read()
        self.assertEqual(data["final_route"], "killed")
        expect(cli("set-node", self.state, "--node", "understand"), 1, "set-node after the run ended")


# ─────────────────────────────────────────────────────────────────────────────
# The whole path, and the committed example
# ─────────────────────────────────────────────────────────────────────────────


class WholePathTests(_TempDir):
    def test_toy_goal_reaches_live_through_every_gate(self):
        run = drive_toy_run(self.root)
        state = json.loads((run / "loop.state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "live")
        self.assertEqual(state["current_node"], "build")
        self.assertEqual([g["node"] for g in state["gates"]], ["understand", "decide", "draft", "build"])
        self.assertEqual(state["budget"]["doubled_back_rounds"], 0)
        verdicts = [json.loads(p.read_text(encoding="utf-8")) for p in (run / "verdicts").glob("*.json")]
        self.assertEqual(sorted(v["id"] for v in verdicts), ["greet-command", "greeting-file"])
        self.assertTrue(all(v["overall"] == "pass" for v in verdicts))
        refused = expect(cli("confirm", run / "loop.state.json", "--by", "agent"), 1, "agent confirm at live")
        self.assertIn("human", refused.stderr)


class ExampleTests(unittest.TestCase):
    """The committed worked example stays consistent with the code."""

    def test_example_is_live_with_four_gates(self):
        state = json.loads((EXAMPLE / "loop.state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "live")
        self.assertEqual({g["node"] for g in state["gates"] if g["passed"]},
                         {"understand", "decide", "draft", "build"})

    def test_example_build_gate_accepts_its_own_evidence(self):
        result = node_gates.check_build(
            workplan=EXAMPLE / "03_draft" / "workplan.json",
            reconciliation=EXAMPLE / "RECONCILIATION.md",
            verdicts_dir=EXAMPLE / "verdicts",
        )
        self.assertTrue(result.ok, result.messages)

    def test_example_frozen_artifacts_still_match(self):
        with tempfile.TemporaryDirectory() as td:
            copy = Path(td) / "toy-run"
            shutil.copytree(EXAMPLE, copy)
            report = json.loads(expect(cli("check", copy / "loop.state.json"), 0, "check on a copy").stdout)
            self.assertEqual(report["mismatches"], [])
            self.assertEqual(report["doubled_back_rounds"], 0)


def write_example():
    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        run = drive_toy_run(Path(td))
        if EXAMPLE.exists():
            shutil.rmtree(EXAMPLE)
        shutil.copytree(run, EXAMPLE, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"wrote {EXAMPLE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-example"]:
        write_example()
    else:
        unittest.main()
