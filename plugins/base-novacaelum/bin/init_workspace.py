#!/usr/bin/env python3
"""Copy this plugin's starter workspace into a target project.

Usage:
    python3 init_workspace.py <target-dir>

Copies every file under ../template/ (relative to this script) into
<target-dir>, preserving the relative path. Never overwrites a file that
already exists at the destination. Prints one "COPIED: <relpath>" or
"SKIPPED: <relpath>" line per file, in sorted order, then exits 0.

Standard library only.
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE_DIR = HERE.parent / "template"


def init_workspace(target_dir):
    target = Path(target_dir).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    lines = []
    for src in sorted(TEMPLATE_DIR.rglob("*")):
        if src.is_dir():
            continue
        rel = src.relative_to(TEMPLATE_DIR)
        dest = target / rel
        if dest.exists():
            lines.append(f"SKIPPED: {rel}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        lines.append(f"COPIED: {rel}")
    return lines


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: init_workspace.py <target-dir>\n")
        return 2
    if not TEMPLATE_DIR.is_dir():
        sys.stderr.write(f"init_workspace: template directory not found at {TEMPLATE_DIR}\n")
        return 2
    for line in init_workspace(argv[1]):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
