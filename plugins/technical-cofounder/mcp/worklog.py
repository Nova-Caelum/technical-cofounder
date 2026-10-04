"""worklog.py -- canonical markdown worklog entries.

One file per entry (worklog/entries/<ts>-<slug>.md, YAML-style frontmatter).
Standard library only.

Public API:
    append(root, summary, detail="", author="agent", tags=None) -> dict
    recent(root, n=5) -> list[dict]
    search(root, query) -> list[dict]
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

MAX_SUMMARY_LEN = 280


def _slugify(text, max_len=40):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "entry"


def _render_frontmatter(now, author, summary, tags):
    lines = [
        "---",
        f"date: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"author: {json.dumps(author)}",
        f"summary: {json.dumps(summary)}",
        f"tags: {json.dumps(list(tags))}",
        "---",
    ]
    return "\n".join(lines)


def _parse_frontmatter(text):
    meta = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith('"') or value.startswith("["):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
        meta[key] = value
    return meta


def _parse_entry(path):
    text = path.read_text(encoding="utf-8")
    meta = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            meta = _parse_frontmatter(text[4:end])
            body = text[end + 4:].lstrip("\n")
    meta["body"] = body
    meta["file"] = str(path)
    return meta


def _entries_dir(root):
    return Path(root) / "worklog" / "entries"


def _sorted_entry_paths(entries_dir, reverse=False):
    """Sort by actual write order (mtime), not filename -- two entries
    appended within the same wall-clock second share a timestamp prefix,
    so filename order would tie-break on the slug instead of append order.
    """
    paths = list(entries_dir.glob("*.md"))
    paths.sort(key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=reverse)
    return paths


def append(root, summary, detail="", author="agent", tags=None):
    """Write one entry file; returns {"file": <path>}.

    Rejects a summary over MAX_SUMMARY_LEN characters.
    """
    if len(summary) > MAX_SUMMARY_LEN:
        raise ValueError(f"summary exceeds {MAX_SUMMARY_LEN} characters ({len(summary)})")

    tags = list(tags or [])
    root = Path(root)
    entries_dir = _entries_dir(root)
    entries_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    slug = _slugify(summary)
    entry_path = entries_dir / f"{ts}-{slug}.md"
    collision = 2
    while entry_path.exists():
        # two appends in the same second can share a timestamp and slug;
        # never clobber a prior entry -- disambiguate instead.
        entry_path = entries_dir / f"{ts}-{slug}-{collision}.md"
        collision += 1

    body = detail or ""
    text = _render_frontmatter(now, author, summary, tags) + "\n" + body
    if body and not body.endswith("\n"):
        text += "\n"
    entry_path.write_text(text, encoding="utf-8")
    return {"file": str(entry_path)}


def recent(root, n=5):
    """Return the n most recent entries, newest first."""
    entries_dir = _entries_dir(root)
    if not entries_dir.exists():
        return []
    paths = _sorted_entry_paths(entries_dir, reverse=True)
    return [_parse_entry(p) for p in paths[:n]]


def search(root, query):
    """Return entries whose summary, body, tags or author contain query (case-insensitive)."""
    entries_dir = _entries_dir(root)
    if not entries_dir.exists():
        return []
    needle = query.lower()
    matches = []
    for path in _sorted_entry_paths(entries_dir, reverse=True):
        meta = _parse_entry(path)
        tags = meta.get("tags")
        haystack = " ".join(
            [
                str(meta.get("summary", "")),
                str(meta.get("body", "")),
                " ".join(tags) if isinstance(tags, list) else "",
                str(meta.get("author", "")),
            ]
        ).lower()
        if needle in haystack:
            matches.append(meta)
    return matches
