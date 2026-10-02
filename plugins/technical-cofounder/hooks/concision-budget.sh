#!/bin/bash
# concision-budget.sh — UserPromptSubmit hook.
#
# Source: adapted from Nova Caelum's internal agentOS concision-budget hook
# (2026). License: MIT.
#
# Selects a response-length band from the incoming prompt, writes
# per-session state for concision-stop.sh to read, and emits a binding
# RESPONSE BUDGET line into context.
#
# Band selection — first match wins, case-insensitive:
#   1. brief markers (quick|brief|just|check-in) OR a short question
#      (ends "?" and <=15 words)                                  -> 120
#   2. depth markers (go deep|deep dive|walk me through|
#      comprehensive|full|long form), minus a cheap negation guard -> 650
#   3. default                                                     -> 300
#
# Observed failure: an earlier version of this hook silently swallowed
# every error (broken state writes, missing fields) with no signal
# anywhere, so the whole mechanism could quietly stop working. Every
# failure path here is loud on stderr instead, even though the hook still
# exits 0 and never blocks the prompt.
#
# Set TC_CONCISION=off in the environment to disable this hook.

set -euo pipefail

# shellcheck disable=SC2034  # read by lib/loud-fail.sh after sourcing
HOOK_NAME="concision-budget"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/loud-fail.sh disable=SC1091
if ! source "$SCRIPT_DIR/lib/loud-fail.sh"; then
    printf '⚠️ concision-budget: cannot source lib/loud-fail.sh\n' >&2
    exit 0
fi
# shellcheck source=lib/resolve-tools.sh disable=SC1091
if ! source "$SCRIPT_DIR/lib/resolve-tools.sh"; then
    log_visible "cannot source lib/resolve-tools.sh — python and jq will not be found"
    export NC_PYTHON="" NC_JQ=""
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

DEFAULT_LINE="RESPONSE BUDGET: <=300 words. Conclusion stays in chat; overflow detail -> a file."

if [ -z "$INPUT" ]; then
    log_visible "empty stdin — emitting default 300-word budget"
    echo "$DEFAULT_LINE"
    exit 0
fi

require_json_or_exit "$INPUT"

PROMPT=$(printf '%s' "$INPUT" | "$NC_JQ" -r '.prompt // empty' 2>/dev/null) || PROMPT=""
SESSION_ID=$(printf '%s' "$INPUT" | "$NC_JQ" -r '.session_id // empty' 2>/dev/null) || SESSION_ID=""

if [ -z "$SESSION_ID" ]; then
    log_visible "session_id absent — emitting default budget, skipping state write"
    echo "$DEFAULT_LINE"
    exit 0
fi

PROMPT_LOWER=$(printf '%s' "$PROMPT" | tr '[:upper:]' '[:lower:]')
PROMPT_WORDS=$(printf '%s' "$PROMPT" | wc -w | tr -d ' ')
case "$PROMPT_WORDS" in ''|*[!0-9]*) PROMPT_WORDS=0 ;; esac

BAND=300
OVERRIDE="none"

BRIEF_RE='quick|brief|just|check-in'
DEPTH_RE='go deep|deep dive|walk me through|comprehensive|full|long form'
NEG_RE="(don't|do not|not|no need to)( [a-z0-9'-]+){0,1} ($DEPTH_RE)"

if printf '%s' "$PROMPT_LOWER" | grep -Eqw "$BRIEF_RE"; then
    BAND=120
    OVERRIDE="brief"
elif printf '%s' "$PROMPT_LOWER" | grep -Eq '\?[[:space:]]*$' && [ "$PROMPT_WORDS" -le 15 ]; then
    BAND=120
    OVERRIDE="brief"
elif printf '%s' "$PROMPT_LOWER" | grep -Eqw "$DEPTH_RE"; then
    if printf '%s' "$PROMPT_LOWER" | grep -Eq "$NEG_RE"; then
        BAND=300
        OVERRIDE="none"
    else
        BAND=650
        OVERRIDE="deep"
    fi
fi

SESSION_KEY="$(sanitize_key "$SESSION_ID" "nosession")"
STATE_DIR="${TMPDIR:-/tmp}/technical-cofounder/concision-state"
if ! mkdir -p "$STATE_DIR" 2>/dev/null; then
    log_visible "cannot create state dir $STATE_DIR — budget line only, no handoff to Stop hook"
    echo "RESPONSE BUDGET: <=${BAND} words. Conclusion stays in chat; overflow detail -> a file."
    exit 0
fi
STATE_FILE="$STATE_DIR/${SESSION_KEY}"
if ! printf '%s|%s|%s\n' "$BAND" "$OVERRIDE" "$PROMPT_WORDS" > "$STATE_FILE" 2>/dev/null; then
    log_visible "cannot write state file $STATE_FILE"
fi

echo "RESPONSE BUDGET: <=${BAND} words. Conclusion stays in chat; overflow detail -> a file."
exit 0
