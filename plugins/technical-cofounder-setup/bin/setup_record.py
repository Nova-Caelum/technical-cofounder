#!/usr/bin/env python3
"""Keep a project's setup record and render its setup guide.

Usage:
    python3 setup_record.py set <project> <step-id> done|skipped|pending [--choice key=value ...]
    python3 setup_record.py status <project>
    python3 setup_record.py render <project>

The steps come from the `steps` list in ../setup/steps.json, which the setup
skill reads too. Everything this script writes lives in <project>/core_text/:

  setup.json        the record: each step's status, when it changed and which
                    part of the guide it belongs to, plus the few choices a
                    step declares (never free text, never a key). A skipped
                    step also carries what skipping costs, copied from
                    steps.json at that moment. The team plugin's session
                    briefing reads this record and nothing in this plugin, so
                    whatever it needs to say has to be written here.
  setup-guide.html  part 1 of the guide (about 20 minutes), one
                    self-contained page rendered from steps.json and the record
  setup-extras.html part 2, the optional extras, in the same style

Every subcommand first creates setup.json when it is absent (all steps
pending). An existing record is never replaced; a step added to steps.json
later reads as pending, and a record written before steps carried their part
gains it the next time `set` writes. `set` refuses an unknown step, a choice key the step
does not declare, an `os`, `judge` or `judge_why` outside its fixed set, and a value that
is longer than 40 characters, is not a plain word, or looks like a key, path
or email. A refusal never echoes the value and never touches the record.

Each page is one card per step (status, minutes when it has any, OK to skip or
required, why, what skipping costs you, the price, and where to check it
yourself) on graph paper, light or dark to match the reader's system, with no
script, font file or other asset.
Part 1 ends with a thank-you and the absolute path of part 2. `render` prints
GUIDE: and EXTRAS: lines carrying both absolute paths.

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
from redact import redact_text  # noqa: E402  (key-, path- and email-shaped patterns)

STATUSES = ("done", "skipped", "pending")
MAX_VALUE = 40
PLAIN_VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+-]*$")
MARKS = {"done": ("done", "✓ Done"), "skipped": ("skipped", "Skipped"), "pending": ("todo", "To do")}
# Choice keys whose values are a fixed set. judge and judge_why are what
# installer/nc_setup.py reports for Hyperspace Engine's verifier judge.
ALLOWED = {
    "os": ("mac", "windows", "linux"),
    "judge": ("claude-code", "codex", "openrouter", "anthropic", "none"),
    "judge_why": ("answered", "kept", "chosen", "not-signed-in", "no-answer", "no-cli"),
}


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
    older record are filled in as pending, and every step is given its part,
    in memory only: nothing is written until `set` writes."""
    path = record_path(project)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = now()
        write_json(path, {
            "schema_version": 1,
            "plugin_version": plugin_version(),
            "created": stamp,
            "updated": stamp,
            "steps": {s["id"]: {"status": "pending", "at": None, "part": s["part"]} for s in steps},
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
        rec["steps"][s["id"]]["part"] = s["part"]
    return rec


def check_value(key, value):
    if len(value) > MAX_VALUE:
        raise Refused(f"choice {key!r}: value is over {MAX_VALUE} characters; not recorded")
    if not PLAIN_VALUE_RE.match(value) or redact_text(value)[1]:
        raise Refused(f"choice {key!r}: value is not a plain word or looks like a key, path or email; not recorded")
    if key in ALLOWED and value not in ALLOWED[key]:
        raise Refused(f"choice {key!r}: use one of {', '.join(ALLOWED[key])}; not recorded")


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
    # The title goes in whatever the status: the team plugin's session briefing
    # calls a skipped step by it, and reads this record and nothing else.
    entry = {"status": status, "at": None if status == "pending" else stamp, "part": step["part"], "title": step["title"]}
    if status == "skipped":
        entry["if_skipped"] = step["if_skipped"]
    rec["steps"][step_id] = entry
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
        lines.append(f"{s['id']:<{width}}  {rec['steps'][s['id']]['status']:<8}  {'-' if s['minutes'] is None else s['minutes']}")
    done = sum(rec["steps"][s["id"]]["status"] == "done" for s in steps)
    lines.append(f"DONE {done}/{len(steps)}")
    return lines


# Nova Caelum graph paper: light cream paper by default, midnight indigo when
# the reader's system is dark. Brand typefaces by name only, with system
# fallbacks; nothing is fetched.
STYLE = """
:root {
  color-scheme: light dark;
  --serif: "Yrsa", "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --sans: "Instrument Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, Roboto, "Helvetica Neue", Arial, sans-serif;
  --paper: #f6f1e9;
  --grid: rgba(63, 61, 108, 0.09);
  --card: #fffdf9;
  --card-line: rgba(63, 61, 108, 0.16);
  --shadow: 0 1px 2px rgba(29, 19, 41, 0.05), 0 6px 18px rgba(29, 19, 41, 0.06);
  --title: #2a1f3d;
  --body: #3b3447;
  --label: #6b6560;
  --rule: rgba(63, 61, 108, 0.13);
  --hero-line: rgba(42, 31, 61, 0.6);
  --pill-bg: rgba(63, 61, 108, 0.09);
  --pill-fg: #3f3d6c;
  --opt-fg: #5c5752;
  --opt-line: rgba(107, 101, 96, 0.38);
  --done-bg: #e2ece8; --done-fg: #2f5247; --done-line: rgba(91, 125, 115, 0.40);
  --todo-bg: #f7e8cf; --todo-fg: #7a4a12; --todo-line: rgba(196, 138, 60, 0.45);
  --skip-bg: #eeebe6; --skip-fg: #5c5752; --skip-line: rgba(107, 101, 96, 0.32);
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #1d1329;
    --grid: rgba(110, 120, 176, 0.09);
    --card: #241b35;
    --card-line: rgba(110, 120, 176, 0.24);
    --shadow: 0 2px 12px rgba(0, 0, 0, 0.30);
    --title: #f5ebdd;
    --body: rgba(245, 235, 221, 0.84);
    --label: rgba(245, 235, 221, 0.64);
    --rule: rgba(110, 120, 176, 0.20);
    --hero-line: rgba(110, 120, 176, 0.30);
    --pill-bg: rgba(245, 235, 221, 0.09);
    --pill-fg: rgba(245, 235, 221, 0.86);
    --opt-fg: rgba(245, 235, 221, 0.74);
    --opt-line: rgba(245, 235, 221, 0.26);
    --done-bg: rgba(91, 125, 115, 0.26); --done-fg: #b1d4c7; --done-line: rgba(127, 168, 155, 0.45);
    --todo-bg: rgba(232, 184, 122, 0.14); --todo-fg: #f0c994; --todo-line: rgba(232, 184, 122, 0.38);
    --skip-bg: rgba(176, 169, 159, 0.10); --skip-fg: #c2bbb2; --skip-line: rgba(176, 169, 159, 0.30);
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: var(--title);
  font: 16px/1.55 var(--sans);
  background-color: var(--paper);
  background-image: linear-gradient(var(--grid) 1px, transparent 1px), linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 28px 28px;
  background-position: -1px -1px;
  -webkit-text-size-adjust: 100%;
}
main { max-width: 46rem; margin: 0 auto; padding: 2.5rem 1.25rem 3rem; }
.hero {
  color: #f5ebdd;
  background-color: #2a1f3d;
  background-image: radial-gradient(120% 90% at 100% 0%, rgba(232, 184, 122, 0.18), transparent 55%);
  border: 1px solid var(--hero-line);
  border-radius: 18px;
  padding: 2rem 1.75rem 1.5rem;
  box-shadow: var(--shadow);
}
h1 { margin: 0; font: 600 2.4rem/1.1 var(--serif); letter-spacing: -0.01em; }
.lede { margin: 0.6rem 0 0; max-width: 34rem; color: rgba(245, 235, 221, 0.80); text-wrap: pretty; }
.stats { display: grid; grid-template-columns: 1fr 1fr 1.4fr; gap: 0.75rem; margin: 1.5rem 0 1.1rem; }
.stat { margin: 0; padding: 0.75rem 0.9rem; border: 1px solid rgba(245, 235, 221, 0.14); border-radius: 12px; background: rgba(245, 235, 221, 0.05); }
.stat span { display: block; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: rgba(245, 235, 221, 0.70); }
.stat b { display: block; margin-top: 0.2rem; font: 600 1.35rem/1.2 var(--serif); font-variant-numeric: tabular-nums; }
.bar { display: flex; gap: 4px; }
.seg { flex: 1; height: 6px; border-radius: 3px; background: rgba(245, 235, 221, 0.16); }
.seg.done { background: #7fa89b; }
.seg.skipped { background: rgba(176, 169, 159, 0.55); }
.steps { list-style: none; margin: 1.5rem 0 0; padding: 0; display: grid; gap: 0.875rem; }
.card { background: var(--card); border: 1px solid var(--card-line); border-radius: 14px; padding: 1.15rem 1.35rem 1.2rem; box-shadow: var(--shadow); }
.card-top { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.5rem; }
.tags { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.chip, .pill, .badge {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.36rem 0.65rem; border: 1px solid transparent; border-radius: 999px;
  font-size: 0.78rem; font-weight: 600; line-height: 1; white-space: nowrap;
}
.chip.done { background: var(--done-bg); color: var(--done-fg); border-color: var(--done-line); }
.chip.todo { background: var(--todo-bg); color: var(--todo-fg); border-color: var(--todo-line); }
.chip.skipped { background: var(--skip-bg); color: var(--skip-fg); border-color: var(--skip-line); }
.chip.todo::before { content: ""; width: 0.55rem; height: 0.55rem; border: 1.5px solid currentColor; border-radius: 50%; }
.chip.skipped::before { content: ""; width: 0.55rem; height: 1.5px; background: currentColor; }
.pill { background: var(--pill-bg); color: var(--pill-fg); font-variant-numeric: tabular-nums; }
.badge.req { background: #3f3d6c; color: #f5ebdd; }
.badge.opt { color: var(--opt-fg); border-color: var(--opt-line); }
.card h2 { margin: 0.85rem 0 0.3rem; font: 600 1.4rem/1.2 var(--serif); color: var(--title); }
.does { margin: 0; color: var(--body); text-wrap: pretty; }
.facts { display: grid; gap: 0.45rem; margin: 0.95rem 0 0; padding-top: 0.85rem; border-top: 1px solid var(--rule); }
.facts div { display: grid; grid-template-columns: 6.5rem 1fr; gap: 0.75rem; }
.facts dt { padding-top: 0.16rem; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--label); }
.facts dd { margin: 0; font-size: 0.95rem; color: var(--body); text-wrap: pretty; }
footer { margin-top: 1.75rem; padding: 0 0.25rem; color: var(--body); }
footer p { margin: 0.25rem 0; }
a { color: var(--pill-fg); }
.card { min-width: 0; overflow-wrap: anywhere; }
.closing { margin-top: 0.875rem; }
.closing .does:last-child { margin-top: 0.9rem; }
.muted { font-size: 0.875rem; color: var(--label); }
@media (max-width: 34rem) {
  main { padding: 1rem 0.875rem 2rem; }
  .hero { padding: 1.5rem 1.25rem 1.25rem; border-radius: 16px; }
  h1 { font-size: 2rem; }
  .stats { grid-template-columns: 1fr; gap: 0.5rem; margin-top: 1.25rem; }
  .stat { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; padding: 0.6rem 0.8rem; }
  .stat b { margin-top: 0; font-size: 1.2rem; white-space: nowrap; }
  .card { padding: 1rem 1.1rem 1.1rem; }
  .facts div { grid-template-columns: 1fr; gap: 0.1rem; }
}
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<style>{style}</style>
</head>
<body>
<main>
<header class="hero">
<h1>{title}</h1>
<p class="lede">{lede}</p>
<p class="lede">{ask}</p>
<div class="stats">
<p class="stat"><span>Done</span><b>{done} of {count}</b></p>
<p class="stat"><span>Left to do</span><b>{left} minutes</b></p>
<p class="stat"><span>Estimated total</span><b>About {total} minutes</b></p>
</div>
<div class="bar" aria-hidden="true">{segs}</div>
</header>
<ol class="steps">
{cards}
</ol>
{closing}
<footer>
<p>Say <b>“continue setup”</b> to Claude to pick up any step.</p>
<p class="muted">Updated {updated} · technical-cofounder-setup {version}</p>
</footer>
</main>
</body>
</html>
"""

CARD = """<li class="card is-{cls}" data-step="{id}">
<div class="card-top"><span class="chip {cls}">{mark}</span><span class="tags">{pill}{badge}</span></div>
<h2>{title}</h2>
<p class="does">{does}</p>{extra}
<dl class="facts">
<div><dt>Why</dt><dd>{why}</dd></div>
<div><dt>If you skip</dt><dd>{if_skipped}</dd></div>
<div><dt>Cost</dt><dd>{cost}</dd></div>
<div><dt>Check it yourself</dt><dd>{verify}</dd></div>
</dl>
</li>"""

ASK = "Questions at any point? Just ask. Type it in the chat and your agent will answer."
LEDES = {
    1: "Every step of setting up this project: what it does, why it matters, what it costs, and whether it can wait.",
    2: "The optional extras, kept off the first page so your first setup stays short. Do them any time.",
}
TITLES = {1: "Your setup guide", 2: "Setup, part 2: extras"}
THANKS = """<section class="card closing">
<h2>Thanks for setting up.</h2>
<p class="does">Your project is ready to work in.</p>
<dl class="facts">
<div><dt>Next steps</dt><dd>Setup part 2 (extras) is here:<br><a href="{uri}">{path}</a></dd></div>
</dl>
<p class="does">{ask}</p>
</section>"""
SAVED = """<section class="card closing">
<p class="does">This page is saved at <a href="{uri}">{path}</a>.</p>
<p class="does">{ask}</p>
</section>"""

BADGES = {True: '<span class="badge opt">OK to skip</span>', False: '<span class="badge req">Required</span>'}


def obsidian_link(project):
    """The OBSIDIAN.md on this machine: the project's own copy when
    init_workspace put one there, otherwise the plugin's template."""
    mine = project / "OBSIDIAN.md"
    return mine if mine.is_file() else PLUGIN_ROOT / "template" / "OBSIDIAN.md"


def render_part(part, steps, rec, project, extras_path):
    e = html.escape
    cards, segs, left, done = [], [], 0, 0
    for s in steps:
        status = rec["steps"][s["id"]]["status"]
        cls, mark = MARKS.get(status, MARKS["pending"])
        minutes = s["minutes"]
        left += (minutes or 0) if status == "pending" else 0
        done += status == "done"
        segs.append(f'<span class="seg {cls}"></span>')
        extra = ""
        if s["id"] == "obsidian":
            link = obsidian_link(project)
            extra = f'\n<p class="does"><a href="{e(link.as_uri())}">Everything about Obsidian is here, or you can just ask.</a><br><span class="muted">{e(str(link))}</span></p>'
        cards.append(CARD.format(
            cls=cls, mark=mark, id=e(s["id"]), title=e(s["title"]), does=e(s["does"]),
            pill="" if minutes is None else f'<span class="pill">{minutes} min</span>',
            badge=BADGES[bool(s["skippable"])], why=e(s["why"]), extra=extra,
            if_skipped=e(s["if_skipped"]), cost=e(str(s.get("cost", ""))), verify=e(s["verify"]),
        ))
    total = (sum(s["minutes"] or 0 for s in steps) + 2) // 5 * 5  # nearest 5
    ends = {1: THANKS, 2: SAVED}[part].format(uri=e(extras_path.as_uri()), path=e(str(extras_path)), ask=e(ASK))
    return PAGE.format(
        style=STYLE, title=e(TITLES[part]), lede=e(LEDES[part]), ask=e(ASK), closing=ends,
        total=total, left=left, done=done, count=len(steps),
        segs="".join(segs), cards="\n".join(cards),
        updated=e(str(rec.get("updated", "")).replace("T", " ").replace("Z", " UTC")),
        version=e(str(rec.get("plugin_version", ""))),
    )


def render(project):
    """Write both pages; return the part 1 path (the extras page sits beside it)."""
    steps = load_steps()
    rec = load_record(project, steps)
    out = record_path(project).with_name("setup-guide.html")
    extras = out.with_name("setup-extras.html")
    root = Path(project).expanduser().resolve()
    for path, part in ((out, 1), (extras, 2)):
        path.write_text(render_part(part, [s for s in steps if s["part"] == part], rec, root, extras), encoding="utf-8")
    return out


def main(argv):
    parser = argparse.ArgumentParser(prog="setup_record.py", description="Keep a project's setup record and render its guide.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_set = sub.add_parser("set", help="record a step's status (and its declared choices), then render")
    p_set.add_argument("project")
    p_set.add_argument("step")
    p_set.add_argument("status")
    p_set.add_argument("--choice", action="append", default=[], metavar="key=value")
    for name, text in (("status", "print each step's status and a DONE n/m line"), ("render", "write core_text/setup-guide.html and setup-extras.html")):
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
            guide = render(args.project)
            print(f"GUIDE: {guide}")
            print(f"EXTRAS: {guide.with_name('setup-extras.html')}")
    except Refused as exc:
        sys.stderr.write(f"REFUSED: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows pipes default to the ANSI code page
    sys.exit(main(sys.argv))
