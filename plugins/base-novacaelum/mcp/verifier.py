#!/usr/bin/env python3
"""verifier.py -- verifier-lite: a deterministic acceptance-criteria checker.

A criteria file is JSON: {"id": ..., "criteria": [{"statement": ...,
"verification": {"kind": "file_state" | "command_check" | "manual", ...}}]}.
Each criterion resolves to pass / fail / uncertain; the overall verdict is
pass only if every criterion passes, fail if any fails, otherwise
uncertain. Standard library only. Importable as a plain module (no server
dependency); also runnable as a CLI.

Public API:
    evaluate_criterion(root, criterion, attestations) -> dict
    run_verification(criteria_file, root=None, attestations=None) -> dict
    write_verdict(root, verdict) -> Path

CLI:
    python3 verifier.py <criteria.json> [--root DIR] [--attest FILE]
    exits 0 pass / 1 fail / 2 uncertain, prints the verdict JSON to stdout.

Fail closed: any error while evaluating a criterion yields "uncertain",
never "pass".

A verdict never closes anything. A criteria file may carry "work_item": the
external_id of a Hyperspace Engine work item. When it does and Hyperspace
Engine is present (<root>/.hyperspace/graph.db), the verdict gains a
"next_step" line: close that item through Hyperspace Engine's
complete_workitem, its one closure door.
"""
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RESULT_PASS = "pass"
RESULT_FAIL = "fail"
RESULT_UNCERTAIN = "uncertain"


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso8601(value):
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _safe_relative(rel_path):
    """Refuse absolute, home-relative or parent-traversing paths."""
    if not rel_path or not isinstance(rel_path, str):
        return None, "missing or invalid path"
    if rel_path.startswith("~") or Path(rel_path).is_absolute():
        return None, f"absolute or home-relative path refused: {rel_path!r}"
    if ".." in Path(rel_path).parts:
        return None, f"parent-traversal path refused: {rel_path!r}"
    return rel_path, None


def _resolve_under_root(root, rel_path):
    safe_rel, err = _safe_relative(rel_path)
    if err:
        return None, err
    root_resolved = Path(root).resolve()
    full = (root_resolved / safe_rel).resolve()
    if full != root_resolved and root_resolved not in full.parents:
        return None, f"path escapes project root: {rel_path!r}"
    return full, None


def _eval_file_state(root, verification):
    path_val = verification.get("path")
    assertion = verification.get("assertion")
    full, err = _resolve_under_root(root, path_val)
    if err:
        return RESULT_UNCERTAIN, err

    if assertion == "exists":
        return (RESULT_PASS if full.exists() else RESULT_FAIL), str(full)

    if assertion == "not_exists":
        return (RESULT_PASS if not full.exists() else RESULT_FAIL), str(full)

    if assertion == "contains":
        expected = verification.get("expected")
        if expected is None:
            return RESULT_UNCERTAIN, "contains assertion missing 'expected'"
        if not full.exists():
            return RESULT_FAIL, f"{full} does not exist"
        try:
            text = full.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError) as exc:
            return RESULT_UNCERTAIN, f"could not read {full}: {exc}"
        return (RESULT_PASS if expected in text else RESULT_FAIL), f"looked for {expected!r} in {full}"

    if assertion == "modified_after":
        expected = verification.get("expected")
        if expected is None:
            return RESULT_UNCERTAIN, "modified_after assertion missing 'expected'"
        try:
            expected_dt = _parse_iso8601(expected)
        except (ValueError, TypeError) as exc:
            return RESULT_UNCERTAIN, f"malformed expected timestamp: {exc}"
        if not full.exists():
            return RESULT_FAIL, f"{full} does not exist"
        try:
            mtime = datetime.fromtimestamp(full.stat().st_mtime, tz=timezone.utc)
        except OSError as exc:
            return RESULT_UNCERTAIN, f"could not stat {full}: {exc}"
        evidence = f"mtime {mtime.isoformat()} vs expected {expected_dt.isoformat()}"
        return (RESULT_PASS if mtime > expected_dt else RESULT_FAIL), evidence

    return RESULT_UNCERTAIN, f"unknown assertion {assertion!r}"


def _run_subprocess(argv, cwd):
    try:
        return subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True), None
    except OSError as exc:
        return None, str(exc)


def _eval_command_check(root, verification):
    check_id = verification.get("check_id")

    if check_id == "tests":
        target = verification.get("target")
        safe_target, err = _safe_relative(target)
        if err:
            return RESULT_UNCERTAIN, err
        result, run_err = _run_subprocess(["python3", "-m", "unittest", safe_target], root)
        if run_err:
            return RESULT_UNCERTAIN, f"could not run tests: {run_err}"
        status = RESULT_PASS if result.returncode == 0 else RESULT_FAIL
        return status, ((result.stdout + result.stderr)[-2000:] or f"exit {result.returncode}")

    if check_id == "git_diff_nonempty":
        result, run_err = _run_subprocess(["git", "status", "--porcelain"], root)
        if run_err:
            return RESULT_UNCERTAIN, f"could not run git: {run_err}"
        if result.returncode != 0:
            return RESULT_UNCERTAIN, result.stderr.strip() or "git status failed"
        status = RESULT_PASS if result.stdout.strip() else RESULT_FAIL
        return status, (result.stdout.strip() or "working tree clean")

    commands_path = Path(root) / "verify.commands.json"
    if not commands_path.is_file():
        return RESULT_UNCERTAIN, f"unknown check_id {check_id!r} and no verify.commands.json"
    try:
        commands = json.loads(commands_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return RESULT_UNCERTAIN, f"could not read verify.commands.json: {exc}"
    argv = commands.get(check_id) if isinstance(commands, dict) else None
    if not isinstance(argv, list) or not argv:
        return RESULT_UNCERTAIN, f"check_id {check_id!r} not defined in verify.commands.json"
    result, run_err = _run_subprocess(argv, root)
    if run_err:
        return RESULT_UNCERTAIN, f"could not run {check_id!r}: {run_err}"
    status = RESULT_PASS if result.returncode == 0 else RESULT_FAIL
    return status, ((result.stdout + result.stderr)[-2000:] or f"exit {result.returncode}")


def _eval_manual(statement, attestations):
    for attestation in attestations or []:
        if isinstance(attestation, dict) and attestation.get("statement") == statement:
            return RESULT_PASS, f"attested by {attestation.get('attested_by', 'unknown')}"
    return RESULT_UNCERTAIN, "no matching attestation supplied"


def evaluate_criterion(root, criterion, attestations):
    """Evaluate one typed criterion. Never raises; fails closed to uncertain."""
    statement = criterion.get("statement", "")
    verification = criterion.get("verification", {}) or {}
    kind = verification.get("kind")
    try:
        if kind == "file_state":
            result, evidence = _eval_file_state(root, verification)
        elif kind == "command_check":
            result, evidence = _eval_command_check(root, verification)
        elif kind == "manual":
            result, evidence = _eval_manual(statement, attestations)
        else:
            result, evidence = RESULT_UNCERTAIN, f"unknown verification kind {kind!r}"
    except Exception as exc:  # fail closed: never let an error escape as a pass
        result, evidence = RESULT_UNCERTAIN, f"error evaluating criterion: {exc}"
    return {"statement": statement, "verification": verification, "result": result, "evidence": evidence}


def _overall(results):
    values = [r["result"] for r in results]
    if all(v == RESULT_PASS for v in values):
        return RESULT_PASS
    if any(v == RESULT_FAIL for v in values):
        return RESULT_FAIL
    return RESULT_UNCERTAIN


def write_verdict(root, verdict):
    verdicts_dir = Path(root) / "verdicts"
    verdicts_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", str(verdict.get("id", "unknown")))
    path = verdicts_dir / f"{safe_id}-{ts}.json"
    path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return path


def run_verification(criteria_file, root=None, attestations=None):
    """Evaluate a criteria file against root; writes and returns the verdict."""
    root_path = Path(root).expanduser().resolve() if root else Path.cwd()
    criteria_path = Path(criteria_file).expanduser()

    try:
        data = json.loads(criteria_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        verdict = {
            "id": criteria_path.stem or "unknown",
            "overall": RESULT_UNCERTAIN,
            "criteria": [],
            "error": f"could not load criteria file: {exc}",
            "timestamp": _now_iso(),
        }
        write_verdict(root_path, verdict)
        return verdict

    crit_id = data.get("id") or criteria_path.stem or "unknown"
    criteria_list = data.get("criteria") or []
    results = [evaluate_criterion(root_path, c, attestations or []) for c in criteria_list]
    overall = _overall(results) if results else RESULT_UNCERTAIN

    verdict = {"id": crit_id, "overall": overall, "criteria": results, "timestamp": _now_iso()}
    work_item = data.get("work_item")
    if isinstance(work_item, str) and work_item.strip() and (root_path / ".hyperspace" / "graph.db").is_file():
        verdict["next_step"] = (
            f"This verdict closes nothing. Close work item {work_item.strip()!r} through "
            "Hyperspace Engine's complete_workitem."
        )
    write_verdict(root_path, verdict)
    return verdict


def _cli(argv):
    parser = argparse.ArgumentParser(
        prog="verifier.py", description="Evaluate a typed acceptance-criteria file (verifier-lite)."
    )
    parser.add_argument("criteria_file")
    parser.add_argument("--root", default=None)
    parser.add_argument("--attest", default=None, help="Path to a JSON file: a list of {statement, attested_by}.")
    args = parser.parse_args(argv)

    attestations = None
    if args.attest:
        attestations = json.loads(Path(args.attest).expanduser().read_text(encoding="utf-8"))

    verdict = run_verification(args.criteria_file, root=args.root, attestations=attestations)
    print(json.dumps(verdict, indent=2))
    if verdict["overall"] == RESULT_PASS:
        return 0
    if verdict["overall"] == RESULT_FAIL:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
