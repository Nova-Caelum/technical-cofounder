"""concision_stop.py — Stop hook (run by concision-stop.sh).

Source: adapted from Nova Caelum's internal agentOS concision-stop hook
(2026). License: MIT.

Hard-blocks a response over 700 words (retry cap 1 via stop_hook_active),
and — when a state file exists from concision_budget.py — logs whether the
response breached its assigned budget. Telemetry is local only: it goes to
${CLAUDE_PLUGIN_DATA} if set, else the temp dir, or nowhere at all. Nothing
here ever leaves this machine.

Observed failure: `last_assistant_message` is an undocumented Stop-hook stdin
field. If a future Claude Code version drops or renames it, this hook must not
silently stop working — the fallback path below still fires
(response_words=-1, never blocks) and marks itself on stderr so the gap stays
visible instead of quietly going dark.

Set TC_CONCISION=off to disable.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from _shared import field, log_visible, parse_json, raw, read_stdin, sanitize_key, state_root, utf8_stdio

HOOK = "concision-stop"
BLOCK = '{"decision":"block","reason":"Over 700 words: put the conclusion in chat and move the rest to a file."}'


def digits(value):
    return value if value.isascii() and value.isdigit() else None


def cut(line, n):
    """`cut -d'|' -fN` on one line: a line with no delimiter is its own every field."""
    parts = line.split("|")
    if len(parts) == 1:
        return line
    return parts[n - 1] if n <= len(parts) else ""


def main():
    utf8_stdio()
    if os.environ.get("TC_CONCISION") == "off":
        return 0
    text = read_stdin()
    if text is None:
        log_visible(HOOK, "cannot read stdin")
        return 0
    if not text.rstrip("\n"):
        log_visible(HOOK, "empty stdin — no block decision, no telemetry")
        return 0
    ok, data = parse_json(text)
    if not ok:
        log_visible(HOOK, "malformed JSON on stdin — skipping this invocation (fail-open)")
        return 0

    response_words = -1
    if isinstance(data, dict) and "last_assistant_message" in data:
        response_words = len(raw(data["last_assistant_message"]).split())
    else:
        log_visible(HOOK, "last_assistant_message field absent — telemetry will show response_words=-1")

    session_id = field(data, "session_id")
    if not session_id:
        log_visible(HOOK, "session_id absent — using 'unknown'")
        session_id = "unknown"
    session_key = sanitize_key(session_id, "unknown")
    stop_hook_active = isinstance(data, dict) and data.get("stop_hook_active") is True

    band, override, prompt_words = 300, "none", -1
    state_file = state_root() / "concision-state" / session_key
    if state_file.is_file():
        try:
            line = state_file.read_text(encoding="utf-8").rstrip("\n")
        except (OSError, ValueError):
            line = ""
        band = int(digits(cut(line, 1)) or band)
        override = cut(line, 2) or override
        prompt_words = int(digits(cut(line, 3)) or prompt_words)
    else:
        log_visible(HOOK, f"state file {state_file} missing — concision-budget did not fire or state expired; using default band=300")

    blocked = response_words > 700 and not stop_hook_active
    breach = response_words > band

    # Emit the block decision BEFORE telemetry, so a logging failure can never
    # suppress a legitimate block.
    if blocked:
        print(BLOCK, flush=True)

    log_dir = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or state_root()) / "telemetry"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log_visible(HOOK, f"cannot create telemetry dir {log_dir} — skipping telemetry this turn")
        return 0
    now = datetime.now(timezone.utc)
    log_file = log_dir / f"{now:%Y-%m-%d}.jsonl"
    record = {"ts": f"{now:%Y-%m-%dT%H:%M:%SZ}", "session": session_key, "prompt_words": prompt_words,
              "band": band, "response_words": response_words, "override": override,
              "breach": breach, "blocked": blocked}
    try:
        with open(log_file, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError:
        log_visible(HOOK, f"cannot append telemetry to {log_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
