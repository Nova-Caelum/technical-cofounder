#!/bin/bash
# lib/rule-disclosure.sh — shared JSON delivery helper for guardrail hooks
# that need to put a warning into the model's context via
# hookSpecificOutput.additionalContext — the only channel PreToolUse and
# PostToolUseFailure hooks have for this; plain stdout is not read on those
# events (it is read on SessionStart/UserPromptSubmit/Stop instead).
#
# Source: adapted from Nova Caelum's internal agentOS hook library (2026).
# License: MIT.
#
# Usage — call as the LAST action in the hook:
#   rule_disclosure_emit "<hook_event_name>" "<context text>"
# Prints the JSON payload to stdout and exits 0. Never returns; callers
# must not place code after the call.
#
# Hook secret handling: the second argument reaches model-visible context
# verbatim. Callers must never pass credential material as context text.

rule_disclosure_emit() {
    local hook_event_name="${1:?rule_disclosure_emit: hook_event_name required}"
    local context_text="${2:?rule_disclosure_emit: context_text required}"

    if command -v jq >/dev/null 2>&1; then
        local payload
        if payload=$(jq -nc \
            --arg event "$hook_event_name" \
            --arg ctx "$context_text" \
            '{hookSpecificOutput: {hookEventName: $event, additionalContext: $ctx}}' 2>/dev/null); then
            printf '%s\n' "$payload"
            exit 0
        fi
    fi

    # jq unavailable or failed to build the payload — degrade to a minimal
    # hand-escaped payload rather than dropping the warning silently.
    local escaped
    escaped=$(printf '%s' "$context_text" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | tr '\n' ' ')
    printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}\n' \
        "$hook_event_name" "$escaped"
    exit 0
}
