#!/usr/bin/env python3
"""Keep a project's setup record and render its setup guide.

Usage:
    python3 setup_record.py set <project> <step-id> done|skipped|pending [--choice key=value ...]
    python3 setup_record.py status <project>
    python3 setup_record.py render <project>

The steps come from ../setup/steps.json, the one list the setup skill, this
script and the session preload share. Everything this script writes lives in
<project>/core_text/:

  setup.json        the record: each step's status and when it changed, plus
                    the few choices a step declares (never free text, never
                    a key)
  setup-guide.html  the guide, one self-contained page rendered from
                    steps.json and the record

Every subcommand first creates setup.json when it is absent (all steps
pending). An existing record is never replaced; a step added to steps.json
later reads as pending. `set` refuses an unknown step, a choice key the step
does not declare, and a value that is longer than 40 characters, is not a
plain word, or looks like a key, path or email. A refusal never echoes the
value and never touches the record.

Exit codes: 0 ok, 1 refused or unreadable record, 2 usage. Standard library
only.
"""
import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
STEPS_FILE = PLUGIN_ROOT / "setup" / "steps.json"
PLUGIN_JSON = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"

sys.path.insert(0, str(HERE))
from ask_issue import redact_text  # noqa: E402  (key-, path- and email-shaped patterns)

STATUSES = ("done", "skipped", "pending")
MAX_VALUE = 40
PLAIN_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+-]*$")
MARKS = {"done": ("done", "✓ Done"), "skipped": ("skipped", "Skipped"), "pending": ("todo", "To do")}


class Refused(Exception):
    """A request this script will not carry out. The message never holds user input."""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_steps():
    return json.loads(STEPS_FILE.read_text(encoding="utf-8"))["steps"]


def plugin_version():
    try:
        return str(json.loads(PLUGIN_JSON.read_text(encoding="utf-8")).get("version", "unknown"))
    except (OSError, ValueError):
        return "unknown"


def record_path(project):
    return Path(project).expanduser().resolve() / "core_text" / "setup.json"


def write_json(path, data):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_record(project, steps):
    """The project's record, created first when absent. Steps missing from an
    older record are filled in as pending in memory only."""
    path = record_path(project)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = now()
        write_json(path, {
            "schema_version": 1,
            "plugin_version": plugin_version(),
            "created": stamp,
            "updated": stamp,
            "steps": {s["id"]: {"status": "pending", "at": None} for s in steps},
            "choices": {},
        })
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rec.get("steps"), dict) or not isinstance(rec.get("choices"), dict):
            raise ValueError("steps or choices is not an object")
    except (OSError, ValueError, AttributeError) as exc:
        raise Refused(f"core_text/setup.json is unreadable ({type(exc).__name__}); left untouched") from None
    for s in steps:
        entry = rec["steps"].get(s["id"])
        if not isinstance(entry, dict) or entry.get("status") not in STATUSES:
            rec["steps"][s["id"]] = {"status": "pending", "at": None}
    return rec


def check_value(key, value):
    if len(value) > MAX_VALUE:
        raise Refused(f"choice {key!r}: value is over {MAX_VALUE} characters; not recorded")
    if not PLAIN_VALUE_RE.match(value) or redact_text(value)[1]:
        raise Refused(f"choice {key!r}: value is not a plain word or looks like a key, path or email; not recorded")


def set_step(project, step_id, status, pairs):
    steps = load_steps()
    rec = load_record(project, steps)
    step = next((s for s in steps if s["id"] == step_id), None)
    if step is None:
        raise Refused(f"unknown step; steps are: {', '.join(s['id'] for s in steps)}")
    if status not in STATUSES:
        raise Refused(f"unknown status; use one of: {', '.join(STATUSES)}")
    choices = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or key not in step["choices"]:
            declared = ", ".join(step["choices"]) or "none"
            raise Refused(f"step {step_id!r} declares choices: {declared}; pass them as key=value")
        check_value(key, value)
        choices[key] = value
    stamp = now()
    rec["steps"][step_id] = {"status": status, "at": None if status == "pending" else stamp}
    rec["choices"].update(choices)
    rec["updated"] = stamp
    write_json(record_path(project), rec)
    return rec


def status_lines(project):
    steps = load_steps()
    rec = load_record(project, steps)
    width = max(len(s["id"]) for s in steps)
    lines = [f"{'step':<{width}}  {'status':<8}  minutes"]
    for s in steps:
        lines.append(f"{s['id']:<{width}}  {rec['steps'][s['id']]['status']:<8}  {s['minutes']}")
    done = sum(rec["steps"][s["id"]]["status"] == "done" for s in steps)
    lines.append(f"DONE {done}/{len(steps)}")
    return lines


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Your setup guide</title>
<style>
:root {{ --bg: #ffffff; --fg: #1f2328; --muted: #59636e; --line: #d1d9e0; --done: #1a7f37; --todo: #9a6700; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #0d1117; --fg: #e6edf3; --muted: #9198a1; --line: #30363d; --done: #3fb950; --todo: #d29922; }}
}}
body {{ margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
main {{ max-width: 68rem; margin: 0 auto; padding: 2rem 1.25rem 3rem; }}
h1 {{ margin: 0 0 .25rem; font-size: 1.6rem; }}
p {{ margin: .25rem 0; }}
.muted {{ color: var(--muted); }}
.totals {{ margin: 1rem 0 1.5rem; font-weight: 600; }}
.scroll {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: .75rem .6rem; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
th {{ font-size: .8rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; white-space: nowrap; }}
td small {{ display: block; color: var(--muted); font-size: .9rem; }}
.done {{ color: var(--done); font-weight: 600; white-space: nowrap; }}
.todo {{ color: var(--todo); font-weight: 600; white-space: nowrap; }}
.skipped {{ color: var(--muted); white-space: nowrap; }}
.num {{ text-align: right; }}
footer {{ margin-top: 1.5rem; }}
</style>
</head>
<body>
<main>
<h1>Your setup guide</h1>
<p class="muted">Every step of setting up this project: what it does, why it matters, and whether it is safe to skip for now.</p>
<p class="totals">About {total} minutes in all. {left} minutes left for the steps still to do. {done} of {count} done.</p>
<div class="scroll">
<table>
<thead><tr><th>Status</th><th>Step</th><th>Why it matters</th><th>OK to skip?</th><th>If you skip it</th><th class="num">Minutes</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</div>
<footer>
<p>Say “continue setup” to Claude to pick up any step.</p>
<p class="muted">Updated {updated} · base-novacaelum {version}</p>
</footer>
</main>
</body>
</html>
"""

ROW = (
    '<tr><td class="{cls}">{mark}</td><td><strong>{title}</strong><small>{does}</small></td>'
    '<td>{why}</td><td>{skip}</td><td>{if_skipped}</td><td class="num">{minutes}</td></tr>'
)


def render(project):
    steps = load_steps()
    rec = load_record(project, steps)
    e = html.escape
    rows, left, done = [], 0, 0
    for s in steps:
        status = rec["steps"][s["id"]]["status"]
        cls, mark = MARKS.get(status, MARKS["pending"])
        left += s["minutes"] if status == "pending" else 0
        done += status == "done"
        rows.append(ROW.format(
            cls=cls, mark=mark, title=e(s["title"]), does=e(s["does"]), why=e(s["why"]),
            skip="Yes" if s["skippable"] else "No", if_skipped=e(s["if_skipped"]), minutes=s["minutes"],
        ))
    out = record_path(project).with_name("setup-guide.html")
    out.write_text(PAGE.format(
        total=sum(s["minutes"] for s in steps), left=left, done=done, count=len(steps), rows="\n".join(rows),
        updated=e(str(rec.get("updated", "")).replace("T", " ").replace("Z", " UTC")),
        version=e(str(rec.get("plugin_version", ""))),
    ), encoding="utf-8")
    return out


def main(argv):
    parser = argparse.ArgumentParser(prog="setup_record.py", description="Keep a project's setup record and render its guide.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_set = sub.add_parser("set", help="record a step's status (and its declared choices), then render")
    p_set.add_argument("project")
    p_set.add_argument("step")
    p_set.add_argument("status")
    p_set.add_argument("--choice", action="append", default=[], metavar="key=value")
    for name, text in (("status", "print each step's status and a DONE n/m line"), ("render", "write core_text/setup-guide.html")):
        sub.add_parser(name, help=text).add_argument("project")
    args = parser.parse_args(argv[1:])

    try:
        if args.cmd == "set":
            set_step(args.project, args.step, args.status, args.choice)
            print(f"RECORDED: {args.step} {args.status}")
            print(f"RENDERED: core_text/{render(args.project).name}")
        elif args.cmd == "status":
            print("\n".join(status_lines(args.project)))
        else:
            print(f"RENDERED: core_text/{render(args.project).name}")
    except Refused as exc:
        sys.stderr.write(f"REFUSED: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
