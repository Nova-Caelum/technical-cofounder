#!/usr/bin/env python3
"""drive_map_write.py -- PreToolUse hook for the Write tool.

When Write is about to create a file that does not exist yet, inside a project
that has a drive map, add ONE line of context pointing at the map. It never
blocks: it returns no permission decision at all, so the normal permission flow
runs untouched. It says nothing for a file that already exists (an overwrite is
an edit), for a path outside the project, for a project with no map, or for the
engine's own folders (hyperspace/, where the run-folder schema and each run's
own map decide) and hidden folders (.claude/, .hyperspace/).

The line is fixed text. It never echoes the path or what is being written. Any
failure is silence and exit 0: a guardrail that can break a write is worse than
none.

Registered in hooks.json for the `Write` matcher. Standard library only.
"""
import json
import os
import sys
from pathlib import Path

MAP = Path("core_text") / "drive-map.md"
LINE = "New file: check core_text/drive-map.md for where it belongs."
OWN_FOLDERS = ("hyperspace",)


def under_a_map(target, project):
    """True when `target` is a new file inside `project`, which has a map, outside folders the map is not for."""
    if not (project / MAP).is_file():
        return False
    try:
        rel = target.resolve().relative_to(project.resolve())
    except (OSError, ValueError):
        return False
    first = rel.parts[0] if rel.parts else ""
    return not (first.startswith(".") or first in OWN_FOLDERS)


def main():
    try:
        event = json.load(sys.stdin)
        if event.get("tool_name", "Write") != "Write":
            return 0
        target = Path(event["tool_input"]["file_path"])
        if target.exists():
            return 0
        candidates = [os.environ.get("CLAUDE_PROJECT_DIR"), event.get("cwd")]
        if any(c and under_a_map(target, Path(c)) for c in candidates):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": LINE}}))
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
