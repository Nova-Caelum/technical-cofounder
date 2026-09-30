#!/usr/bin/env python3
"""loop_state.py -- the state file and the gates of one working-loop run.

A run is a folder, `<workspace>/<goal-slug>/`, with a `loop.state.json` that
answers on any resume: which stage the run is in, which gates it passed,
which files those gates froze, and how it ended. Only this script writes it.

The stages are understand -> decide -> draft -> build. A stage is entered
with `set-node` and left only through `gate-pass`, which runs that stage's
exit check (node_gates.py) and, on a pass, freezes the evidence by sha256.
Gates are one way: a stage cannot be entered until the gate before it has
passed. Passing the build gate sets `status: live` and leaves
`current_node: build`: building is over, but the run is not done. Only a
person moves it to done (`confirm`, which refuses unless the recorded driver
authority is `human`).

A frozen file that changes later is a double-back. It is counted once per
edit in `budget.doubled_back_rounds`: the fix-versus-pivot evidence. Nothing
is refused for it; it is recorded so nobody has to remember it.

Usage (exit 0 ok, 1 refused, 2 usage or unreadable input, 3 hold):

    loop_state.py init --goal SLUG --input ASK.md [--workspace DIR]   (default: cwd)
    loop_state.py read STATE
    loop_state.py set-node STATE --node understand|decide|draft|build
    loop_state.py gate-pass STATE --node understand --by WHO --tests tests.json [--artifact F ...]
    loop_state.py gate-pass STATE --node decide     --by WHO --mapping mapping.json [--artifact F ...]
    loop_state.py gate-pass STATE --node draft      --by WHO --workplan workplan.json [--artifact F ...]
    loop_state.py gate-pass STATE --node build      --by WHO --workplan workplan.json \\
                                  --reconciliation RECONCILIATION.md --verdicts DIR [--artifact F ...]
    loop_state.py check STATE
    loop_state.py record-approval STATE --human-present true|false --authority human|agent [--tier T]
    loop_state.py confirm STATE --by WHO [--escaped N --caught N]
    loop_state.py record-kill STATE --reason TEXT
    loop_state.py descope STATE --decision PATH

Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import node_gates  # noqa: E402

SCHEMA_PATH = HERE / "loop_state.schema.json"
STATE_FILENAME = "loop.state.json"
STAGES = ("understand", "decide", "draft", "build")
PREDECESSOR = {"understand": None, "decide": "understand", "draft": "decide", "build": "draft"}
_SLUG = re.compile(r"^[A-Za-z0-9_.-]+$")

EXIT_OK, EXIT_REFUSED, EXIT_USAGE, EXIT_HOLD = 0, 1, 2, 3


class Refused(Exception):
    """The request is well formed but the run's state does not allow it."""


class Unusable(Exception):
    """The request cannot be evaluated: a missing flag or an unreadable file."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Schema: a minimal draft-07 subset (required, type, enum, properties, items)
# ─────────────────────────────────────────────────────────────────────────────

_TYPES = {
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    if "type" in schema:
        allowed = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_TYPES[t](instance) for t in allowed):
            return [f"{path}: expected {schema['type']}, got {type(instance).__name__}"]
    errors: list[str] = []
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    if isinstance(instance, dict):
        errors += [f"{path}: missing {k!r}" for k in schema.get("required", []) if k not in instance]
        for key, sub in schema.get("properties", {}).items():
            if key in instance:
                errors += validate(instance[key], sub, f"{path}.{key}")
    elif isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors += validate(item, schema["items"], f"{path}[{index}]")
    return errors


# ─────────────────────────────────────────────────────────────────────────────
# The state file
# ─────────────────────────────────────────────────────────────────────────────


class Run:
    """One run: its folder and its state. Every change ends in save()."""

    def __init__(self, state_path: Path, data: dict[str, Any]):
        self.path = Path(state_path).resolve()
        self.dir = self.path.parent
        self.data = data

    @classmethod
    def load(cls, state_path: Path | str) -> "Run":
        try:
            data = json.loads(Path(state_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Unusable(f"state file unreadable: {state_path}: {exc}") from exc
        return cls(Path(state_path), data)

    def save(self) -> None:
        errors = validate(self.data, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
        if errors:
            raise RuntimeError("refusing to write an invalid state file: " + "; ".join(errors))
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=f".{STATE_FILENAME}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    # paths are stored relative to the run folder so a run can be moved or copied
    def rel(self, path: Path | str) -> str:
        resolved = Path(path).resolve()
        try:
            return resolved.relative_to(self.dir).as_posix()
        except ValueError:
            return str(resolved)

    def abs(self, stored: str) -> Path:
        candidate = Path(stored)
        return candidate if candidate.is_absolute() else self.dir / candidate

    def gate_passed(self, node: str) -> dict[str, Any] | None:
        passed = [g for g in self.data["gates"] if g["node"] == node and g["passed"]]
        return passed[-1] if passed else None

    def ensure_open(self) -> None:
        if self.data.get("final_route") is not None:
            raise Refused(f"the run has ended ({self.data['final_route']}); nothing more can change it")


def init(goal: str, input_path: Path, workspace: Path) -> Run:
    if not _SLUG.match(goal):
        raise Unusable(f"goal slug {goal!r} must match [A-Za-z0-9_.-]+ (it becomes the folder name)")
    try:
        original_input = Path(input_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise Unusable(f"input file unreadable: {input_path}: {exc}") from exc
    run_dir = Path(workspace) / goal
    state_path = run_dir / STATE_FILENAME
    if state_path.exists():
        raise Refused(f"a run already exists at {state_path}")
    run_dir.mkdir(parents=True, exist_ok=True)
    now = _now()
    run = Run(state_path, {
        "run_id": str(uuid.uuid4()),
        "goal_slug": goal,
        "original_input": original_input,
        "input_hash": hashlib.sha256(original_input.encode("utf-8")).hexdigest(),
        "status": "framing",
        "current_node": "framing",
        "trail": [{"node": "framing", "entered_at": now, "exited_at": None}],
        "artifacts": [],
        "gates": [],
        "budget": {"doubled_back_rounds": 0, "doubled_back_events": []},
        "driver": {"tier": None, "human_present": False, "authority": None},
        "kill": {"fired": False, "reason": None},
        "descope_decision_ref": None,
        "final_route": None,
        "escape_rate": None,
    })
    run.save()
    return run


def set_node(run: Run, node: str) -> None:
    """Enter a stage. Entering a stage needs the previous stage's gate; going
    back to an earlier stage is always allowed. A run that is live stays
    live: going back to fix something does not un-finish the build."""
    run.ensure_open()
    before = PREDECESSOR[node]
    if before is not None and run.gate_passed(before) is None:
        raise Refused(f"cannot enter {node}: the {before} gate has not passed")
    now = _now()
    trail = run.data["trail"]
    if trail and trail[-1]["exited_at"] is None:
        trail[-1]["exited_at"] = now
    trail.append({"node": node, "entered_at": now, "exited_at": None})
    run.data["current_node"] = node
    if run.data["status"] != "live":
        run.data["status"] = node
    run.save()


def check_frozen(run: Run) -> list[dict[str, str]]:
    """Re-hash every frozen artifact. Each changed (or vanished) file is one
    double-back; its recorded hash then moves to the new content, so the same
    edit is never counted twice. Saves only when something changed."""
    now = _now()
    mismatches: list[dict[str, str]] = []
    for artifact in run.data["artifacts"]:
        path = run.abs(artifact["path"])
        current = _sha256(path) if path.is_file() else "absent"
        if current != artifact["sha256"]:
            mismatches.append({"path": artifact["path"], "detected_at": now})
            artifact["sha256"] = current
    if mismatches:
        budget = run.data["budget"]
        budget["doubled_back_rounds"] += len(mismatches)
        budget["doubled_back_events"].extend(mismatches)
        run.save()
    return mismatches


def _freeze(run: Run, node: str, paths: list[Path], by: str) -> int:
    now = _now()
    by_path = {a["path"]: a for a in run.data["artifacts"]}
    count = 0
    for path in dict.fromkeys(Path(p).resolve() for p in paths):
        stored = run.rel(path)
        entry = {"path": stored, "sha256": _sha256(path), "frozen_at": now, "frozen_by": by, "node": node}
        if stored in by_path:
            by_path[stored].update(entry)
        else:
            run.data["artifacts"].append(entry)
            by_path[stored] = entry
        count += 1
    return count


def gate_pass(run: Run, node: str, by: str, evidence: dict[str, Path | None], extras: list[Path]):
    """Run the exit check for the current stage; on a pass, freeze and record.
    Returns (GateResult, frozen_count). A refusal or hold records nothing."""
    run.ensure_open()
    if run.data["current_node"] != node:
        raise Refused(f"gate-pass exits the current node, and the current node is {run.data['current_node']!r}")

    required = {
        "understand": ("tests",),
        "decide": ("mapping",),
        "draft": ("workplan",),
        "build": ("workplan", "reconciliation", "verdicts"),
    }[node]
    missing = [f"--{name}" for name in required if evidence.get(name) is None]
    if missing:
        raise Unusable(f"gate-pass --node {node} requires {' '.join(missing)}")
    absent = [str(p) for p in extras if not Path(p).is_file()]
    if absent:
        raise Unusable(f"artifact not found: {', '.join(absent)}")

    if node == "understand":
        result = node_gates.check_understand(tests=evidence["tests"])
        freeze = [evidence["tests"]]
    elif node == "decide":
        result = node_gates.check_decide(mapping=evidence["mapping"])
        freeze = [evidence["mapping"], *node_gates.mapping_files(evidence["mapping"])]
    elif node == "draft":
        result = node_gates.check_draft(workplan=evidence["workplan"])
        freeze = [evidence["workplan"], *node_gates.criteria_files(evidence["workplan"])]
    else:
        filed = run.gate_passed("draft")
        result = node_gates.check_build(
            workplan=evidence["workplan"],
            reconciliation=evidence["reconciliation"],
            verdicts_dir=evidence["verdicts"],
            not_before=filed["passed_at"] if filed else None,
        )
        freeze = [evidence["reconciliation"]]

    if not result.ok:
        return result, 0

    check_frozen(run)
    frozen = _freeze(run, node, [*freeze, *extras], by)
    run.data["gates"].append({"node": node, "passed": True, "passed_at": _now()})
    if node == "build":
        run.data["status"] = "live"
    run.save()
    return result, frozen


def record_approval(run: Run, *, tier: str | None, human_present: bool, authority: str) -> None:
    """Record who is driving. This writes down a grant a person already gave;
    it never creates one."""
    run.data["driver"] = {"tier": tier, "human_present": human_present, "authority": authority}
    run.save()


def confirm(run: Run, by: str, escaped: int = 0, caught: int = 0) -> None:
    """live -> done. Only a person can do this: the recorded authority must be
    `human`. escape_rate = escaped / (escaped + caught), or null if both are 0."""
    run.ensure_open()
    if run.data["status"] != "live":
        raise Refused(f"confirm needs status 'live', the run is {run.data['status']!r}")
    if run.data["driver"].get("authority") != "human":
        raise Refused("confirm needs driver authority 'human': a person confirms, an agent never does")
    total = escaped + caught
    run.data["escape_rate"] = escaped / total if total else None
    run.data["status"] = run.data["final_route"] = "done"
    run.save()


def record_kill(run: Run, reason: str) -> None:
    run.ensure_open()
    run.data["kill"] = {"fired": True, "reason": reason}
    run.data["status"] = run.data["final_route"] = "killed"
    run.save()


def descope(run: Run, decision_ref: str) -> None:
    run.ensure_open()
    run.data["descope_decision_ref"] = decision_ref
    run.data["status"] = run.data["final_route"] = "descoped"
    run.save()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────


def _bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in ("true", "yes", "1"):
        return True
    if lowered in ("false", "no", "0"):
        return False
    raise argparse.ArgumentTypeError(f"expected true or false, got {value!r}")


def _optional_path(value: str | None) -> Path | None:
    return Path(value) if value else None


def _summary(run: Run) -> str:
    d = run.data
    return f"status={d['status']} node={d['current_node']} gates={[g['node'] for g in d['gates']]}"


def _cmd(args: argparse.Namespace) -> int:
    if args.command == "init":
        run = init(args.goal, Path(args.input), Path(args.workspace or os.getcwd()))
        print(run.path)
        return EXIT_OK

    run = Run.load(args.state)
    if args.command == "read":
        print(json.dumps(run.data, indent=2, sort_keys=True))
    elif args.command == "set-node":
        set_node(run, args.node)
        print(_summary(run))
    elif args.command == "gate-pass":
        evidence = {name: _optional_path(getattr(args, name))
                    for name in ("tests", "mapping", "workplan", "reconciliation", "verdicts")}
        result, frozen = gate_pass(run, args.node, args.by, evidence, [Path(a) for a in args.artifact])
        if not result.ok:
            for line in result.messages:
                print(line, file=sys.stderr)
            print(f"gate {args.node}: {'HOLD' if result.hold else 'REFUSED'}; nothing recorded", file=sys.stderr)
            return EXIT_HOLD if result.hold else EXIT_REFUSED
        for line in result.messages:
            print(line)
        print(f"gate {args.node}: passed, {frozen} artifact(s) frozen; {_summary(run)}")
    elif args.command == "check":
        mismatches = check_frozen(run)
        print(json.dumps({"mismatches": mismatches,
                          "doubled_back_rounds": run.data["budget"]["doubled_back_rounds"]}, indent=2))
    elif args.command == "record-approval":
        record_approval(run, tier=args.tier, human_present=args.human_present, authority=args.authority)
        print(json.dumps(run.data["driver"]))
    elif args.command == "confirm":
        confirm(run, args.by, args.escaped, args.caught)
        print(_summary(run))
    elif args.command == "record-kill":
        record_kill(run, args.reason)
        print(_summary(run))
    elif args.command == "descope":
        descope(run, args.decision)
        print(_summary(run))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="loop_state.py", description="State file and gates of a working-loop run.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create <workspace>/<goal>/loop.state.json")
    p.add_argument("--goal", required=True)
    p.add_argument("--input", required=True, help="file holding the ask, verbatim")
    p.add_argument("--workspace", default=None, help="parent folder for the run (default: cwd)")

    p = sub.add_parser("read")
    p.add_argument("state")

    p = sub.add_parser("set-node", help="enter a stage")
    p.add_argument("state")
    p.add_argument("--node", required=True, choices=STAGES)

    p = sub.add_parser("gate-pass", help="run the current stage's exit check; freeze on pass")
    p.add_argument("state")
    p.add_argument("--node", required=True, choices=STAGES)
    p.add_argument("--by", required=True, help="who is passing the gate")
    p.add_argument("--artifact", nargs="*", default=[], help="extra files to freeze with the evidence")
    p.add_argument("--tests", help="understand: 01_understand/tests.json")
    p.add_argument("--mapping", help="decide: 02_decide/mapping.json")
    p.add_argument("--workplan", help="draft and build: 03_draft/workplan.json")
    p.add_argument("--reconciliation", help="build: RECONCILIATION.md")
    p.add_argument("--verdicts", help="build: the verifier-lite verdicts folder")

    p = sub.add_parser("check", help="re-hash frozen artifacts; count double-backs")
    p.add_argument("state")

    p = sub.add_parser("record-approval", help="record who is driving")
    p.add_argument("state")
    p.add_argument("--human-present", required=True, type=_bool, dest="human_present")
    p.add_argument("--authority", required=True)
    p.add_argument("--tier", default=None)

    p = sub.add_parser("confirm", help="live -> done; a person only")
    p.add_argument("state")
    p.add_argument("--by", required=True)
    p.add_argument("--escaped", type=int, default=0, help="defects the live test found that the loop's tests missed")
    p.add_argument("--caught", type=int, default=0, help="defects the loop's own tests caught first")

    p = sub.add_parser("record-kill", help="end the run as killed")
    p.add_argument("state")
    p.add_argument("--reason", required=True)

    p = sub.add_parser("descope", help="end the run as descoped")
    p.add_argument("state")
    p.add_argument("--decision", required=True, help="where the descope decision is written down")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _cmd(args)
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    except Unusable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows pipes default to the ANSI code page
    sys.exit(main())
