"""circuit_breaker.py — PreToolUse / PostToolUse / PostToolUseFailure hook
(run by circuit-breaker.sh).

Source: adapted from Nova Caelum's internal agentOS circuit-breaker hook
(2026). License: MIT.

Blocks a tool from running again once it has FAILED with the same error class
5 times in a row this session, with no intervening success. Dispatches on
hook_event_name (read from stdin JSON):

  PostToolUseFailure — the only place a counter is ever incremented. Key:
                       tool_name + a normalized error class (lowercase;
                       digits, UUIDs, quoted literals, paths and long tokens
                       stripped, so two failures that differ only in a
                       timestamp or a file path still count as the same
                       class). At every multiple of 3, warns via
                       additionalContext. At 5, the counter this tool's next
                       PreToolUse checks is now past threshold.
  PostToolUse        — fires only on success; resets every failure counter
                       for that tool. A success is evidence the loop broke,
                       so an intermittent pattern (fail, fail, succeed, fail,
                       ...) never trips this.
  PreToolUse         — READ-ONLY check: is this tool's failure count for any
                       class already >= 5? If so, block (exit 2). Never
                       increments anything itself.

Observed failure: an earlier version of this hook counted PreToolUse ATTEMPTS
instead of failures, and fired a false block after 3 tool calls that all ran
in parallel and all succeeded — parallel dispatch sends every PreToolUse
before any PostToolUse lands, so an attempt-count counter can cross its own
threshold on ordinary concurrent success. This version counts only
PostToolUseFailure events, so N parallel calls that all succeed never move the
counter at all (tests/test_template_hooks.py exercises exactly this: N
parallel Pre events + N successes never trips; 5 identical failures do).

Never blocks on a session it cannot confidently identify — an absent/unsafe
session_id collapses into a shared "nosession" bucket that must never gain
blocking authority, only warn authority.
"""
import hashlib
import os
import re
import sys

from _shared import emit_context, field, log_visible, parse_json, read_stdin, sanitize_key, state_root, utf8_stdio

HOOK = "circuit-breaker"
WARN_EVERY = 3
BLOCK_THRESHOLD = 5

# Applied in order, each within one line, as the bash version's sed passes were.
_CLASS_RULES = (
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"), "<uuid>"),
    (re.compile(r"'[^'\n]*'"), "<lit>"),
    (re.compile(r'"[^"\n]*"'), "<lit>"),
    (re.compile(r"(/[A-Za-z0-9._~-]+){2,}/?"), "<path>"),
    (re.compile(r"0x[0-9a-f]+"), "<hex>"),
    (re.compile(r"[0-9]+"), "<n>"),
    (re.compile(r"[A-Za-z0-9]{20,}"), "<token>"),
    (re.compile(r"[ \t\n\v\f\r]+"), " "),
)


def normalize_error_class(text):
    if not text:
        return "<no-error-text>"
    norm = text.lower().rstrip("\n")
    for pattern, replacement in _CLASS_RULES:
        norm = pattern.sub(replacement, norm)
    return norm[:500]


def class_key_hash(norm):
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def count_lines(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace").count("\n")
    except OSError:
        return 0


def counter_files(session_dir, tool_key):
    return sorted(session_dir.glob(f"failclass-{tool_key}-*.count"))


def handle_pretooluse(session_id, tool_name):
    session_key = sanitize_key(session_id, "nosession")
    confident = bool(session_id) and session_key != "nosession"
    session_dir = state_root() / "circuit-breaker" / session_key
    if not session_dir.is_dir():
        return 0
    for path in counter_files(session_dir, sanitize_key(tool_name, "unknown-tool")):
        count = count_lines(path)
        if confident and count >= BLOCK_THRESHOLD:
            print(
                f'⚠️ CIRCUIT BREAKER — BLOCKED: tool "{tool_name}" has failed the same way {count} times in a row '
                "this session with no intervening success. Two options: (1) stop and change approach entirely — a "
                "different tool, a different method, or question whether the frame itself is wrong; or (2) "
                "escalate to the user/caller now and describe what failed and why. A success on any other tool "
                f'does not clear this — "{tool_name}" itself has to succeed once to reset. If the problem is this '
                "plugin itself, /base-novacaelum:ask reaches its makers.",
                file=sys.stderr,
            )
            return 2
    return 0


def handle_posttooluse(session_id, tool_name):
    session_dir = state_root() / "circuit-breaker" / sanitize_key(session_id, "nosession")
    for path in counter_files(session_dir, sanitize_key(tool_name, "unknown-tool")):
        try:
            path.unlink()
        except OSError:
            pass
    return 0


def handle_posttoolusefailure(session_id, tool_name, error_text):
    session_dir = state_root() / "circuit-breaker" / sanitize_key(session_id, "nosession")
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_visible(HOOK, f"cannot create {session_dir} — skipping this failure (fail-open)")
        return 0
    tool_key = sanitize_key(tool_name, "unknown-tool")
    counter = session_dir / f"failclass-{tool_key}-{class_key_hash(normalize_error_class(error_text))}.count"
    try:
        with open(counter, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(f"{os.getpid()}\n")
    except OSError:
        log_visible(HOOK, f"cannot append {counter} — skipping count this call (fail-open)")
        return 0
    count = count_lines(counter)
    if count >= WARN_EVERY and count % WARN_EVERY == 0:
        emit_context(
            "PostToolUseFailure",
            f'Circuit breaker: {count} consecutive failures of the same kind on tool "{tool_name}" this session, '
            "with no success in between. At 5 this tool gets blocked until it succeeds once. The same approach "
            "failing repeatedly usually means the frame is wrong, not that one more variation will work.",
        )
    return 0


def main():
    utf8_stdio()
    text = read_stdin() or ""
    if not text.rstrip("\n"):
        log_visible(HOOK, "empty stdin — nothing to process")
        return 0
    ok, data = parse_json(text)
    if not ok:
        log_visible(HOOK, "malformed JSON on stdin — skipping this invocation (fail-open)")
        return 0

    event = field(data, "hook_event_name")
    tool_name = field(data, "tool_name")
    session_id = field(data, "session_id")
    if not tool_name:
        log_visible(HOOK, f"tool_name absent on {event} — nothing to key on")
        return 0
    if event == "PreToolUse":
        return handle_pretooluse(session_id, tool_name)
    if event == "PostToolUse":
        return handle_posttooluse(session_id, tool_name)
    if event == "PostToolUseFailure":
        return handle_posttoolusefailure(session_id, tool_name, field(data, "error"))
    log_visible(HOOK, f"unrecognized hook_event_name '{event}' — no-op (fail-open)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
