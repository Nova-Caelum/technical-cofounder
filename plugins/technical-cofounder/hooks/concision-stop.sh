#!/bin/bash
# concision-stop.sh — Stop hook.
#
# Source: adapted from Nova Caelum's internal agentOS concision-stop hook
# (2026). License: MIT.
#
# Hard-blocks a response over 700 words (retry cap 1 via stop_hook_active),
# and — when a state file exists from concision-budget.sh — logs whether
# the response breached its assigned budget. Telemetry is local only: it
# goes to ${CLAUDE_PLUGIN_DATA} if set, else a temp dir, or nowhere at all.
# Nothing here ever leaves this machine.
#
# Observed failure: `last_assistant_message` is an undocumented Stop-hook
# stdin field. If a future Claude Code version drops or renames it, this
# hook must not silently stop working — the fallback path below still
# fires (response_words=-1, never blocks) and marks itself on stderr so
# the gap stays visible instead of quietly going dark.
#
# Set TC_CONCISION=off to disable.

set -euo pipefail

# shellcheck disable=SC2034  # read by lib/loud-fail.sh after sourcing
HOOK_NAME="concision-stop"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/loud-fail.sh disable=SC1091
if ! source "$SCRIPT_DIR/lib/loud-fail.sh"; then
    printf '⚠️ concision-stop: cannot source lib/loud-fail.sh\n' >&2
    exit 0
fi

if [ "${TC_CONCISION:-}" = "off" ]; then
    exit 0
fi

require_jq_or_exit

INPUT=""
if ! INPUT="$(cat)"; then
    log_visible "cannot read stdin"
    exit 0
fi

if [ -z "$INPUT" ]; then
    log_visible "empty stdin — no block decision, no telemetry"
    exit 0
fi

require_json_or_exit "$INPUT"

HAS_MSG="no"
if printf '%s' "$INPUT" | jq -e 'has("last_assistant_message")' >/dev/null 2>&1; then
    HAS_MSG="yes"
fi

RESPONSE_WORDS=-1
if [ "$HAS_MSG" = "yes" ]; then
    LAST_MSG=$(printf '%s' "$INPUT" | jq -r '.last_assistant_message' 2>/dev/null) || LAST_MSG=""
    RW=$(printf '%s' "$LAST_MSG" | wc -w | tr -d ' ')
    case "$RW" in
        ''|*[!0-9]*) RESPONSE_WORDS=-1 ;;
        *) RESPONSE_WORDS="$RW" ;;
    esac
else
    log_visible "last_assistant_message field absent — telemetry will show response_words=-1"
fi

SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null) || SESSION_ID=""
if [ -z "$SESSION_ID" ]; then
    log_visible "session_id absent — using 'unknown'"
    SESSION_ID="unknown"
fi
SESSION_KEY="$(sanitize_key "$SESSION_ID" "unknown")"

STOP_HOOK_ACTIVE="false"
if printf '%s' "$INPUT" | jq -e '.stop_hook_active == true' >/dev/null 2>&1; then
    STOP_HOOK_ACTIVE="true"
fi

BAND=300
OVERRIDE="none"
PROMPT_WORDS=-1
STATE_FILE="${TMPDIR:-/tmp}/technical-cofounder/concision-state/${SESSION_KEY}"
if [ -f "$STATE_FILE" ]; then
    STATE_LINE=$(cat "$STATE_FILE" 2>/dev/null) || STATE_LINE=""
    S_BAND=$(printf '%s' "$STATE_LINE" | cut -d'|' -f1)
    S_OVERRIDE=$(printf '%s' "$STATE_LINE" | cut -d'|' -f2)
    S_PROMPT_WORDS=$(printf '%s' "$STATE_LINE" | cut -d'|' -f3)
    case "$S_BAND" in ''|*[!0-9]*) : ;; *) BAND="$S_BAND" ;; esac
    [ -n "${S_OVERRIDE:-}" ] && OVERRIDE="$S_OVERRIDE"
    case "${S_PROMPT_WORDS:-}" in ''|*[!0-9]*) : ;; *) PROMPT_WORDS="$S_PROMPT_WORDS" ;; esac
else
    log_visible "state file $STATE_FILE missing — concision-budget did not fire or state expired; using default band=300"
fi

BLOCKED=false
if [ "$RESPONSE_WORDS" -gt 700 ] && [ "$STOP_HOOK_ACTIVE" != "true" ]; then
    BLOCKED=true
fi

BREACH=false
if [ "$RESPONSE_WORDS" -gt "$BAND" ]; then
    BREACH=true
fi

# Emit the block decision BEFORE telemetry, so a logging failure can never
# suppress a legitimate block.
if [ "$BLOCKED" = "true" ]; then
    echo '{"decision":"block","reason":"Over 700 words: put the conclusion in chat and move the rest to a file."}'
fi

LOG_DIR="${CLAUDE_PLUGIN_DATA:-${TMPDIR:-/tmp}/technical-cofounder}/telemetry"
if mkdir -p "$LOG_DIR" 2>/dev/null; then
    LOG_FILE="$LOG_DIR/$(date -u +%F).jsonl"
    TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    if command -v jq >/dev/null 2>&1; then
        TELEMETRY_LINE=$(jq -nc \
            --arg ts "$TS" --arg session "$SESSION_KEY" \
            --argjson prompt_words "$PROMPT_WORDS" --argjson band "$BAND" \
            --argjson response_words "$RESPONSE_WORDS" --arg override "$OVERRIDE" \
            --argjson breach "$BREACH" --argjson blocked "$BLOCKED" \
            '{ts:$ts, session:$session, prompt_words:$prompt_words, band:$band, response_words:$response_words, override:$override, breach:$breach, blocked:$blocked}' 2>/dev/null) || TELEMETRY_LINE=""
        if [ -n "$TELEMETRY_LINE" ]; then
            echo "$TELEMETRY_LINE" >> "$LOG_FILE" 2>/dev/null || log_visible "cannot append telemetry to $LOG_FILE"
        fi
    fi
else
    log_visible "cannot create telemetry dir $LOG_DIR — skipping telemetry this turn"
fi

exit 0
