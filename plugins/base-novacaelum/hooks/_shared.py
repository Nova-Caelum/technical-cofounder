"""_shared.py — what every base-novacaelum guardrail hook shares.

Source: adapted from Nova Caelum's internal agentOS hook library (2026).
License: MIT.

Every hook fails OPEN: a broken hook must never break the user's Claude Code
session. These helpers make failures VISIBLE on stderr while the hook still
exits 0. Standard library only: no jq, no shasum.

The hooks were ported from bash, and the field readers below keep what the
bash versions did with `$(jq -r '.field // empty')`: a missing field, null or
false reads as "", a non-object reads as "", a non-string value reads as its
JSON text, and trailing newlines are dropped.

Hook secret handling: the helpers only ever echo caller-supplied strings that
are not credential material (hook stdin here is prompt text, tool names and
session ids, never secrets).
"""
import json
import re
import sys
import tempfile
from pathlib import Path

_SAFE_KEY = re.compile(r"[A-Za-z0-9._-]+")


def utf8_stdio():
    """Windows pipes default to the ANSI code page; the hooks read and write
    UTF-8 on every OS."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def log_visible(hook, msg):
    """A `⚠️ hook: msg` line on stderr only; the caller continues."""
    print(f"⚠️ {hook}: {msg}", file=sys.stderr)


def read_stdin():
    """All of stdin, or None when it cannot be read."""
    try:
        return sys.stdin.read()
    except (OSError, ValueError):
        return None


def parse_json(text):
    """(ok, value). ok is False for anything `jq -e .` would reject: invalid
    JSON, or a top-level null/false."""
    try:
        value = json.loads(text)
    except ValueError:
        return False, None
    return value is not None and value is not False, value


def raw(value):
    """`jq -r` output inside `$(...)`."""
    text = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False)
    return text.rstrip("\n")


def field(data, key):
    """`$(jq -r '.key // empty')`."""
    if not isinstance(data, dict):
        return ""
    value = data.get(key)
    return "" if value is None or value is False else raw(value)


def sanitize_key(value, fallback):
    """A safe filesystem path component, or the fallback: reject the whole
    value (any disallowed character, empty, over 200 characters, or a bare
    "." / "..") rather than strip it partially."""
    if not value or len(value) > 200 or not _SAFE_KEY.fullmatch(value) or value in (".", ".."):
        return fallback
    return value


def state_root():
    """Per-machine hook state: <temp dir>/base-novacaelum. The temp dir honours
    TMPDIR first, then TEMP and TMP, so it works on Windows too."""
    return Path(tempfile.gettempdir()) / "base-novacaelum"


def emit_context(event, text):
    """Print hookSpecificOutput.additionalContext, the only channel PreToolUse
    and PostToolUseFailure hooks have into the model's context. The text reaches
    the model verbatim: never pass credential material."""
    payload = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
