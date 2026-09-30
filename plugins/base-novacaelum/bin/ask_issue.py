#!/usr/bin/env python3
"""Redact-and-post helper behind the contact-nova-caelum skill.

Usage:
    python3 ask_issue.py redact <draft.md>
    python3 ask_issue.py env
    python3 ask_issue.py post <draft.md> --title "<title>"
    python3 ask_issue.py whatsapp-link <message.txt>

`redact` rewrites a draft file in place, replacing home-directory paths,
email addresses and several key-shaped strings with `[redacted]`, and prints
only `REDACTED: <n> <kind>` counts — never the matched text.

`env` prints a short, credential-free environment footer: this plugin's
version, whether super-novacaelum is enabled, `claude --version` if on PATH,
and the OS. No username, hostname or path is ever printed.

`post` prefixes the title with `[ask] ` if missing, appends the `env`
footer to the draft, re-runs `redact` (defence in depth), then posts via
`gh issue create` when `gh auth status` succeeds, or prints a prefilled
`issues/new?` URL otherwise. It never posts anywhere but
Nova-Caelum/technical-cofounder, and never invokes a shell.

`whatsapp-link` reads the founder's number from contact.json in the plugin
root, prints `NOT_SET` if it is empty, otherwise `OPEN: <wa.me link>` with the
message prefixed by "[Technical Cofounder] ". The number must be digits only,
8-15 characters; anything else prints `FAILED: <reason>` and exits 1.

Standard library only.
"""
import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path
import os

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or HERE.parent)

REPO = "Nova-Caelum/technical-cofounder"
ASK_PREFIX = "[ask] "
WHATSAPP_PREFIX = "[Technical Cofounder] "
WHATSAPP_RE = re.compile(r"\d{8,15}")
MAX_URL_LEN = 7000
TRUNCATION_NOTE = "\n\n[Note: this draft was truncated to fit the link's length limit.]"

# --- redaction patterns -----------------------------------------------------

PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
ASSIGNMENT_RE = re.compile(
    r"\b(\w*(?:KEY|TOKEN|SECRET|PASSWORD)\w*)(\s*[:=]\s*)(\"[^\"\n]*\"|'[^'\n]*'|\S+)",
    re.IGNORECASE,
)
KEYSHAPED_RE = re.compile(
    r"\bsk-[A-Za-z0-9_-]{10,}\b"
    r"|\bgh[po]_[A-Za-z0-9]{20,}\b"
    r"|\bgithub_pat_[A-Za-z0-9_]{20,}\b"
    r"|\bAKIA[0-9A-Z]{16}\b"
    r"|\bxox[bap]-[A-Za-z0-9-]{10,}\b"
)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
HOME_UNIX_RE = re.compile(r"(?:/(?:Users|home)/)[\w.\-]+(?:/[\w.\-]+)*")
HOME_WIN_RE = re.compile(r"[A-Za-z]:\\Users\\[\w.\-]+(?:\\[\w.\-]+)*", re.IGNORECASE)
TOKEN_RE = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")

# Printed in this order; only kinds with count > 0 are shown.
REDACT_ORDER = ("path", "email", "private_key", "assignment", "keyshaped", "token")


def redact_text(text):
    """Returns (redacted_text, counts). Applied in an order that never lets
    a later, broader pattern (e.g. the generic high-entropy token scan)
    re-match text a more specific pattern already replaced."""
    counts = {}

    def sub(pattern, repl, kind, s):
        s2, n = pattern.subn(repl, s)
        if n:
            counts[kind] = counts.get(kind, 0) + n
        return s2

    text = sub(PRIVATE_KEY_RE, "[redacted]", "private_key", text)
    text = sub(ASSIGNMENT_RE, r"\1\2[redacted]", "assignment", text)
    text = sub(KEYSHAPED_RE, "[redacted]", "keyshaped", text)
    text = sub(EMAIL_RE, "[redacted]", "email", text)
    text = sub(HOME_WIN_RE, "[redacted]", "path", text)
    text = sub(HOME_UNIX_RE, "[redacted]", "path", text)
    text = sub(TOKEN_RE, "[redacted]", "token", text)
    return text, counts


def cmd_redact(argv):
    parser = argparse.ArgumentParser(prog="ask_issue.py redact")
    parser.add_argument("draft")
    args = parser.parse_args(argv)

    path = Path(args.draft)
    original = path.read_text(encoding="utf-8")
    redacted, counts = redact_text(original)
    path.write_text(redacted, encoding="utf-8")

    total = sum(counts.values())
    if total == 0:
        print("REDACTED: 0 total")
    else:
        for kind in REDACT_ORDER:
            if counts.get(kind):
                print(f"REDACTED: {counts[kind]} {kind}")
    return 0


# --- env ---------------------------------------------------------------

def _plugin_version():
    plugin_json = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
    try:
        data = json.loads(plugin_json.read_text(encoding="utf-8"))
        return str(data.get("version", "unknown"))
    except Exception:
        return "unknown"


def _super_enabled():
    for settings_path in (Path.cwd() / ".claude" / "settings.json", Path.home() / ".claude" / "settings.json"):
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        enabled = data.get("enabledPlugins") if isinstance(data, dict) else None
        if isinstance(enabled, dict):
            for name, val in enabled.items():
                if val and isinstance(name, str) and name.startswith("super-novacaelum@"):
                    return True
    return False


def _claude_version():
    exe = shutil.which("claude")
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    out = (r.stdout or r.stderr or "").strip().splitlines()
    return out[0] if out else None


def env_lines():
    lines = [f"base-novacaelum: {_plugin_version()}"]
    lines.append(f"super-novacaelum: {'enabled' if _super_enabled() else 'not enabled'}")
    claude_version = _claude_version()
    if claude_version:
        lines.append(f"claude: {claude_version}")
    lines.append(f"OS: {platform.system()} {platform.release()}")
    return lines


def cmd_env(_argv):
    print("\n".join(env_lines()))
    return 0


# --- post ----------------------------------------------------------------

def _gh_auth_ok():
    exe = shutil.which("gh")
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, timeout=15)
    except Exception:
        return False
    return r.returncode == 0


def _build_open_url(title, body):
    base = f"https://github.com/{REPO}/issues/new?"
    encoded_title = urllib.parse.quote(title, safe="")

    def make_url(b):
        return base + "title=" + encoded_title + "&body=" + urllib.parse.quote(b, safe="")

    url = make_url(body)
    if len(url) <= MAX_URL_LEN:
        return url

    low, high, best = 0, len(body), ""
    while low <= high:
        mid = (low + high) // 2
        candidate = body[:mid].rstrip() + TRUNCATION_NOTE
        if len(make_url(candidate)) <= MAX_URL_LEN:
            best = candidate
            low = mid + 1
        else:
            high = mid - 1
    return make_url(best)


def cmd_post(argv):
    parser = argparse.ArgumentParser(prog="ask_issue.py post")
    parser.add_argument("draft")
    parser.add_argument("--title", required=True)
    args = parser.parse_args(argv)

    draft_path = Path(args.draft)
    title = args.title if args.title.startswith(ASK_PREFIX) else ASK_PREFIX + args.title
    # Redact AFTER prefixing, so the `[ask] ` prefix itself survives intact
    # (nothing in it matches any redaction pattern). A path or key typed
    # into --title must never reach the posted issue.
    title, _title_counts = redact_text(title)

    # 1. append the env footer to the draft file.
    original = draft_path.read_text(encoding="utf-8")
    with_footer = original.rstrip("\n") + "\n\n---\n" + "\n".join(env_lines()) + "\n"
    draft_path.write_text(with_footer, encoding="utf-8")

    # 2. re-run redact, defence in depth. Silent: `post` prints only
    #    POSTED:/OPEN:/FAILED:, per its own contract.
    redacted, _counts = redact_text(draft_path.read_text(encoding="utf-8"))
    draft_path.write_text(redacted, encoding="utf-8")
    body_text = redacted

    if not _gh_auth_ok():
        print(f"OPEN: {_build_open_url(title, body_text)}")
        return 0

    try:
        r = subprocess.run(
            ["gh", "issue", "create", "-R", REPO, "--title", title, "--body-file", str(draft_path)],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        print(f"OPEN: {_build_open_url(title, body_text)}")
        return 0

    if r.returncode == 0:
        url = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        print(f"POSTED: {url}")
        return 0

    stderr_first = r.stderr.strip().splitlines()[0] if r.stderr.strip() else "gh issue create failed"
    print(f"FAILED: {stderr_first}")
    print(f"OPEN: {_build_open_url(title, body_text)}")
    return 1


# --- whatsapp-link -------------------------------------------------------

def cmd_whatsapp_link(argv):
    parser = argparse.ArgumentParser(prog="ask_issue.py whatsapp-link")
    parser.add_argument("message")
    args = parser.parse_args(argv)

    try:
        cfg = json.loads((PLUGIN_ROOT / "contact.json").read_text(encoding="utf-8"))
        number = cfg["whatsapp"]
    except (OSError, ValueError, KeyError, TypeError):
        print("FAILED: contact.json is missing or unreadable")
        return 1
    if not isinstance(number, str):
        print("FAILED: contact.json whatsapp must be a string of digits")
        return 1
    if number == "":
        print("NOT_SET")
        return 0
    if not WHATSAPP_RE.fullmatch(number):
        print("FAILED: contact.json whatsapp must be digits only, 8-15 characters")
        return 1

    try:
        message = Path(args.message).read_text(encoding="utf-8").strip()
    except OSError:
        print("FAILED: message file unreadable")
        return 1
    if not message:
        print("FAILED: message is empty")
        return 1

    text = urllib.parse.quote(WHATSAPP_PREFIX + message, safe="")
    print(f"OPEN: https://wa.me/{number}?text={text}")
    return 0


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: ask_issue.py redact <draft.md> | env | post <draft.md> --title \"<t>\" | whatsapp-link <message.txt>\n")
        return 2
    sub, rest = argv[1], argv[2:]
    if sub == "redact":
        return cmd_redact(rest)
    if sub == "env":
        return cmd_env(rest)
    if sub == "post":
        return cmd_post(rest)
    if sub == "whatsapp-link":
        return cmd_whatsapp_link(rest)
    sys.stderr.write(f"ask_issue.py: unknown subcommand {sub!r}\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
