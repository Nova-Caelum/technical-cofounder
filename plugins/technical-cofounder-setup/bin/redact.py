#!/usr/bin/env python3
"""Redaction patterns shared by the plugin's helpers.

`redact_text(text, kinds=None)` replaces home-directory paths, email
addresses and several key-shaped strings with `[redacted]` and returns
`(text, counts)`. `kinds` limits it to a subset: `contact.py` uses
`SECRET_KINDS`, so a message to the founder keeps its emails and paths but
never carries a key. `format_counts(counts)` renders the counts as
`REDACTED: <n> <kind>` lines — never the matched text.

Standard library only.
"""
import re

PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
ASSIGNMENT_RE = re.compile(
    r"\b(\w*(?:KEY|TOKEN|SECRET|PASSWORD)\w*)(\s*[:=]\s*)(\"[^\"\n]*\"|'[^'\n]*'|\S+)",
    re.IGNORECASE,
)
KEYSHAPED_RE = re.compile(
    r"\bsk-[A-Za-z0-9_-]{10,}\b"
    r"|\bgh[po]_[A-Za-z0-9]{20,}\b"
    r"|\bgithub_pat_[A-Za-z0-9_]{20,}\b"
    r"|\bAKIA[0-9A-Z]{16}\b"
    r"|\bxox[bap]-[A-Za-z0-9-]{10,}\b"
)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
HOME_UNIX_RE = re.compile(r"(?:/(?:Users|home)/)[\w.\-]+(?:/[\w.\-]+)*")
HOME_WIN_RE = re.compile(r"[A-Za-z]:\\Users\\[\w.\-]+(?:\\[\w.\-]+)*", re.IGNORECASE)
TOKEN_RE = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")

# Printed in this order; only kinds with count > 0 are shown.
REDACT_ORDER = ("path", "email", "private_key", "assignment", "keyshaped", "token")

SECRET_KINDS = frozenset({"private_key", "assignment", "keyshaped", "token"})

# Applied in this order, so a later, broader pattern (the generic
# high-entropy token scan) never re-matches text a more specific one replaced.
_RULES = (
    (PRIVATE_KEY_RE, "[redacted]", "private_key"),
    (ASSIGNMENT_RE, r"\1\2[redacted]", "assignment"),
    (KEYSHAPED_RE, "[redacted]", "keyshaped"),
    (EMAIL_RE, "[redacted]", "email"),
    (HOME_WIN_RE, "[redacted]", "path"),
    (HOME_UNIX_RE, "[redacted]", "path"),
    (TOKEN_RE, "[redacted]", "token"),
)


def redact_text(text, kinds=None):
    """Returns (redacted_text, counts)."""
    counts = {}
    for pattern, repl, kind in _RULES:
        if kinds is not None and kind not in kinds:
            continue
        text, n = pattern.subn(repl, text)
        if n:
            counts[kind] = counts.get(kind, 0) + n
    return text, counts


def format_counts(counts):
    """`REDACTED: <n> <kind>` lines in a fixed order, or `REDACTED: 0 total`."""
    lines = [f"REDACTED: {counts[k]} {k}" for k in REDACT_ORDER if counts.get(k)]
    return "\n".join(lines) if lines else "REDACTED: 0 total"
