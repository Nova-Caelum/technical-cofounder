"""Unit tests for the contact-nova-caelum skill's helpers:
plugins/technical-cofounder/bin/contact.py (POST to the contact Worker, with
retries and a fallback address) and bin/redact.py (the redaction patterns
shared with setup_record.py), plus the shipped wiring (contact.json, the
command, the skill, the agents)."""
import importlib.util
import json
import os
import secrets as _rand
import socket
import string
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "technical-cofounder"
BIN_DIR = PLUGIN_ROOT / "bin"
CONTACT_BIN = BIN_DIR / "contact.py"
FALLBACK = "Email us at hello@novacaelum.com"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, BIN_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(BIN_DIR))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(BIN_DIR))
    return mod


def _fake(prefix, n=32):
    alphabet = string.ascii_letters + string.digits
    return prefix + "".join(_rand.choice(alphabet) for _ in range(n))


# ----------------------------------------------------------- redaction (redact.py)

class RedactionKindTests(unittest.TestCase):
    """Each redaction kind: the secret is gone from the text, and the
    printed REDACTED counts never contain the matched text itself."""

    def _redact(self, content):
        redact = _load("redact")
        out, counts = redact.redact_text(content)
        return types.SimpleNamespace(stdout=redact.format_counts(counts), returncode=0, stderr=""), out

    def test_redacts_unix_home_path(self):
        secret_user = "throwaway-probe-user"
        r, out = self._redact("See /Users/" + secret_user + "/notes/secret-plan.md for context.\n")
        self.assertNotIn(secret_user, out)
        self.assertNotIn(secret_user, r.stdout)
        self.assertIn("[redacted]", out)
        self.assertIn("REDACTED:", r.stdout)
        self.assertIn("path", r.stdout)

    def test_redacts_windows_home_path(self):
        secret_user = "winprobeuser"
        r, out = self._redact(f"Open C:\\Users\\{secret_user}\\Documents\\notes.txt please.\n")
        self.assertNotIn(secret_user, out)
        self.assertNotIn(secret_user, r.stdout)
        self.assertIn("[redacted]", out)
        self.assertIn("path", r.stdout)

    def test_redacts_email(self):
        addr = f"probe-{_rand.token_hex(4)}@example-throwaway.invalid"
        r, out = self._redact(f"Reach me at {addr} if you need more detail.\n")
        self.assertNotIn(addr, out)
        self.assertNotIn(addr, r.stdout)
        self.assertIn("email", r.stdout)

    def test_redacts_private_key_block(self):
        body = "\n".join(_fake("", 60) for _ in range(3))
        pem = f"-----BEGIN RSA PRIVATE KEY-----\n{body}\n-----END RSA PRIVATE KEY-----"
        r, out = self._redact(f"Do not commit this:\n{pem}\nthanks\n")
        self.assertNotIn(body.splitlines()[0], out)
        self.assertNotIn(body.splitlines()[0], r.stdout)
        self.assertNotIn("BEGIN RSA PRIVATE KEY", out)
        self.assertIn("private_key", r.stdout)

    def test_redacts_assignment(self):
        value = _fake("", 32)
        r, out = self._redact(f"config line: STRIPE_SECRET_KEY={value}\nrest of file\n")
        self.assertNotIn(value, out)
        self.assertNotIn(value, r.stdout)
        self.assertIn("STRIPE_SECRET_KEY=[redacted]", out)
        self.assertIn("assignment", r.stdout)

    def test_redacts_stripe_like_key(self):
        key = _fake("sk-" + "live" + "-", 24)
        r, out = self._redact(f"the key was {key} in the log\n")
        self.assertNotIn(key, out)
        self.assertNotIn(key, r.stdout)
        self.assertIn("keyshaped", r.stdout)

    def test_redacts_github_pat(self):
        key = "ghp_" + "".join(_rand.choice(string.ascii_letters + string.digits) for _ in range(36))
        r, out = self._redact(f"the pat is {key} for the CI job\n")
        self.assertNotIn(key, out)
        self.assertNotIn(key, r.stdout)
        self.assertIn("keyshaped", r.stdout)

    def test_redacts_akia(self):
        key = "AKIA" + "".join(_rand.choice(string.ascii_uppercase + string.digits) for _ in range(16))
        r, out = self._redact(f"aws key {key}\n")
        self.assertNotIn(key, out)
        self.assertNotIn(key, r.stdout)
        self.assertIn("keyshaped", r.stdout)

    def test_redacts_slack_token(self):
        key = "xoxb-" + "".join(_rand.choice(string.ascii_letters + string.digits + "-") for _ in range(20))
        r, out = self._redact(f"slack token {key}\n")
        self.assertNotIn(key, out)
        self.assertNotIn(key, r.stdout)
        self.assertIn("keyshaped", r.stdout)

    def test_redacts_generic_high_entropy_token(self):
        token = _fake("", 40)
        r, out = self._redact(f"random blob {token} in prose\n")
        self.assertNotIn(token, out)
        self.assertNotIn(token, r.stdout)
        self.assertIn("token", r.stdout)

    def test_clean_draft_reports_zero(self):
        r, out = self._redact("Nothing sensitive here, just a plain bug report.\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("REDACTED: 0", r.stdout)


    def test_secrets_only_mode_keeps_emails_and_paths(self):
        redact = _load("redact")
        key = _fake("sk-" + "live" + "-", 24)
        text = f"I'm at me@example.org, repo in /Users/me/app, key {key}"
        out, counts = redact.redact_text(text, kinds=redact.SECRET_KINDS)
        self.assertIn("me@example.org", out)
        self.assertIn("/Users/me/app", out)
        self.assertNotIn(key, out)
        self.assertEqual(counts, {"keyshaped": 1})

    def test_setup_record_uses_the_same_patterns(self):
        # setup_record.py lives in the setup plugin, which is installed on its
        # own and cannot import from this one. It carries its own copy of
        # redact.py, and the two copies must stay the same file.
        setup_bin = REPO_ROOT / "plugins" / "technical-cofounder-setup" / "bin"
        text = (setup_bin / "setup_record.py").read_text(encoding="utf-8")
        self.assertIn("from redact import redact_text", text)
        self.assertEqual((setup_bin / "redact.py").read_bytes(), (BIN_DIR / "redact.py").read_bytes())


# ----------------------------------------------------------- contact.py send

class _Server:
    """A local stand-in for the Worker: replies from a script, records requests."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                outer.requests.append({
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": json.loads(self.rfile.read(length) or b"{}"),
                })
                status, payload = outer.replies.pop(0) if outer.replies else (500, {"ok": False})
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/contact"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _free_port_url():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return f"http://127.0.0.1:{s.getsockname()[1]}/contact"


class ContactSendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "plugin"
        (self.root / ".claude-plugin").mkdir(parents=True)
        (self.root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"version": "9.8.7"}), encoding="utf-8")
        self.msg = Path(self.tmp.name) / "message.txt"
        self.msg.write_text("The quick-start guide was great, but step 4 confused me.\n", encoding="utf-8")
        self.contact = _load("contact")
        self.sleeps = []
        patcher = mock.patch.object(self.contact.time, "sleep", side_effect=self.sleeps.append)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def endpoint(self, url):
        (self.root / "contact.json").write_text(json.dumps({"endpoint": url}), encoding="utf-8")

    def send(self, email="ann@example.org", msg=None):
        from io import StringIO
        out = StringIO()
        with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(self.root)}), mock.patch("sys.stdout", out):
            code = self.contact.main(["send", str(msg or self.msg), "--email", email])
        return code, out.getvalue()

    def serve(self, replies):
        srv = _Server(replies)
        self.addCleanup(srv.close)
        self.endpoint(srv.url)
        return srv

    def test_success_prints_sent_with_the_id(self):
        srv = self.serve([(200, {"ok": True, "id": 42})])
        code, out = self.send()
        self.assertEqual(code, 0, out)
        self.assertIn("SENT: 42", out)
        self.assertEqual(len(srv.requests), 1)
        body = srv.requests[0]["body"]
        self.assertEqual(body, {
            "message": "The quick-start guide was great, but step 4 confused me.",
            "email": "ann@example.org",
            "client": "technical-cofounder",
            "version": "9.8.7",
        })
        self.assertIn("application/json", srv.requests[0]["headers"].get("Content-Type", ""))

    def test_invalid_email_is_relayed_and_not_retried(self):
        srv = self.serve([(400, {"ok": False, "field": "email", "reason": "That domain can't receive email."})])
        code, out = self.send(email="x@nomail.example")
        self.assertEqual(code, 2)
        self.assertIn("INVALID email: That domain can't receive email.", out)
        self.assertEqual(len(srv.requests), 1)

    def test_retries_5xx_with_backoff_then_succeeds(self):
        srv = self.serve([(500, {"ok": False}), (503, {"ok": False}), (200, {"ok": True, "id": 7})])
        code, out = self.send()
        self.assertEqual(code, 0, out)
        self.assertIn("SENT: 7", out)
        self.assertEqual(len(srv.requests), 3)
        self.assertEqual(self.sleeps, [1, 2])

    def test_persistent_5xx_fails_with_the_fallback_after_three_retries(self):
        srv = self.serve([(500, {"ok": False})] * 4)
        code, out = self.send()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", out)
        self.assertIn(FALLBACK, out)
        self.assertEqual(len(srv.requests), 4)
        self.assertEqual(self.sleeps, [1, 2, 4])

    def test_network_error_retries_then_fails_with_the_fallback(self):
        self.endpoint(_free_port_url())
        code, out = self.send()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", out)
        self.assertIn(FALLBACK, out)
        self.assertEqual(self.sleeps, [1, 2, 4])

    def test_rate_limit_is_not_retried(self):
        srv = self.serve([(429, {"ok": False, "field": None, "reason": "Too many messages."})])
        code, out = self.send()
        self.assertEqual(code, 1)
        self.assertIn("FAILED: Too many messages.", out)
        self.assertIn(FALLBACK, out)
        self.assertEqual(len(srv.requests), 1)

    def test_keys_are_redacted_before_sending_and_never_printed(self):
        key = _fake("sk-" + "live" + "-", 24)
        self.msg.write_text(f"My setup fails. The key was {key} and it broke.\n", encoding="utf-8")
        srv = self.serve([(200, {"ok": True, "id": 1})])
        code, out = self.send()
        self.assertEqual(code, 0, out)
        self.assertNotIn(key, json.dumps(srv.requests[0]["body"]))
        self.assertNotIn(key, out)
        self.assertIn("REDACTED: 1 keyshaped", out)

    def test_empty_message_is_rejected_without_a_request(self):
        srv = self.serve([])
        self.msg.write_text("   \n", encoding="utf-8")
        code, out = self.send()
        self.assertEqual(code, 2)
        self.assertIn("INVALID message", out)
        self.assertEqual(srv.requests, [])

    def test_missing_endpoint_fails_with_the_fallback(self):
        code, out = self.send()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", out)
        self.assertIn(FALLBACK, out)

    def test_refuses_plain_http_to_a_remote_host(self):
        self.endpoint("http://example.org/contact")
        code, out = self.send()
        self.assertEqual(code, 1)
        self.assertIn("FAILED", out)
        self.assertEqual(self.sleeps, [])

    def test_cli_end_to_end(self):
        srv = self.serve([(200, {"ok": True, "id": 5})])
        env = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(self.root))
        r = subprocess.run(
            [sys.executable, str(CONTACT_BIN), "send", str(self.msg), "--email", "ann@example.org"],
            capture_output=True, text=True, env=env, timeout=30,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "SENT: 5")
        self.assertEqual(len(srv.requests), 1)


# ----------------------------------------------------------- shipped wiring

class ShippedWiringTests(unittest.TestCase):
    def test_contact_json_holds_only_the_https_endpoint(self):
        cfg = json.loads((PLUGIN_ROOT / "contact.json").read_text(encoding="utf-8"))
        self.assertEqual(list(cfg), ["endpoint"])
        self.assertRegex(cfg["endpoint"], r"^https://[a-z0-9.-]+/contact$")

    def test_command_and_skill(self):
        cmds = PLUGIN_ROOT / "commands"
        self.assertTrue((cmds / "contact.md").is_file())
        self.assertFalse((cmds / "ask.md").exists())
        self.assertIn("contact-nova-caelum", (cmds / "contact.md").read_text(encoding="utf-8"))
        skill = (PLUGIN_ROOT / "skills" / "contact-nova-caelum" / "SKILL.md").read_text(encoding="utf-8")
        flat = " ".join(skill.split())
        for needle in (
            "name: contact-nova-caelum",
            "AskUserQuestion",
            "What would you like to tell us?",
            "What email should we reply to?",
            "Send? (yes / edit)",
            'python3 "${CLAUDE_PLUGIN_ROOT}/bin/contact.py" send',
            "INVALID email:",
            "Sent ✓ (#<id>). Thanks, we'll reply to <email>. A confirmation email is on its way.",
            "hello@novacaelum.com",
            "Nothing is ever sent without their yes.",
            "Source: Nova Caelum (Apache-2.0).",
        ):
            self.assertIn(needle, flat, needle)
        self.assertNotIn("python3 -c", skill)

    def test_retired_pieces_are_gone(self):
        self.assertFalse((BIN_DIR / "ask_issue.py").exists())
        self.assertFalse((REPO_ROOT / "tests" / "test_ask.py").exists())
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("tests.test_contact", ci)
        self.assertNotIn("tests.test_ask", ci)

    def test_no_stale_references_remain(self):
        stale = ("ask" + "-nova-caelum", "technical-cofounder" + ":ask", "ask" + "_issue", "whats" + "app",
                 "agents" + "@novacaelum.com")
        skip = {".git", "__pycache__"}
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file() or skip & set(path.parts) or path == Path(__file__).resolve():
                continue
            try:
                text = path.read_text(encoding="utf-8").lower()
            except UnicodeDecodeError:
                continue
            for needle in stale:
                self.assertNotIn(needle, text, f"{needle!r} still in {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    unittest.main()
