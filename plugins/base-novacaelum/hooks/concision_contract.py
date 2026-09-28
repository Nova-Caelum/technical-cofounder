"""concision_contract.py — UserPromptSubmit hook (run by concision-contract.sh).

Source: adapted from Nova Caelum's internal agentOS concision-contract hook
(2026). License: MIT.

Injects a short, static "minimal sufficient output" contract into context
once per session. Fires on UserPromptSubmit and self-gates on a per-session
marker file so the contract text is spent once, not on every turn.

Observed failure: an earlier version of this injection relied on an
output-style setting that turned out to be silently suppressed under some
launch surfaces. Injecting the contract as plain UserPromptSubmit text is the
fallback that was empirically confirmed to actually reach context on every
launch surface tested.

Set TC_CONCISION=off to disable.
"""
import os
import sys

from _shared import field, log_visible, parse_json, read_stdin, sanitize_key, state_root, utf8_stdio

HOOK = "concision-contract"
CONTRACT = """═══ MINIMAL SUFFICIENT OUTPUT CONTRACT ═══
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
       before deploy; added a cleanup step so this can't recur. (~25 w)\""""


def main():
    utf8_stdio()
    if os.environ.get("TC_CONCISION") == "off":
        return 0
    text = read_stdin() or ""
    session_id = ""
    if text.rstrip("\n"):
        ok, data = parse_json(text)
        if ok:
            session_id = field(data, "session_id")

    if not session_id:
        log_visible(HOOK, "session_id unavailable — injecting without a once-per-session guard")
    else:
        state_dir = state_root() / "concision-state"
        marker = state_dir / f"contract-injected-{sanitize_key(session_id, 'nosession')}"
        if marker.is_file():
            return 0
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
            marker.touch()
        except OSError:
            pass
    print(CONTRACT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
