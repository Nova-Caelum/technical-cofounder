"""concision_budget.py — UserPromptSubmit hook (run by concision-budget.sh).

Source: adapted from Nova Caelum's internal agentOS concision-budget hook
(2026). License: MIT.

Selects a response-length band from the incoming prompt, writes per-session
state for concision_stop.py to read, and emits a binding RESPONSE BUDGET line
into context.

Band selection — first match wins, case-insensitive:
  1. brief markers (quick|brief|just|check-in) as whole words, OR a short
     question (a line ends "?" and the prompt is <=15 words)       -> 120
  2. depth markers (go deep|deep dive|walk me through|comprehensive|full|
     long form), minus a cheap negation guard                       -> 650
  3. default                                                        -> 300

Observed failure: an earlier version of this hook silently swallowed every
error (broken state writes, missing fields) with no signal anywhere, so the
whole mechanism could quietly stop working. Every failure path here is loud on
stderr instead, even though the hook still exits 0 and never blocks the prompt.

Set TC_CONCISION=off in the environment to disable this hook.
"""
import os
import re
import sys

from _shared import field, log_visible, parse_json, read_stdin, sanitize_key, state_root, utf8_stdio

HOOK = "concision-budget"
DEFAULT_LINE = "RESPONSE BUDGET: <=300 words. Conclusion stays in chat; overflow detail -> a file."
BRIEF = r"quick|brief|just|check-in"
DEPTH = r"go deep|deep dive|walk me through|comprehensive|full|long form"
NEGATED_DEPTH = rf"(don't|do not|not|no need to)( [a-z0-9'-]+){{0,1}} ({DEPTH})"


def whole_word(pattern, text):
    """`grep -Eqw`: a match with no word character on either side."""
    return re.search(rf"(?<![A-Za-z0-9_])(?:{pattern})(?![A-Za-z0-9_])", text) is not None


def band_for(prompt):
    lower = prompt.lower()
    words = len(prompt.split())
    if whole_word(BRIEF, lower):
        return 120, "brief", words
    if re.search(r"\?\s*$", lower, re.MULTILINE) and words <= 15:
        return 120, "brief", words
    if whole_word(DEPTH, lower):
        if re.search(NEGATED_DEPTH, lower):
            return 300, "none", words
        return 650, "deep", words
    return 300, "none", words


def main():
    utf8_stdio()
    if os.environ.get("TC_CONCISION") == "off":
        return 0
    text = read_stdin()
    if text is None:
        log_visible(HOOK, "cannot read stdin")
        return 0
    if not text.rstrip("\n"):
        log_visible(HOOK, "empty stdin — emitting default 300-word budget")
        print(DEFAULT_LINE)
        return 0
    ok, data = parse_json(text)
    if not ok:
        log_visible(HOOK, "malformed JSON on stdin — skipping this invocation (fail-open)")
        return 0

    prompt = field(data, "prompt")
    session_id = field(data, "session_id")
    if not session_id:
        log_visible(HOOK, "session_id absent — emitting default budget, skipping state write")
        print(DEFAULT_LINE)
        return 0

    band, override, words = band_for(prompt)
    line = f"RESPONSE BUDGET: <={band} words. Conclusion stays in chat; overflow detail -> a file."
    state_dir = state_root() / "concision-state"
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_visible(HOOK, f"cannot create state dir {state_dir} — budget line only, no handoff to Stop hook")
        print(line)
        return 0
    state_file = state_dir / sanitize_key(session_id, "nosession")
    try:
        with open(state_file, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f"{band}|{override}|{words}\n")
    except OSError:
        log_visible(HOOK, f"cannot write state file {state_file}")
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
