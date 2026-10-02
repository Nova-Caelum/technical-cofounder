#!/bin/bash
# circuit-breaker.sh — PreToolUse / PostToolUse / PostToolUseFailure hook.
#
# Source: adapted from Nova Caelum's internal agentOS circuit-breaker hook
# (2026). License: MIT.
#
# Blocks a tool from running again once it has FAILED with the same error
# class 5 times in a row this session, with no intervening success.
# Dispatches on hook_event_name (read from stdin JSON):
#
#   PostToolUseFailure — the only place a counter is ever incremented. Key:
#                         tool_name + a normalized error class (lowercase;
#                         digits, UUIDs, quoted literals, paths and long
#                         tokens stripped, so two failures that differ only
#                         in a timestamp or a file path still count as the
#                         same class). At every multiple of 3, warns via
#                         additionalContext. At 5, the counter this tool's
#                         next PreToolUse checks is now past threshold.
#   PostToolUse         — fires only on success; resets every failure
#                         counter for that tool. A success is evidence the
#                         loop broke, so an intermittent pattern (fail,
#                         fail, succeed, fail, ...) never trips this.
#   PreToolUse          — READ-ONLY check: is this tool's failure count for
#                         any class already >= 5? If so, block (exit 2).
#                         Never increments anything itself.
#
# Observed failure: an earlier version of this hook counted PreToolUse
# ATTEMPTS instead of failures, and fired a false block after 3 tool calls
# that all ran in parallel and all succeeded — parallel dispatch sends
# every PreToolUse before any PostToolUse lands, so an attempt-count
# counter can cross its own threshold on ordinary concurrent success. This
# version counts only PostToolUseFailure events, so N parallel calls that
# all succeed never move the counter at all (tests/test_template_hooks.py
# exercises exactly this: N parallel Pre events + N successes never trips;
# 5 identical failures do).
#
# Never blocks on a session it cannot confidently identify — an
# absent/unsafe session_id collapses into a shared "nosession" bucket that
# must never gain blocking authority, only warn authority.

set -euo pipefail

# shellcheck disable=SC2034  # read by lib/loud-fail.sh after sourcing
HOOK_NAME="circuit-breaker"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/loud-fail.sh disable=SC1091
if ! source "$SCRIPT_DIR/lib/loud-fail.sh"; then
    printf '⚠️ circuit-breaker: cannot source lib/loud-fail.sh\n' >&2
    exit 0
fi
# shellcheck source=lib/resolve-tools.sh disable=SC1091
if ! source "$SCRIPT_DIR/lib/resolve-tools.sh"; then
    log_visible "cannot source lib/resolve-tools.sh — jq will not be found"
    export NC_JQ=""
fi
# shellcheck source=lib/rule-disclosure.sh disable=SC1091
if ! source "$SCRIPT_DIR/lib/rule-disclosure.sh"; then
    log_visible "cannot source lib/rule-disclosure.sh — warnings become a silent no-op"
    rule_disclosure_emit() { :; }
fi

STATE_ROOT="${TMPDIR:-/tmp}/technical-cofounder/circuit-breaker"
WARN_EVERY=3
BLOCK_THRESHOLD=5

class_key_hash() {
    local norm="$1" out=""
    if command -v shasum >/dev/null 2>&1; then
        out="$(printf '%s' "$norm" | shasum -a 256 2>/dev/null | awk '{print substr($1,1,16)}')" || out=""
    fi
    if [ -z "$out" ] && command -v md5 >/dev/null 2>&1; then
        out="$(printf '%s' "$norm" | md5 2>/dev/null | awk '{print substr($1,1,16)}')" || out=""
    fi
    if [ -z "$out" ] && command -v md5sum >/dev/null 2>&1; then
        out="$(printf '%s' "$norm" | md5sum 2>/dev/null | awk '{print substr($1,1,16)}')" || out=""
    fi
    if [ -z "$out" ]; then
        out="$(printf '%s' "$norm" | tr -cd 'a-z0-9' 2>/dev/null | cut -c1-40)" || out=""
    fi
    if [ -n "$out" ]; then
        printf '%s' "$out"
    else
        printf '%s' "unknown-class"
    fi
}

normalize_error_class() {
    local raw="$1"
    if [ -z "$raw" ]; then
        printf '%s' "<no-error-text>"
        return 0
    fi
    local norm="$raw"
    norm="$(printf '%s' "$norm" | tr '[:upper:]' '[:lower:]' 2>/dev/null)" || :
    norm="$(printf '%s' "$norm" | sed -E 's/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/<uuid>/g' 2>/dev/null)" || :
    norm="$(printf '%s' "$norm" | sed -E "s/'[^']*'/<lit>/g" 2>/dev/null)" || :
    norm="$(printf '%s' "$norm" | sed -E 's/"[^"]*"/<lit>/g' 2>/dev/null)" || :
    norm="$(printf '%s' "$norm" | sed -E 's#(/[A-Za-z0-9._~-]+){2,}/?#<path>#g' 2>/dev/null)" || :
    norm="$(printf '%s' "$norm" | sed -E 's/0x[0-9a-f]+/<hex>/g' 2>/dev/null)" || :
    norm="$(printf '%s' "$norm" | sed -E 's/[0-9]+/<n>/g' 2>/dev/null)" || :
    norm="$(printf '%s' "$norm" | sed -E 's/[A-Za-z0-9]{20,}/<token>/g' 2>/dev/null)" || :
    norm="$(printf '%s' "$norm" | tr -s '[:space:]' ' ' 2>/dev/null)" || :
    norm="${norm:0:500}"
    printf '%s' "$norm"
}

count_lines() {
    local file="$1" count=0
    if [ -r "$file" ]; then
        while IFS= read -r _; do
            count=$((count + 1))
        done < "$file"
    fi
    printf '%s' "$count"
}

block_and_exit() {
    local tool_name="$1" count="$2"
    printf '⚠️ CIRCUIT BREAKER — BLOCKED: tool "%s" has failed the same way %s times in a row this session with no intervening success. Two options: (1) stop and change approach entirely — a different tool, a different method, or question whether the frame itself is wrong; or (2) escalate to the user/caller now and describe what failed and why. A success on any other tool does not clear this — "%s" itself has to succeed once to reset. If the problem is this plugin itself, /technical-cofounder:contact reaches its makers.\n' \
        "$tool_name" "$count" "$tool_name" >&2
    exit 2
}

handle_pretooluse() {
    local session_id="$1" tool_name="$2"
    local session_confident=1 session_key tool_key

    if [ -z "$session_id" ]; then
        session_key="nosession"
        session_confident=0
    else
        session_key="$(sanitize_key "$session_id" "nosession")"
        [ "$session_key" = "nosession" ] && session_confident=0
    fi
    tool_key="$(sanitize_key "$tool_name" "unknown-tool")"

    local session_dir="$STATE_ROOT/$session_key"
    [ -d "$session_dir" ] || return 0

    local f count
    for f in "$session_dir/failclass-${tool_key}-"*.count; do
        [ -e "$f" ] || continue
        count="$(count_lines "$f")"
        if [ "$session_confident" -eq 1 ] && [ "$count" -ge "$BLOCK_THRESHOLD" ]; then
            block_and_exit "$tool_name" "$count"   # never returns
        fi
    done
    return 0
}

handle_posttooluse() {
    local session_id="$1" tool_name="$2"
    local session_key tool_key
    session_key="$(sanitize_key "${session_id:-}" "nosession")"
    tool_key="$(sanitize_key "$tool_name" "unknown-tool")"
    rm -f "$STATE_ROOT/$session_key/failclass-${tool_key}-"*.count 2>/dev/null || true
    return 0
}

handle_posttoolusefailure() {
    local session_id="$1" tool_name="$2" error_text="$3"
    local session_key tool_key
    session_key="$(sanitize_key "${session_id:-}" "nosession")"
    tool_key="$(sanitize_key "$tool_name" "unknown-tool")"

    local session_dir="$STATE_ROOT/$session_key"
    if ! mkdir -p "$session_dir" 2>/dev/null; then
        log_visible "cannot create $session_dir — skipping this failure (fail-open)"
        return 0
    fi

    local class_norm class_hash counter_file count
    class_norm="$(normalize_error_class "$error_text")"
    class_hash="$(class_key_hash "$class_norm")"
    counter_file="$session_dir/failclass-${tool_key}-${class_hash}.count"

    if ! printf '%s\n' "$$" >> "$counter_file" 2>/dev/null; then
        log_visible "cannot append $counter_file — skipping count this call (fail-open)"
        return 0
    fi
    count="$(count_lines "$counter_file")"

    if [ "$count" -ge "$WARN_EVERY" ] && [ "$((count % WARN_EVERY))" -eq 0 ]; then
        local msg="Circuit breaker: ${count} consecutive failures of the same kind on tool \"${tool_name}\" this session, with no success in between. At 5 this tool gets blocked until it succeeds once. The same approach failing repeatedly usually means the frame is wrong, not that one more variation will work."
        rule_disclosure_emit "PostToolUseFailure" "$msg"   # exits 0 on success; falls through if unavailable
    fi
    return 0
}

# --- main ---

INPUT="$(cat 2>/dev/null || true)"
if [ -z "$INPUT" ]; then
    log_visible "empty stdin — nothing to process"
    exit 0
fi

if [ -z "$NC_JQ" ]; then
    log_visible "jq not found on PATH or in the tools folder — skipping this invocation (fail-open)"
    exit 0
fi

if ! printf '%s' "$INPUT" | "$NC_JQ" -e . >/dev/null 2>&1; then
    log_visible "malformed JSON on stdin — skipping this invocation (fail-open)"
    exit 0
fi

HOOK_EVENT=$(printf '%s' "$INPUT" | "$NC_JQ" -r '.hook_event_name // empty' 2>/dev/null) || HOOK_EVENT=""
TOOL_NAME=$(printf '%s' "$INPUT" | "$NC_JQ" -r '.tool_name // empty' 2>/dev/null) || TOOL_NAME=""
SESSION_ID=$(printf '%s' "$INPUT" | "$NC_JQ" -r '.session_id // empty' 2>/dev/null) || SESSION_ID=""

if [ -z "$TOOL_NAME" ]; then
    log_visible "tool_name absent on $HOOK_EVENT — nothing to key on"
    exit 0
fi

case "$HOOK_EVENT" in
    PreToolUse)
        handle_pretooluse "$SESSION_ID" "$TOOL_NAME"
        ;;
    PostToolUse)
        handle_posttooluse "$SESSION_ID" "$TOOL_NAME"
        ;;
    PostToolUseFailure)
        ERROR_TEXT=$(printf '%s' "$INPUT" | "$NC_JQ" -r '.error // empty' 2>/dev/null) || ERROR_TEXT=""
        handle_posttoolusefailure "$SESSION_ID" "$TOOL_NAME" "$ERROR_TEXT"
        ;;
    *)
        log_visible "unrecognized hook_event_name '$HOOK_EVENT' — no-op (fail-open)"
        ;;
esac

exit 0
