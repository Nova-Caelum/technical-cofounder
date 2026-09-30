#!/usr/bin/env python3
"""Sends a /base-novacaelum:contact message to Nova Caelum.

Usage:
    python3 contact.py send <message-file> --email <reply-address>

POSTs {message, email, client, version} to the endpoint in contact.json (the
one place the URL lives). Key-shaped strings are redacted from the message
first. Prints exactly one outcome line (after an optional `REDACTED:` line):

    SENT: <id>                   stored; exit 0
    INVALID <field>: <reason>    fix the field and resend; exit 2
    FAILED: <reason>             then "Email us at hello@novacaelum.com"; exit 1

Network errors and 5xx responses are retried 3 times (1 s, 2 s, 4 s). Other
4xx responses (such as a rate limit) are not. Standard library only.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from redact import SECRET_KINDS, format_counts, redact_text  # noqa: E402

CLIENT = "technical-cofounder"
FALLBACK = "Email us at hello@novacaelum.com"
BACKOFF = (1, 2, 4)
TIMEOUT = 15
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class Failed(Exception):
    """A send that should end with FAILED plus the fallback address."""


def plugin_root():
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent)


def load_endpoint(root):
    try:
        url = json.loads((root / "contact.json").read_text(encoding="utf-8"))["endpoint"]
    except (OSError, ValueError, KeyError, TypeError):
        raise Failed("the contact endpoint isn't configured")
    parts = urllib.parse.urlsplit(url if isinstance(url, str) else "")
    if not (parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in LOOPBACK)):
        raise Failed("the contact endpoint must use https")
    return url


def plugin_version(root):
    try:
        return str(json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def post(url, payload, version):
    """Returns (status, body_dict). Raises OSError on a network failure."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": f"base-novacaelum-contact/{version or '0'}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            status, raw = res.status, res.read()
    except urllib.error.HTTPError as err:
        status, raw = err.code, err.read()
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        body = {}
    return status, body if isinstance(body, dict) else {}


def send(message_file, email):
    root = plugin_root()
    try:
        message = Path(message_file).read_text(encoding="utf-8").strip()
    except OSError:
        raise Failed("the message file couldn't be read")
    if not message:
        print("INVALID message: The message is empty. What would you like to tell us?")
        return 2
    message, counts = redact_text(message, kinds=SECRET_KINDS)
    if counts:
        print(format_counts(counts).replace("\n", ", "))

    url = load_endpoint(root)
    version = plugin_version(root)
    payload = {"message": message, "email": email.strip(), "client": CLIENT, "version": version}

    reason = "no response"
    for attempt in range(len(BACKOFF) + 1):
        if attempt:
            time.sleep(BACKOFF[attempt - 1])
        try:
            status, body = post(url, payload, version)
        except OSError as err:
            reason = f"couldn't reach Nova Caelum ({type(err).__name__})"
            continue
        if 200 <= status < 300 and body.get("ok") and body.get("id") is not None:
            print(f"SENT: {body['id']}")
            return 0
        if status >= 500 or 200 <= status < 300:
            reason = f"the server answered {status}"
            continue
        field = body.get("field")
        text = str(body.get("reason") or f"the server answered {status}")
        if field in ("email", "message"):
            print(f"INVALID {field}: {text}")
            return 2
        raise Failed(text)
    raise Failed(reason)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="contact.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_send = sub.add_parser("send", help="send a message file to Nova Caelum")
    p_send.add_argument("message_file")
    p_send.add_argument("--email", required=True)
    args = parser.parse_args(argv)
    try:
        return send(args.message_file, args.email)
    except Failed as err:
        print(f"FAILED: {err}")
        print(FALLBACK)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows pipes default to the ANSI code page
    sys.exit(main())
