#!/usr/bin/env python3
"""he_bridge.py -- Technical Cofounder on Hyperspace Engine's worklog store.

When Hyperspace Engine (HE) is installed in a project (it keeps
<project>/.hyperspace/graph.db), its SQLite store is the one worklog. This
module is TC's whole side of that arrangement; HE never knows TC exists.

Modes, read from .hyperspace/config.toml's top-level `worklog_owner`:
    tc          no .hyperspace/graph.db: TC alone, markdown worklog
    pending     graph.db, no owner yet: TC alone until the handshake runs
    tc-preload  owner "technical-cofounder": HE's store, TC's preload
    he-preload  any other owner: HE's store, HE's preload

The handshake (SessionStart, a set-up TC project, mode pending): import
worklog/entries into the store once, then append `worklog_owner` and, when
core_text/setup.json chose worklog_view "obsidian", `worklog_mirror_dir`, then
run `mirror --rebuild` once so HE rows written before the key existed get their
files (imported rows never do). A failed import writes no key and retries next
session. The import never runs again after the keys land: HE's import keys on
filename only, so it would take HE's own mirror files for new entries. A
failed rebuild is therefore one note naming the command, not a retry.
Keys are appended as scalar strings before any table, never rewriting a line.

Reads and writes go through HE's CLI contract (v0.1.2):
    <project>/.hyperspace/env/bin/python -m hyperspace.cli worklog <verb> ... --json
(env/Scripts/python.exe on Windows) and come back in the shape TC's own tools
return, with `file` None (the store is the record; TC never guesses HE's
mirror filenames). Any CLI failure raises BridgeError naming the fix. There is
no fallback to markdown: that would split the store.

Standard library only; no tomllib (the hook runs on the user's python3).

CLI:
    python3 he_bridge.py preload <project>   the handshake + the worklog block
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OWNER_KEY = "worklog_owner"
MIRROR_KEY = "worklog_mirror_dir"
TC_OWNER = "technical-cofounder"
ENTRIES = "worklog/entries"
SUMMARY_MAX = 280  # HE's append refuses more; TC's worklog.MAX_SUMMARY_LEN matches
CLI_TIMEOUT = 60
PRELOAD_N = 3
BODY_CAP = 400
GEAR_LINE = "Hyperspace Engine is installed: use its gear* skills for the working loop."

FIXES = {
    2: "the hyperspace CLI refused the request as invalid; correct it and retry",
    3: "this project has no Hyperspace store; run the hyperspace-setup skill (hyperspace init)",
}
FIX_UNEXPECTED = "Hyperspace Engine hit an internal error; run `hyperspace doctor` and check its install"

_ASSIGN = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=\s*(.*?)\s*$")
_STRING = re.compile(r"""^(?:"((?:[^"\\]|\\.)*)"|'([^']*)')\s*(?:#.*)?$""")


class BridgeError(RuntimeError):
    """A loud failure. The message says what broke and how to fix it."""


# ── config ────────────────────────────────────────────────────────────────

def _config_path(root):
    return Path(root) / ".hyperspace" / "config.toml"


def _top_level(text):
    """key -> raw value for each assignment before the first table header."""
    found = {}
    for line in text.splitlines():
        if line.lstrip().startswith("["):
            break
        match = _ASSIGN.match(line)
        if match:
            found.setdefault(match.group(1), match.group(2))
    return found


def read_key(root, key):
    """A top-level string value from config.toml, stripped; None when absent,
    blank, not a string, or unreadable (HE's own hook reads the same way)."""
    try:
        raw = _top_level(_config_path(root).read_text(encoding="utf-8")).get(key)
    except (OSError, UnicodeDecodeError):
        return None
    match = _STRING.match(raw or "")
    if not match:
        return None
    value = match.group(2)
    if match.group(1) is not None:
        try:
            value = json.loads(f'"{match.group(1)}"')
        except ValueError:
            value = match.group(1)
    return value.strip() or None


def mode(root):
    if not (Path(root) / ".hyperspace" / "graph.db").is_file():
        return "tc"
    owner = read_key(root, OWNER_KEY)
    if owner is None:
        return "pending"
    return "tc-preload" if owner == TC_OWNER else "he-preload"


def uses_store(root):
    """True when HE's store holds this project's worklog."""
    return mode(root) in ("tc-preload", "he-preload")


def _add_keys(root, keys):
    """Insert `key = "value"` lines for keys not already defined, before the
    first table header; every existing line stays byte-identical."""
    path = _config_path(root)
    text = path.read_text(encoding="utf-8")
    present = _top_level(text)
    new = [f"{key} = {json.dumps(value)}\n" for key, value in keys.items() if key not in present]
    if not new:
        return
    lines = text.splitlines(keepends=True)
    at = next((i for i, line in enumerate(lines) if line.lstrip().startswith("[")), len(lines))
    head = lines[:at]
    if head and not head[-1].endswith("\n"):
        head[-1] += "\n"
    tmp = path.with_name(path.name + ".tc-tmp")
    tmp.write_text("".join(head + new + lines[at:]), encoding="utf-8")
    tmp.replace(path)


def _worklog_view(root):
    try:
        record = json.loads((Path(root) / "core_text" / "setup.json").read_text(encoding="utf-8"))
        return record["choices"]["worklog_view"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def handshake(root):
    """Claim the preload for TC once. None when done or nothing to do; a
    one-line note when it failed (it retries next session). Never raises."""
    root = Path(root)
    try:
        if mode(root) != "pending":
            return None
        if (root / ENTRIES).is_dir():
            run_cli(root, "import", f"--from={ENTRIES}")
        obsidian = _worklog_view(root) == "obsidian"
        _add_keys(root, {OWNER_KEY: TC_OWNER, **({MIRROR_KEY: ENTRIES} if obsidian else {})})
        if obsidian:
            try:
                run_cli(root, "mirror", "--rebuild")
            except BridgeError as exc:
                return ("technical-cofounder: older Hyperspace rows have no Obsidian file yet; run "
                        f"`hyperspace worklog mirror --rebuild` once ({' '.join(str(exc).split())})")
        return None
    except Exception as exc:  # the session must never break over this
        detail = " ".join(str(exc).split())
        return f"technical-cofounder: the Hyperspace worklog handshake did not complete and retries next session ({detail})"


# ── the CLI ──────────────────────────────────────────────────────────────

def _interpreters(root):
    """HE's env interpreter layouts, this OS's own first."""
    env = Path(root) / ".hyperspace" / "env"
    posix, windows = env / "bin" / "python", env / "Scripts" / "python.exe"
    return (windows, posix) if os.name == "nt" else (posix, windows)


def interpreter(root):
    """HE's interpreter for this project, or None when neither layout exists."""
    return next((path for path in _interpreters(root) if path.exists()), None)


def run_cli(root, verb, *args):
    """One `hyperspace worklog <verb>` call; its JSON payload on success,
    BridgeError on anything else."""
    root = Path(root)
    python = interpreter(root)
    if python is None:
        expected = _interpreters(root)[0].as_posix()
        raise BridgeError(
            f"the hyperspace CLI is missing ({expected} not found). Fix: re-run the hyperspace-setup skill "
            "(or `hyperspace init --provision`) to rebuild .hyperspace/env. Nothing was written: while "
            "Hyperspace Engine holds this project's worklog, TC never falls back to markdown."
        )
    cmd = [str(python), "-m", "hyperspace.cli", "worklog", verb, *args, f"--dir={root}", "--json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CLI_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BridgeError(f"hyperspace worklog {verb} could not run ({exc}). Fix: {FIX_UNEXPECTED}") from None
    try:
        payload = json.loads(proc.stdout)
    except ValueError:
        payload = None
    if proc.returncode == 0 and isinstance(payload, dict) and payload.get("ok") is True:
        return payload
    error = payload.get("error") if isinstance(payload, dict) else "no JSON on stdout"
    fix = FIXES.get(proc.returncode, FIX_UNEXPECTED)
    raise BridgeError(f"hyperspace worklog {verb} failed (exit {proc.returncode}): {error}. Fix: {fix}")


def _tc_date(created_at):
    try:
        return datetime.fromisoformat(created_at).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return created_at or ""


def _tc_entry(row):
    tags = row.get("tags")
    return {
        "date": _tc_date(row.get("created_at")),
        "author": row.get("author") or "",
        "summary": row.get("summary") or "",
        "tags": tags if isinstance(tags, list) else [],
        "body": row.get("detailed") or "",
        "file": None,
        "row_id": row.get("id"),
    }


# ── worklog.py's API, over the store ──────────────────────────────────────

def append(root, summary, detail="", author="agent", tags=None):
    if len(summary) > SUMMARY_MAX:
        raise ValueError(f"summary exceeds {SUMMARY_MAX} characters ({len(summary)})")
    tags = list(tags or [])
    if any("," in tag for tag in tags):
        raise ValueError("a tag contains a comma, which the hyperspace CLI would split in two; rename the tag")
    args = [f"--author={author}", f"--summary={summary}"]
    if detail:
        args.append(f"--detail={detail}")
    if tags:
        args.append("--tags=" + ",".join(tags))
    entry = run_cli(root, "append", *args)["entry"]
    return {"file": None, "csv_error": None, "row_id": entry["id"]}


def recent(root, n=5):
    return [_tc_entry(row) for row in run_cli(root, "recent", f"--limit={int(n)}")["entries"]]


def search(root, query):
    """TC's match (summary, body, tags, author; case-insensitive) over every
    row, newest first. HE's own --query covers summary and body only."""
    needle = query.lower()
    matches = []
    for row in run_cli(root, "search")["entries"]:
        entry = _tc_entry(row)
        haystack = " ".join([entry["summary"], entry["body"], " ".join(entry["tags"]), entry["author"]]).lower()
        if needle in haystack:
            matches.append(entry)
    return matches


# ── SessionStart ─────────────────────────────────────────────────────────

def worklog_block(root, n=PRELOAD_N):
    lines = [f"## Recent worklog — last {n}", ""]
    try:
        entries = recent(root, n)
    except BridgeError as exc:
        entries = []
        lines.append(f"(worklog unavailable: {' '.join(str(exc).split())})")
    else:
        if not entries:
            lines.append("(no worklog entries yet)")
    for entry in entries:
        lines.append(f"--- {entry['date']} · {entry['author']} ---")
        lines.append(entry["summary"])
        if entry["tags"]:
            lines.append("tags: " + ", ".join(entry["tags"]))
        body = entry["body"].strip()
        if body:
            lines.append(body if len(body) <= BODY_CAP else body[:BODY_CAP].rstrip() + " …")
        lines.append("")
    lines.append(GEAR_LINE)
    return "\n".join(lines)


def preload_text(root):
    """The handshake (and its one-line note, if any), then TC's worklog block
    when TC owns the preload. Otherwise HE's own hook shows the worklog."""
    note = handshake(root)
    block = worklog_block(root) if mode(root) == "tc-preload" else ""
    return "\n".join(part for part in (note, block) if part)


def main(argv):
    if len(argv) != 2 or argv[0] != "preload":
        sys.stderr.write("usage: he_bridge.py preload <project>\n")
        return 2
    try:
        text = preload_text(argv[1])
    except Exception as exc:  # never break the session
        text = f"(worklog unavailable: {type(exc).__name__})"
    if text:
        print(text)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows pipes default to the ANSI code page
    sys.exit(main(sys.argv[1:]))
