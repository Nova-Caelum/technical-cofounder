"""Unit tests for plugins/base-novacaelum/bin/ask_issue.py: the redact,
env, post and whatsapp-link subcommands behind the contact-nova-caelum skill.

Standard library only. Never posts to a real repo: every `post` test runs
against a stub `gh` placed first on PATH, and no test ever hits the network.
Fixtures build key-shaped strings at runtime (never as source-file literals)
so the leak scanner stays clean.
"""
import getpass
import json
import os
import secrets as _rand
import string
import subprocess
import tempfile
import unittest
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "base-novacaelum"
BIN = PLUGIN_ROOT / "bin" / "ask_issue.py"
REPO_SLUG = "Nova-Caelum/technical-cofounder"

STUB_GH_AUTHENTICATED = """#!/bin/bash
set -euo pipefail
RECORD="${{ASK_TEST_GH_RECORD:?}}"
if [ "$1" = "auth" ] && [ "$2" = "status" ]; then
    exit 0
fi
if [ "$1" = "issue" ] && [ "$2" = "create" ]; then
    printf '%s\\n' "$@" > "$RECORD"
    echo "{issue_url}"
    exit 0
fi
echo "stub gh: unrecognized invocation: $*" >&2
exit 3
"""

STUB_GH_UNAUTHENTICATED = """#!/bin/bash
set -euo pipefail
if [ "$1" = "auth" ] && [ "$2" = "status" ]; then
    exit 1
fi
echo "stub gh: unrecognized invocation: $*" >&2
exit 3
"""

STUB_GH_ISSUE_CREATE_FAILS = """#!/bin/bash
set -euo pipefail
if [ "$1" = "auth" ] && [ "$2" = "status" ]; then
    exit 0
fi
if [ "$1" = "issue" ] && [ "$2" = "create" ]; then
    echo "some gh stderr line one" >&2
    echo "second line" >&2
    exit 1
fi
echo "stub gh: unrecognized invocation: $*" >&2
exit 3
"""


def _fake(prefix, n=32):
    alphabet = string.ascii_letters + string.digits
    return prefix + "".join(_rand.choice(alphabet) for _ in range(n))


def _write_stub_gh(tmpdir, script_text, issue_url=None):
    bindir = Path(tmpdir) / "stubbin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    text = script_text.format(issue_url=issue_url) if issue_url else script_text
    gh.write_text(text, encoding="utf-8")
    gh.chmod(0o755)
    return bindir


def run_ask(args, cwd=None, env_extra=None, path_prepend=None):
    env = os.environ.copy()
    if path_prepend is not None:
        env["PATH"] = f"{path_prepend}{os.pathsep}{env.get('PATH', '')}"
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["python3", str(BIN), *args],
        cwd=cwd, capture_output=True, text=True, env=env, timeout=30,
    )


def parse_open_url(stdout):
    line = next(ln for ln in stdout.splitlines() if ln.startswith("OPEN: "))
    url = line[len("OPEN: "):].strip()
    prefix = f"https://github.com/{REPO_SLUG}/issues/new?"
    assert url.startswith(prefix), url
    qs = urllib.parse.parse_qs(url[len(prefix):])
    return url, qs.get("title", [""])[0], qs.get("body", [""])[0]


class RedactionKindTests(unittest.TestCase):
    """Each redaction kind: the secret is gone from the file, and the
    printed REDACTED counts never contain the matched text itself."""

    def _redact(self, content):
        with tempfile.TemporaryDirectory() as td:
            draft = Path(td) / "draft.md"
            draft.write_text(content, encoding="utf-8")
            r = run_ask(["redact", str(draft)])
            self.assertEqual(r.returncode, 0, r.stderr)
            return r, draft.read_text(encoding="utf-8")

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


class AskPrefixIdempotentTests(unittest.TestCase):
    def test_prefix_added_once_and_not_doubled(self):
        with tempfile.TemporaryDirectory() as td:
            draft = Path(td) / "draft.md"
            draft.write_text("A plain bug report.\n", encoding="utf-8")
            record = Path(td) / "record.txt"
            stubbin = _write_stub_gh(td, STUB_GH_AUTHENTICATED, issue_url=f"https://github.com/{REPO_SLUG}/issues/1")

            r1 = run_ask(["post", str(draft), "--title", "Something broke"],
                         env_extra={"ASK_TEST_GH_RECORD": str(record)}, path_prepend=str(stubbin))
            self.assertEqual(r1.returncode, 0, r1.stderr)
            argv1 = record.read_text(encoding="utf-8")
            self.assertIn("[ask] Something broke", argv1)
            self.assertNotIn("[ask] [ask]", argv1)

            draft.write_text("A plain bug report.\n", encoding="utf-8")
            r2 = run_ask(["post", str(draft), "--title", "[ask] Something broke"],
                         env_extra={"ASK_TEST_GH_RECORD": str(record)}, path_prepend=str(stubbin))
            self.assertEqual(r2.returncode, 0, r2.stderr)
            argv2 = record.read_text(encoding="utf-8")
            self.assertIn("[ask] Something broke", argv2)
            self.assertNotIn("[ask] [ask]", argv2)


class PostViaStubGhTests(unittest.TestCase):
    def test_authenticated_stub_records_repo_title_and_body_file(self):
        with tempfile.TemporaryDirectory() as td:
            draft = Path(td) / "draft.md"
            draft.write_text("What I tried, what happened, what I tried next.\n", encoding="utf-8")
            record = Path(td) / "record.txt"
            issue_url = f"https://github.com/{REPO_SLUG}/issues/42"
            stubbin = _write_stub_gh(td, STUB_GH_AUTHENTICATED, issue_url=issue_url)

            r = run_ask(["post", str(draft), "--title", "Draft title here"],
                        env_extra={"ASK_TEST_GH_RECORD": str(record)}, path_prepend=str(stubbin))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(f"POSTED: {issue_url}", r.stdout)

            argv = record.read_text(encoding="utf-8").splitlines()
            self.assertIn("-R", argv)
            self.assertIn(REPO_SLUG, argv)
            self.assertIn("--title", argv)
            self.assertIn("[ask] Draft title here", argv)
            self.assertIn("--body-file", argv)
            body_file_idx = argv.index("--body-file") + 1
            self.assertTrue(Path(argv[body_file_idx]).is_file())

    def test_gh_failure_after_auth_prints_failed_and_open_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            draft = Path(td) / "draft.md"
            draft.write_text("Body of the report.\n", encoding="utf-8")
            stubbin = _write_stub_gh(td, STUB_GH_ISSUE_CREATE_FAILS)

            r = run_ask(["post", str(draft), "--title", "A failing post"], path_prepend=str(stubbin))
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("FAILED: some gh stderr line one", r.stdout)
            self.assertNotIn("second line", r.stdout)
            self.assertIn("OPEN: https://github.com/", r.stdout)


class PostRedactsTitleTests(unittest.TestCase):
    """A path or key typed into --title must never reach the posted issue:
    the title goes through the same redact_text as the body."""

    def test_title_is_redacted_before_posting(self):
        with tempfile.TemporaryDirectory() as td:
            draft = Path(td) / "draft.md"
            draft.write_text("Body of the report.\n", encoding="utf-8")
            record = Path(td) / "record.txt"
            issue_url = f"https://github.com/{REPO_SLUG}/issues/99"
            stubbin = _write_stub_gh(td, STUB_GH_AUTHENTICATED, issue_url=issue_url)

            secret_user = "titleprobeuser"
            key = _fake("sk-" + "live" + "-", 24)
            title = "See /Users/" + secret_user + "/notes for context " + key

            r = run_ask(["post", str(draft), "--title", title],
                        env_extra={"ASK_TEST_GH_RECORD": str(record)}, path_prepend=str(stubbin))
            self.assertEqual(r.returncode, 0, r.stderr)

            argv = record.read_text(encoding="utf-8").splitlines()
            title_idx = argv.index("--title") + 1
            recorded_title = argv[title_idx]
            self.assertNotIn(secret_user, recorded_title)
            self.assertNotIn(key, recorded_title)
            self.assertIn("[redacted]", recorded_title)
            self.assertTrue(recorded_title.startswith("[ask] "))


class UnauthenticatedFallbackTests(unittest.TestCase):
    def test_unauthenticated_stub_gives_open_url_decoding_back(self):
        with tempfile.TemporaryDirectory() as td:
            draft = Path(td) / "draft.md"
            marker = f"unique-marker-{_rand.token_hex(6)}"
            draft.write_text(f"Trying X, got Y instead. {marker}\n", encoding="utf-8")
            stubbin = _write_stub_gh(td, STUB_GH_UNAUTHENTICATED)

            r = run_ask(["post", str(draft), "--title", "Idea for a feature"], path_prepend=str(stubbin))
            self.assertEqual(r.returncode, 0, r.stderr)
            url, title, body = parse_open_url(r.stdout)
            self.assertEqual(title, "[ask] Idea for a feature")
            self.assertIn(marker, body)


class UrlLengthCapTests(unittest.TestCase):
    def test_long_body_truncated_under_cap(self):
        with tempfile.TemporaryDirectory() as td:
            draft = Path(td) / "draft.md"
            draft.write_text("word " * 4000, encoding="utf-8")
            stubbin = _write_stub_gh(td, STUB_GH_UNAUTHENTICATED)

            r = run_ask(["post", str(draft), "--title", "Huge draft"], path_prepend=str(stubbin))
            self.assertEqual(r.returncode, 0, r.stderr)
            url, title, body = parse_open_url(r.stdout)
            self.assertLessEqual(len(url), 7000)
            self.assertIn("truncat", body.lower())


class EnvFooterTests(unittest.TestCase):
    def test_env_has_no_home_path_or_username(self):
        r = run_ask(["env"])
        self.assertEqual(r.returncode, 0, r.stderr)
        user = getpass.getuser()
        self.assertNotIn(user, r.stdout)
        self.assertNotIn(str(Path.home()), r.stdout)
        self.assertNotIn("/Users/", r.stdout)
        self.assertIn("base-novacaelum", r.stdout)

    def test_env_reports_super_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            claude_dir = Path(td) / ".claude"
            claude_dir.mkdir()
            (claude_dir / "settings.json").write_text(
                json.dumps({"enabledPlugins": {"super-novacaelum@technical-cofounder": True}}),
                encoding="utf-8",
            )
            r = run_ask(["env"], cwd=td)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("super-novacaelum: enabled", r.stdout)

    def test_env_reports_super_not_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            r = run_ask(["env"], cwd=td)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("super-novacaelum: not enabled", r.stdout)

    def test_post_appends_env_footer_to_body(self):
        with tempfile.TemporaryDirectory() as td:
            draft = Path(td) / "draft.md"
            draft.write_text("The original report body.\n", encoding="utf-8")
            stubbin = _write_stub_gh(td, STUB_GH_UNAUTHENTICATED)

            r = run_ask(["post", str(draft), "--title", "Footer check"], path_prepend=str(stubbin))
            self.assertEqual(r.returncode, 0, r.stderr)
            url, title, body = parse_open_url(r.stdout)
            self.assertIn("The original report body.", body)
            self.assertIn("base-novacaelum", body)


class WhatsappLinkTests(unittest.TestCase):
    """`whatsapp-link` reads contact.json from the plugin root (CLAUDE_PLUGIN_ROOT
    overrides it, so tests use a temp copy) and prints NOT_SET or OPEN: <wa.me url>."""

    def _run(self, whatsapp, message="Hello there", raw_config=None):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "plugin"
            root.mkdir()
            (root / "contact.json").write_text(
                raw_config if raw_config is not None else json.dumps({"whatsapp": whatsapp}),
                encoding="utf-8",
            )
            msg = Path(td) / "msg.txt"
            msg.write_text(message, encoding="utf-8")
            return run_ask(["whatsapp-link", str(msg)], env_extra={"CLAUDE_PLUGIN_ROOT": str(root)})

    def test_prints_not_set_when_number_is_empty(self):
        r = self._run("")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "NOT_SET")

    def test_builds_encoded_url_with_prefix(self):
        message = "It broke: 100% of the time & \u00e9v\u00e9rything?\nSecond line"
        r = self._run("15551234567", message=message + "\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        line = r.stdout.strip()
        self.assertTrue(line.startswith("OPEN: https://wa.me/15551234567?text="), line)
        url = line[len("OPEN: "):]
        text = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["text"][0]
        self.assertEqual(text, "[Technical Cofounder] " + message)
        # nothing unencoded leaks into the query string
        raw = url.split("?text=", 1)[1]
        for ch in " &\n?%":
            if ch != "%":
                self.assertNotIn(ch, raw)

    def test_refuses_non_digit_number(self):
        for bad in ("+15551234567", "1555 123 4567", "abc12345678", "1234567", "1" * 16):
            r = self._run(bad)
            self.assertEqual(r.returncode, 1, (bad, r.stdout, r.stderr))
            self.assertNotIn("OPEN:", r.stdout)
            self.assertIn("FAILED:", r.stdout)

    def test_refuses_non_string_number_or_bad_config(self):
        for raw in (json.dumps({"whatsapp": 15551234567}), "not json", json.dumps({})):
            r = self._run(None, raw_config=raw)
            self.assertEqual(r.returncode, 1, (raw, r.stdout, r.stderr))
            self.assertIn("FAILED:", r.stdout)

    def test_refuses_empty_message(self):
        r = self._run("15551234567", message="  \n")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("FAILED:", r.stdout)

    def test_shipped_contact_json_is_valid(self):
        cfg = json.loads((PLUGIN_ROOT / "contact.json").read_text(encoding="utf-8"))
        self.assertEqual(list(cfg), ["whatsapp"])
        self.assertRegex(cfg["whatsapp"], r"^(\d{8,15})?$")


class ContactWiringTests(unittest.TestCase):
    def test_command_renamed_and_skill_replaced(self):
        cmds = PLUGIN_ROOT / "commands"
        self.assertTrue((cmds / "contact.md").is_file())
        self.assertFalse((cmds / "ask.md").exists())
        self.assertIn("contact-nova-caelum", (cmds / "contact.md").read_text(encoding="utf-8"))
        skills = PLUGIN_ROOT / "skills"
        self.assertTrue((skills / "contact-nova-caelum" / "SKILL.md").is_file())
        self.assertFalse((skills / ("ask" + "-nova-caelum")).exists())

    def test_skill_uses_the_subcommand_not_a_placeholder(self):
        text = (PLUGIN_ROOT / "skills" / "contact-nova-caelum" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: contact-nova-caelum", text)
        self.assertIn("whatsapp-link", text)
        self.assertNotIn("<WHATSAPP_NUMBER>", text)
        self.assertNotIn("python3 -c", text)
        self.assertIn("Messaging the founder directly is being set up. For now you can leave a note on GitHub",
                      " ".join(text.split()))

    def test_no_stale_ask_references_remain(self):
        stale = ("ask" + "-nova-caelum", "base-novacaelum" + ":ask")
        skip = {".git", "__pycache__"}
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file() or skip & set(path.parts) or path == Path(__file__).resolve():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for needle in stale:
                self.assertNotIn(needle, text, f"{needle!r} still in {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    unittest.main()
