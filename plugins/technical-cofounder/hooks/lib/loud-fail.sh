#!/bin/bash
# lib/loud-fail.sh — shared failure-visibility + safe-JSON-read helpers for
# technical-cofounder's guardrail hooks.
#
# Source: adapted from Nova Caelum's internal agentOS hook library (2026).
# License: MIT.
#
# Every guardrail hook in this plugin fails OPEN: a broken hook must never
# break the user's Claude Code session. These helpers make failures VISIBLE
# on stderr (never silently swallowed) while still letting the calling hook
# exit 0 and get out of the way.
#
#   log_visible          — write a "hook: msg" line to stderr only; the
#                           caller continues. Used for documented fallback
#                           paths: missing jq, malformed JSON, an absent
#                           optional field.
#   fail_loud_stderr      — same, then exits with the given code (default
#                           1). Reserved for setup errors the hook cannot
#                           recover from at all (e.g. a required lib file
#                           failed to source).
#   require_jq_or_exit    — fail-open exit 0 if `jq` isn't on PATH.
#   require_json_or_exit  — fail-open exit 0 if $1 doesn't parse as JSON.
#   sanitize_key          — turn a session_id/tool_name into a safe
#                           filesystem path component; reject-whole-value
#                           (any disallowed character, an empty value, an
#                           over-length value, or a bare "."/".." falls
#                           back to the caller-supplied default instead of
#                           being partially stripped).
#
# Caller sets HOOK_NAME before sourcing this file.
#
# Hook secret handling: these helpers only ever echo caller-supplied
# strings that are not credential material (hook stdin here is prompt
# text, tool names, and session ids — never secrets). No curl, no `set -x`.

: "${HOOK_NAME:=unknown-hook}"

log_visible() {
    printf '⚠️ %s: %s\n' "$HOOK_NAME" "$1" >&2
}

fail_loud_stderr() {
    local msg="$1" code="${2:-1}"
    printf '⚠️ %s: %s\n' "$HOOK_NAME" "$msg" >&2
    exit "$code"
}

require_jq_or_exit() {
    if ! command -v jq >/dev/null 2>&1; then
        log_visible "jq not found on PATH — skipping this invocation (fail-open)"
        exit 0
    fi
}

require_json_or_exit() {
    if ! printf '%s' "$1" | jq -e . >/dev/null 2>&1; then
        log_visible "malformed JSON on stdin — skipping this invocation (fail-open)"
        exit 0
    fi
}

sanitize_key() {
    local raw="$1" fallback="$2"
    if [ -z "$raw" ] || [ "${#raw}" -gt 200 ]; then
        printf '%s' "$fallback"
        return 0
    fi
    case "$raw" in
        *[!A-Za-z0-9._-]*) printf '%s' "$fallback" ;;
        .|..) printf '%s' "$fallback" ;;
        *) printf '%s' "$raw" ;;
    esac
}
