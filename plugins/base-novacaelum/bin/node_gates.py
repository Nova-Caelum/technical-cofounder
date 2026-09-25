#!/usr/bin/env python3
"""node_gates.py -- the exit check for each stage of the working loop.

An exit gate is how a stage proves it is finished. Each check reads files
and nothing else: no network, no hosted service, standard library only.
`loop_state.py gate-pass` runs the check for the stage being exited and
records the gate as passed only when the check says so.

    understand  tests.json is a valid criteria file (the verifier-lite
                format), with at least one non-manual criterion and at least
                one statement beginning `WHOLE-PATH:`
    decide      mapping.json maps every test to a component, and every
                component is kept by a test, kept by a declared principle, or
                named under `## Deferred`
    draft       every workplan task has a unique id and a valid criteria file
                whose id matches, and every test is served by some task
    build       every workplan row is declared in RECONCILIATION.md; a `done`
                row needs a verifier-lite verdict with overall `pass` on the
                row's own criteria; `deferred` and `live-test` rows need none

A check returns a GateResult. `ok` passes. `hold` is the build gate's third
answer: nothing is wrong except criteria only a person can attest, and the
messages list them. Every other failure is a refusal, and every refusal in a
file is listed at once so the driver fixes a stage in one pass.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

KINDS = ("file_state", "command_check", "manual")
FILE_ASSERTIONS = ("exists", "not_exists", "contains", "modified_after")

_WHOLE_PATH = re.compile(r"^\s*WHOLE-PATH:", re.IGNORECASE)
_TEST_ID = re.compile(r"^T[1-9]\d*$")
_ROW_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
_DEFERRED_HEADING = re.compile(r"^## Deferred\s*$")
_DEFERRED_BULLET = re.compile(r"^\s*[-*]\s+\*\*(.+?)\*\*")

#: One reconciliation line: `- <row id> → <disposition>` (or `->`), then any
#: notes. The alternation IS the validation: a typo'd disposition does not
#: match, so its row reads as absent and the gate refuses (fails closed).
_RECONCILIATION_LINE = re.compile(r"^\s*[-*]\s*(?P<id>\S+)\s+(?:→|->)\s+(?P<disposition>done|deferred|live-test)\b")

#: A principle may be cited to keep a component only while it is active.
_CITABLE_PRINCIPLE_STATES = frozenset({"active"})


@dataclass
class GateResult:
    ok: bool
    hold: bool = False
    messages: list[str] = field(default_factory=list)


def _refuse(messages: list[str]) -> GateResult:
    return GateResult(ok=False, hold=False, messages=messages)


def _load_json_object(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _resolve_beside(anchor: Path, value: str) -> Path:
    """A file reference resolved relative to the directory of the file that
    names it; an absolute reference is used as-is."""
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (Path(anchor).resolve().parent / candidate).resolve()


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Criteria files (the verifier-lite format)
# ─────────────────────────────────────────────────────────────────────────────


def _path_problem(value: Any) -> str | None:
    """Why a criterion path could never be checked as written, or None."""
    if not isinstance(value, str) or not value.strip():
        return "missing"
    if value.startswith("~") or Path(value).is_absolute():
        return "absolute or home-relative (paths are relative to the project root)"
    if ".." in Path(value).parts:
        return "climbs out of the project root with '..'"
    if "<" in value or ">" in value:
        return "carries a <placeholder>, which can never be true on disk"
    return None


def validate_criteria(data: Any) -> list[str]:
    """Structural check of one criteria file against the verifier-lite
    format. Returns every problem found; an empty list means valid. It does
    not run anything: whether a criterion can fail today is the author's
    self-review, not something a file read can see."""
    if not isinstance(data, dict):
        return ["criteria file is not a JSON object"]
    problems: list[str] = []
    if not isinstance(data.get("id"), str) or not data["id"].strip():
        problems.append("criteria file has no id")
    criteria = data.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return problems + ["criteria file declares no criteria"]

    for index, item in enumerate(criteria, start=1):
        where = f"criterion {index}"
        if not isinstance(item, dict):
            problems.append(f"{where}: not an object")
            continue
        if not isinstance(item.get("statement"), str) or not item["statement"].strip():
            problems.append(f"{where}: no statement")
        verification = item.get("verification")
        if not isinstance(verification, dict):
            problems.append(f"{where}: no verification object")
            continue
        kind = verification.get("kind")
        if kind not in KINDS:
            problems.append(f"{where}: unknown verification kind {kind!r} (expected one of {', '.join(KINDS)})")
        elif kind == "file_state":
            issue = _path_problem(verification.get("path"))
            if issue:
                problems.append(f"{where}: path {issue}")
            assertion = verification.get("assertion")
            if assertion not in FILE_ASSERTIONS:
                problems.append(f"{where}: unknown file_state assertion {assertion!r}")
            elif assertion == "contains" and not isinstance(verification.get("expected"), str):
                problems.append(f"{where}: contains needs an expected string")
            elif assertion == "modified_after" and _parse_time(verification.get("expected")) is None:
                problems.append(f"{where}: modified_after needs an ISO-8601 expected timestamp")
        elif kind == "command_check":
            check_id = verification.get("check_id")
            if not isinstance(check_id, str) or not check_id.strip():
                problems.append(f"{where}: command_check needs a check_id")
            elif check_id == "tests":
                issue = _path_problem(verification.get("target"))
                if issue:
                    problems.append(f"{where}: tests target {issue}")
        elif kind == "manual":
            instruction = verification.get("instruction")
            if not isinstance(instruction, str) or not instruction.strip():
                problems.append(f"{where}: manual needs an instruction a person can follow")
    return problems


def _executable_count(data: dict[str, Any]) -> int:
    return sum(
        1 for c in data.get("criteria", [])
        if isinstance(c, dict) and isinstance(c.get("verification"), dict)
        and c["verification"].get("kind") != "manual"
    )


# ─────────────────────────────────────────────────────────────────────────────
# understand
# ─────────────────────────────────────────────────────────────────────────────


def check_understand(tests: Path) -> GateResult:
    """tests.json defines finished before anything is designed."""
    data = _load_json_object(tests)
    if data is None:
        return _refuse([f"tests file unreadable or not a JSON object: {tests}"])
    problems = validate_criteria(data)
    if problems:
        return _refuse([f"tests.json: {p}" for p in problems])

    criteria = data["criteria"]
    messages: list[str] = []
    executable = _executable_count(data)
    whole_path = sum(1 for c in criteria if _WHOLE_PATH.match(c["statement"]))
    if executable == 0:
        messages.append("no non-manual criterion: an all-manual set cannot be checked by any machine")
    if whole_path == 0:
        messages.append(
            "no WHOLE-PATH: criterion: at least one statement must begin 'WHOLE-PATH:' and walk "
            "from the entry action to the terminal effect"
        )
    if messages:
        return _refuse(messages)
    return GateResult(ok=True, messages=[
        f"tests.json valid: {len(criteria)} criteria, {executable} executable, {whole_path} whole-path"
    ])


# ─────────────────────────────────────────────────────────────────────────────
# decide
# ─────────────────────────────────────────────────────────────────────────────


def _deferred_names(text: str) -> set[str]:
    """Bold names of the bullets under `## Deferred`, up to the next `## `."""
    names: set[str] = set()
    inside = False
    for line in text.splitlines():
        if _DEFERRED_HEADING.match(line):
            inside = True
            continue
        if line.startswith("## "):
            inside = False
            continue
        if inside:
            match = _DEFERRED_BULLET.match(line)
            if match:
                names.add(match.group(1))
    return names


def check_decide(mapping: Path) -> GateResult:
    """Every test maps to a component; every component earns its place."""
    mapping = Path(mapping)
    data = _load_json_object(mapping)
    if data is None:
        return _refuse([f"mapping file unreadable or not a JSON object: {mapping}"])

    messages: list[str] = []
    for key in ("tests_file", "deferred_file", "principles_file"):
        if not isinstance(data.get(key), str) or not data[key]:
            messages.append(f"mapping missing key: {key}")
    if not isinstance(data.get("components"), list):
        messages.append("mapping missing key: components")
    if messages:
        return _refuse(messages)

    tests_path = _resolve_beside(mapping, data["tests_file"])
    principles_path = _resolve_beside(mapping, data["principles_file"])
    deferred_path = _resolve_beside(mapping, data["deferred_file"])

    tests = _load_json_object(tests_path)
    if tests is None or not isinstance(tests.get("criteria"), list) or not tests["criteria"]:
        messages.append(f"tests file unreadable or declares no criteria: {tests_path}")
    principles = _load_json_object(principles_path)
    if principles is None or not isinstance(principles.get("principles"), list):
        messages.append(f"principles file unreadable or has no principles list: {principles_path}")
    try:
        deferred = _deferred_names(deferred_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        deferred = set()
        messages.append(f"deferred file unreadable: {deferred_path}")
    if messages:
        return _refuse(messages)

    n_tests = len(tests["criteria"])
    states = {
        p["id"]: str(p.get("state"))
        for p in principles["principles"]
        if isinstance(p, dict) and isinstance(p.get("id"), str)
    }
    components = data["components"]
    if not components:
        return _refuse(["mapping names no components"])

    seen: set[str] = set()
    referenced: set[str] = set()
    counts = {"test": 0, "principle": 0, "deferred": 0}
    for component in components:
        name = component.get("name") if isinstance(component, dict) else None
        if not isinstance(name, str) or not name:
            messages.append("component has no name")
            continue
        if name in seen:
            messages.append(f"duplicate component name: {name}")
        seen.add(name)

        test_ids = component.get("tests") or []
        principle_ids = component.get("principles") or []
        if not isinstance(test_ids, list):
            messages.append(f"{name}: tests must be a list of test ids")
            test_ids = []
        if not isinstance(principle_ids, list):
            messages.append(f"{name}: principles must be a list of principle ids")
            principle_ids = []

        for test_id in map(str, test_ids):
            if _TEST_ID.match(test_id) and int(test_id[1:]) <= n_tests:
                referenced.add(test_id)
            else:
                messages.append(f"{name}: unknown test id {test_id} (tests.json declares T1..T{n_tests})")
        for principle in map(str, principle_ids):
            state = states.get(principle)
            if state is None:
                messages.append(f"{name}: unknown principle {principle}: not in principles.json")
            elif state not in _CITABLE_PRINCIPLE_STATES:
                messages.append(f"{name}: principle {principle} is {state}, not active")

        if test_ids:
            counts["test"] += 1
        elif principle_ids:
            counts["principle"] += 1
        elif name in deferred:
            counts["deferred"] += 1
        else:
            messages.append(f"{name}: unmapped: no test, no principle, and not named under ## Deferred in {deferred_path.name}")

    for index in range(1, n_tests + 1):
        if f"T{index}" not in referenced:
            messages.append(f"T{index} maps to no component")

    if messages:
        return _refuse(messages)
    return GateResult(ok=True, messages=[
        f"mapping valid: {n_tests} tests, {len(components)} components ({counts['test']} kept by test, "
        f"{counts['principle']} kept by principle, {counts['deferred']} deferred)"
    ])


# ─────────────────────────────────────────────────────────────────────────────
# draft
# ─────────────────────────────────────────────────────────────────────────────


def _workplan_tasks(workplan: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    data = _load_json_object(workplan)
    if data is None:
        return None, []
    tasks = data.get("tasks")
    return data, [t for t in tasks if isinstance(t, dict)] if isinstance(tasks, list) else []


def check_draft(workplan: Path) -> GateResult:
    """The plan is tracked work: every task can be closed by a verifier."""
    workplan = Path(workplan)
    data, tasks = _workplan_tasks(workplan)
    if data is None:
        return _refuse([f"workplan unreadable or not a JSON object: {workplan}"])
    if not tasks:
        return _refuse(["workplan declares no tasks"])

    messages: list[str] = []
    n_tests = 0
    if not isinstance(data.get("tests_file"), str) or not data["tests_file"]:
        messages.append("workplan missing key: tests_file")
    else:
        tests = _load_json_object(_resolve_beside(workplan, data["tests_file"]))
        if tests is None or not isinstance(tests.get("criteria"), list):
            messages.append(f"tests file unreadable: {data['tests_file']}")
        else:
            n_tests = len(tests["criteria"])

    seen: set[str] = set()
    served: set[str] = set()
    for position, task in enumerate(tasks, start=1):
        row_id = task.get("id")
        if not isinstance(row_id, str) or not _ROW_ID.match(row_id):
            messages.append(f"task {position}: id missing or not [A-Za-z0-9_.-]+")
            continue
        if row_id in seen:
            messages.append(f"{row_id}: duplicate task id")
        seen.add(row_id)

        for test_id in map(str, task.get("serves") or []):
            if _TEST_ID.match(test_id) and int(test_id[1:]) <= n_tests:
                served.add(test_id)
            else:
                messages.append(f"{row_id}: serves unknown test id {test_id}")

        ref = task.get("criteria")
        if not isinstance(ref, str) or not ref:
            messages.append(f"{row_id}: no criteria file")
            continue
        criteria_path = _resolve_beside(workplan, ref)
        criteria = _load_json_object(criteria_path)
        if criteria is None:
            messages.append(f"{row_id}: criteria file missing or unreadable: {ref}")
            continue
        messages.extend(f"{row_id}: {p}" for p in validate_criteria(criteria))
        if criteria.get("id") != row_id:
            messages.append(f"{row_id}: criteria file id {criteria.get('id')!r} does not match the task id")
        if _executable_count(criteria) == 0:
            messages.append(f"{row_id}: every criterion is manual, so no verifier can ever close this row")

    for index in range(1, n_tests + 1):
        if f"T{index}" not in served:
            messages.append(f"T{index} is served by no task")

    if messages:
        return _refuse(messages)
    return GateResult(ok=True, messages=[f"workplan valid: {len(tasks)} tasks, T1..T{n_tests} all served"])


def mapping_files(mapping: Path) -> list[Path]:
    """The files a mapping points at. The decide gate freezes them with it."""
    data = _load_json_object(Path(mapping)) or {}
    return [
        _resolve_beside(Path(mapping), data[key])
        for key in ("deferred_file", "principles_file")
        if isinstance(data.get(key), str) and data[key]
    ]


def criteria_files(workplan: Path) -> list[Path]:
    """Every criteria file the workplan names, resolved. The draft gate
    freezes these with the workplan, so an edit after filing is visible."""
    _, tasks = _workplan_tasks(Path(workplan))
    return [
        _resolve_beside(Path(workplan), t["criteria"])
        for t in tasks if isinstance(t.get("criteria"), str) and t["criteria"]
    ]


# ─────────────────────────────────────────────────────────────────────────────
# build
# ─────────────────────────────────────────────────────────────────────────────


def _latest_verdict(verdicts_dir: Path, row_id: str) -> dict[str, Any] | None:
    """The newest verdict whose `id` is this row's. verifier-lite names files
    `<id>-<UTC second>.json` and a same-second rerun overwrites, so the
    timestamp is unique per row and `max` is well defined."""
    best: dict[str, Any] | None = None
    best_time: datetime | None = None
    if not Path(verdicts_dir).is_dir():
        return None
    for path in sorted(Path(verdicts_dir).glob("*.json")):
        data = _load_json_object(path)
        if data is None or data.get("id") != row_id:
            continue
        when = _parse_time(data.get("timestamp"))
        if when is None:
            continue
        if best_time is None or when > best_time:
            best, best_time = data, when
    return best


def check_build(
    workplan: Path,
    reconciliation: Path,
    verdicts_dir: Path,
    not_before: str | None = None,
) -> GateResult:
    """Every row is accounted for, and every `done` is the verifier's word.

    `not_before` is when the plan was filed (the draft gate's pass time):
    a verdict older than the plan says nothing about work done under it.
    """
    workplan = Path(workplan)
    data, tasks = _workplan_tasks(workplan)
    if data is None:
        return _refuse([f"workplan unreadable or not a JSON object: {workplan}"])
    rows = {t["id"]: t for t in tasks if isinstance(t.get("id"), str)}
    if not rows:
        return _refuse(["workplan declares no tasks with an id"])

    try:
        text = Path(reconciliation).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return _refuse([f"reconciliation unreadable: {reconciliation}"])
    dispositions: dict[str, str] = {}
    for line in text.splitlines():
        match = _RECONCILIATION_LINE.match(line)
        if match:
            dispositions[match.group("id")] = match.group("disposition")

    cutoff = _parse_time(not_before)
    if cutoff is not None:
        cutoff = cutoff.replace(microsecond=0)  # verdict timestamps are whole seconds

    messages: list[str] = []
    refused = False
    for row_id in dispositions:
        if row_id not in rows:
            messages.append(f"{row_id}: in the reconciliation but not in the workplan")
            refused = True

    for row_id, task in rows.items():
        disposition = dispositions.get(row_id)
        if disposition is None:
            messages.append(
                f"{row_id}: no disposition in {Path(reconciliation).name}: every row is done, deferred, or live-test"
            )
            refused = True
            continue
        if disposition in ("deferred", "live-test"):
            continue

        criteria = _load_json_object(_resolve_beside(workplan, str(task.get("criteria") or "")))
        if criteria is None or not isinstance(criteria.get("criteria"), list):
            messages.append(f"{row_id}: criteria file missing or unreadable: {task.get('criteria')}")
            refused = True
            continue
        expected = [c.get("statement") for c in criteria["criteria"] if isinstance(c, dict)]
        verdict = _latest_verdict(Path(verdicts_dir), row_id)
        if verdict is None:
            messages.append(f"{row_id}: declared done but no verifier-lite verdict found in {verdicts_dir}")
            refused = True
            continue
        if cutoff is not None and _parse_time(verdict.get("timestamp")) < cutoff:
            messages.append(f"{row_id}: latest verdict ({verdict.get('timestamp')}) is from before the plan was filed")
            refused = True
            continue
        judged = verdict.get("criteria") if isinstance(verdict.get("criteria"), list) else []
        if [c.get("statement") for c in judged if isinstance(c, dict)] != expected or not expected:
            messages.append(f"{row_id}: latest verdict judged different criteria than the row's criteria file")
            refused = True
            continue

        overall = verdict.get("overall")
        if overall == "pass":
            continue
        open_items = [c for c in judged if isinstance(c, dict) and c.get("result") != "pass"]
        manual_only = overall == "uncertain" and all(
            (c.get("verification") or {}).get("kind") == "manual" and c.get("result") == "uncertain"
            for c in open_items
        )
        if manual_only:
            messages.extend(f"{row_id} → {c.get('statement')}" for c in open_items)
            messages.append(f"{row_id}: waiting on a person's attestation (the lines above), nothing else open")
        else:
            messages.append(f"{row_id}: latest verdict is {overall!r}, not pass")
            refused = True

    if not messages:
        return GateResult(ok=True, messages=[f"build closed: {len(rows)} rows accounted for"])
    if refused:
        return _refuse(messages)
    return GateResult(ok=False, hold=True, messages=messages)


#: node -> check. `gate-pass` accepts these four nodes and no others.
CHECKS: dict[str, Callable[..., GateResult]] = {
    "understand": check_understand,
    "decide": check_decide,
    "draft": check_draft,
    "build": check_build,
}
