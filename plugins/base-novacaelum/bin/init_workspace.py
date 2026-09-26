#!/usr/bin/env python3
"""Copy this plugin's starter workspace into a target project.

Usage:
    python3 init_workspace.py <target-dir> [--obsidian|--no-obsidian] [--super|--no-super]

Copies every file under ../template/ (relative to this script) into
<target-dir>, preserving the relative path. Never overwrites a file that
already exists at the destination. Prints one "COPIED: <relpath>" or
"SKIPPED: <relpath>" line per file, in sorted order, then a
machine-readable summary line, then exits 0.

--obsidian/--no-obsidian controls whether `.obsidian/` and
`worklog/worklog.base` are part of the copy (every other `worklog/` file
copies either way). --super, when set, additionally prints the
super-novacaelum install command (project scope) and a pointer to the
super-setup skill; it never copies anything itself.

The setup skill always passes both flags explicitly — this script's own
"ask" path exists only for a bare, human-run CLI invocation. A flag left
unset is asked for with a plain terminal prompt when stdin is a tty; when
it isn't (a script, CI, a non-interactive dry run), it defaults to "no"
and a DEFAULTED line names which flags were defaulted, so a bare
invocation never blocks waiting on input that will never arrive.

Standard library only.
"""
import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE_DIR = HERE.parent / "template"

SUPER_INSTALL_CMD = "claude plugin install super-novacaelum@technical-cofounder --scope project"
SUPER_KEY_GUIDE_POINTER = (
    "Next, the super-setup skill walks you through accounts and keys for "
    "each service, starting from zero if you have never used an API key."
)


def _is_obsidian_only(rel):
    return rel.parts[0] == ".obsidian" or rel == Path("worklog") / "worklog.base"


def _stdin_is_tty():
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def _ask_yes_no(prompt, default):
    """Returns (answer, was_defaulted). Never blocks when stdin isn't a tty."""
    if not _stdin_is_tty():
        return default, True
    suffix = "[Y/n] " if default else "[y/N] "
    try:
        raw = input(f"{prompt} {suffix}").strip().lower()
    except EOFError:
        return default, True
    if not raw:
        return default, True
    return raw.startswith("y"), False


def init_workspace(target_dir, obsidian, super_):
    target = Path(target_dir).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    lines = []
    copied = 0
    skipped = 0
    for src in sorted(TEMPLATE_DIR.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(TEMPLATE_DIR)
        if not obsidian and _is_obsidian_only(rel):
            continue
        dest = target / rel
        if dest.exists():
            lines.append(f"SKIPPED: {rel}")
            skipped += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        lines.append(f"COPIED: {rel}")
        copied += 1

    if super_:
        lines.append("")
        lines.append(f"Enable the opt-in services plugin with your own keys: {SUPER_INSTALL_CMD}")
        lines.append(SUPER_KEY_GUIDE_POINTER)

    lines.append("")
    lines.append(
        f"INIT_SUMMARY obsidian={str(obsidian).lower()} super={str(super_).lower()} "
        f"copied={copied} skipped={skipped}"
    )
    return lines


def main(argv):
    parser = argparse.ArgumentParser(
        prog="init_workspace.py",
        description="Copy this plugin's starter workspace into a target project.",
    )
    parser.add_argument("target_dir", metavar="<target-dir>")
    parser.add_argument(
        "--obsidian", dest="obsidian", action="store_true", default=None,
        help="include the Obsidian starter view (.obsidian/, worklog/worklog.base)",
    )
    parser.add_argument(
        "--no-obsidian", dest="obsidian", action="store_false",
        help="skip the Obsidian starter view",
    )
    parser.add_argument(
        "--super", dest="super_", action="store_true", default=None,
        help="print the super-novacaelum install command and key-guide pointer",
    )
    parser.add_argument(
        "--no-super", dest="super_", action="store_false",
        help="skip the super-novacaelum pointer",
    )
    args = parser.parse_args(argv[1:])

    if not TEMPLATE_DIR.is_dir():
        sys.stderr.write(f"init_workspace: template directory not found at {TEMPLATE_DIR}\n")
        return 2

    defaulted = []
    obsidian = args.obsidian
    if obsidian is None:
        obsidian, was_defaulted = _ask_yes_no("Add the Obsidian starter view?", default=False)
        if was_defaulted:
            defaulted.append("obsidian")

    super_ = args.super_
    if super_ is None:
        super_, was_defaulted = _ask_yes_no("Install the opt-in super-novacaelum services plugin too?", default=False)
        if was_defaulted:
            defaulted.append("super")

    for line in init_workspace(args.target_dir, obsidian, super_):
        print(line)
    if defaulted:
        print(f"DEFAULTED (non-interactive, no flag given): {', '.join(defaulted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
