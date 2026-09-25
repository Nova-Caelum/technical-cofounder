#!/bin/bash
# concision-contract.sh — UserPromptSubmit hook.
#
# Source: adapted from Nova Caelum's internal agentOS concision-contract
# hook (2026). License: MIT.
#
# Injects a short, static "minimal sufficient output" contract into
# context once per session. Fires on UserPromptSubmit and self-gates on a
# per-session marker file so the contract text is spent once, not on every
# turn.
#
# Observed failure: an earlier version of this injection relied on an
# output-style setting that turned out to be silently suppressed under
# some launch surfaces. Injecting the contract as plain SessionStart/
# UserPromptSubmit text is the fallback that was empirically confirmed to
# actually reach context on every launch surface tested.
#
# Set TC_CONCISION=off to disable.

set -euo pipefail

# shellcheck disable=SC2034  # read by lib/loud-fail.sh after sourcing
HOOK_NAME="concision-contract"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/loud-fail.sh disable=SC1091
if ! source "$SCRIPT_DIR/lib/loud-fail.sh"; then
    printf '⚠️ concision-contract: cannot source lib/loud-fail.sh\n' >&2
    exit 0
fi

if [ "${TC_CONCISION:-}" = "off" ]; then
    exit 0
fi

INPUT=""
if ! INPUT="$(cat)"; then
    INPUT=""
fi

SESSION_ID=""
if [ -n "$INPUT" ] && command -v jq >/dev/null 2>&1 && printf '%s' "$INPUT" | jq -e . >/dev/null 2>&1; then
    SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null) || SESSION_ID=""
fi

if [ -z "$SESSION_ID" ]; then
    log_visible "session_id unavailable — injecting without a once-per-session guard"
else
    SESSION_KEY="$(sanitize_key "$SESSION_ID" "nosession")"
    STATE_DIR="${TMPDIR:-/tmp}/base-novacaelum/concision-state"
    mkdir -p "$STATE_DIR" 2>/dev/null || true
    MARKER_FILE="$STATE_DIR/contract-injected-${SESSION_KEY}"
    if [ -f "$MARKER_FILE" ]; then
        exit 0
    fi
    : > "$MARKER_FILE" 2>/dev/null || true
fi

cat <<'EOF'
═══ MINIMAL SUFFICIENT OUTPUT CONTRACT ═══
1. Lead with the answer. Include only: the outcome, the evidence needed to
   trust it, and any unresolved decision or material risk.
2. Omit: request recaps, process narration, repeated evidence, generic
   advice, follow-up-offer menus, decorative structure on short answers.
3. Match the scale of the ask; a RESPONSE BUDGET line, when present, is
   binding.
4. Overflow -> a file: write it, reply with the conclusion plus the path.
   A bare pointer with no conclusion is non-compliant. Never truncate a
   long deliverable with a placeholder — write all of it, or say plainly
   that it's partial and why.

Example — Q (9 words): "What broke in the deploy last night?"
Bad:  a 400-word essay with headers, background, and a "let me know if" close.
Good: "The deploy script never removed a stale config file, so the old
       version kept running behind the new one. Fixed by deleting it
       before deploy; added a cleanup step so this can't recur. (~25 w)"
EOF
exit 0
