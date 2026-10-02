"""Unit tests for worklog.py and the JSON-RPC server (server.py).
Standard library only.
"""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_DIR = REPO_ROOT / "plugins" / "technical-cofounder" / "mcp"
SERVER_PATH = MCP_DIR / "server.py"
sys.path.insert(0, str(MCP_DIR))

import worklog  # noqa: E402


class WorklogAppendTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_append_writes_markdown_and_csv_row(self):
        result = worklog.append(self.root, "first entry", detail="body text", author="agent", tags=["a", "b"])
        entry_path = Path(result["file"])
        self.assertTrue(entry_path.is_file())
        self.assertIsNone(result["csv_error"])
        self.assertIn("body text", entry_path.read_text(encoding="utf-8"))

        csv_path = self.root / "worklog" / "worklog.csv"
        self.assertTrue(csv_path.is_file())
        with csv_path.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["summary"], "first entry")
        self.assertEqual(rows[0]["tags"], "a;b")

    def test_append_rejects_summary_over_280_chars(self):
        with self.assertRaises(ValueError):
            worklog.append(self.root, "x" * 281)

    def test_append_survives_csv_regeneration_failure(self):
        with mock.patch("worklog._regenerate_csv", side_effect=RuntimeError("disk full")):
            result = worklog.append(self.root, "still written")
        self.assertTrue(Path(result["file"]).is_file())
        self.assertEqual(result["csv_error"], "disk full")

    def test_recent_returns_newest_first(self):
        worklog.append(self.root, "one")
        worklog.append(self.root, "two")
        worklog.append(self.root, "three")
        entries = worklog.recent(self.root, n=2)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["summary"], "three")
        self.assertEqual(entries[1]["summary"], "two")

    def test_search_matches_summary_and_tags(self):
        worklog.append(self.root, "fix the widget", tags=["bugfix"])
        worklog.append(self.root, "unrelated entry", tags=["chore"])
        by_summary = worklog.search(self.root, "widget")
        by_tag = worklog.search(self.root, "bugfix")
        self.assertEqual(len(by_summary), 1)
        self.assertEqual(len(by_tag), 1)
        self.assertEqual(worklog.search(self.root, "nonexistent"), [])

    def test_recent_and_search_on_empty_worklog(self):
        self.assertEqual(worklog.recent(self.root), [])
        self.assertEqual(worklog.search(self.root, "anything"), [])

    def test_append_never_clobbers_a_same_second_same_slug_entry(self):
        first = worklog.append(self.root, "same summary")
        second = worklog.append(self.root, "same summary")
        self.assertNotEqual(first["file"], second["file"])
        self.assertTrue(Path(first["file"]).is_file())
        self.assertTrue(Path(second["file"]).is_file())
        entries = list((self.root / "worklog" / "entries").glob("*.md"))
        self.assertEqual(len(entries), 2)


class _StdioSession:
    def __init__(self):
        self.proc = subprocess.Popen(
            ["python3", str(SERVER_PATH)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

    def send(self, message):
        # Raw UTF-8, as Claude Code writes it (json.dumps would escape it to ASCII).
        self.proc.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def recv(self):
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("server closed stdout: " + self.proc.stderr.read())
        return json.loads(line)

    def close(self):
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except Exception:
                pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


class ServerProtocolTests(unittest.TestCase):
    def setUp(self):
        self.session = _StdioSession()

    def tearDown(self):
        self.session.close()

    def test_initialize_echoes_protocol_version_and_server_info(self):
        self.session.send(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2026-06-18"}}
        )
        resp = self.session.recv()
        self.assertEqual(resp["id"], 1)
        result = resp["result"]
        self.assertEqual(result["protocolVersion"], "2026-06-18")
        self.assertEqual(result["capabilities"], {"tools": {}})
        self.assertEqual(result["serverInfo"], {"name": "cofounder", "version": "0.1.0"})

    def test_notifications_initialized_gets_no_reply(self):
        self.session.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "x"}})
        self.session.recv()
        self.session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.session.send({"jsonrpc": "2.0", "id": 2, "method": "ping"})
        resp = self.session.recv()
        self.assertEqual(resp["id"], 2)

    def test_tools_list_names_the_three_worklog_tools(self):
        self.session.send({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        resp = self.session.recv()
        names = {t["name"] for t in resp["result"]["tools"]}
        self.assertEqual(names, {"worklog_append", "worklog_recent", "worklog_search"})

    def test_unknown_method_returns_method_not_found(self):
        self.session.send({"jsonrpc": "2.0", "id": 1, "method": "not/a/method"})
        resp = self.session.recv()
        self.assertEqual(resp["error"]["code"], -32601)

    def test_non_object_message_is_invalid_request_not_a_crash(self):
        self.session.proc.stdin.write(json.dumps([1, 2, 3]) + "\n")
        self.session.proc.stdin.flush()
        resp = self.session.recv()
        self.assertEqual(resp["error"]["code"], -32600)
        # the server must still be alive and responsive after a malformed message
        self.session.send({"jsonrpc": "2.0", "id": 9, "method": "ping"})
        follow_up = self.session.recv()
        self.assertEqual(follow_up["id"], 9)

    def test_tools_call_worklog_append_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.session.send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "worklog_append", "arguments": {"summary": "round trip", "root": tmp}},
                }
            )
            resp = self.session.recv()
            self.assertFalse(resp["result"]["isError"])
            entries = list((Path(tmp) / "worklog" / "entries").glob("*.md"))
            self.assertEqual(len(entries), 1)
            self.assertTrue((Path(tmp) / "worklog" / "worklog.csv").is_file())

    def test_non_ascii_text_round_trips_over_stdio(self):
        # Windows pipes default to the ANSI code page (cp1252), which has no arrow,
        # check mark or omega; Claude Code writes UTF-8.
        text = "Café → ✓ Ω"
        with tempfile.TemporaryDirectory() as tmp:
            for msg_id, name, arguments in (
                (1, "worklog_append", {"summary": text, "root": tmp}),
                (2, "worklog_recent", {"n": 1, "root": tmp}),
            ):
                self.session.send(
                    {"jsonrpc": "2.0", "id": msg_id, "method": "tools/call", "params": {"name": name, "arguments": arguments}}
                )
                result = self.session.recv()["result"]
                self.assertFalse(result["isError"], result)
            self.assertEqual(json.loads(result["content"][0]["text"])[0]["summary"], text)

    def test_tools_call_missing_required_argument_is_isError(self):
        self.session.send(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "worklog_search", "arguments": {}}}
        )
        resp = self.session.recv()
        self.assertTrue(resp["result"]["isError"])
        # the server must still be alive and responsive after a bad call
        self.session.send({"jsonrpc": "2.0", "id": 2, "method": "ping"})
        follow_up = self.session.recv()
        self.assertEqual(follow_up["id"], 2)

    def test_tools_call_unknown_tool_is_isError(self):
        self.session.send(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "does_not_exist", "arguments": {}}}
        )
        resp = self.session.recv()
        self.assertTrue(resp["result"]["isError"])


sys.path.insert(0, str(REPO_ROOT))
from tests.test_he_bridge import APPEND_OK, NO_STORE, RECENT_OK, FakeHE  # noqa: E402


class HyperspaceAdapterTests(unittest.TestCase):
    """With Hyperspace Engine holding the worklog, the worklog tools go through
    its CLI (stubbed by FakeHE), fail loud, and never write markdown."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.session = _StdioSession()

    def tearDown(self):
        self.session.close()
        self._tmp.cleanup()

    def call(self, name, arguments):
        self.session.send({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": {**arguments, "root": str(self.root)}}})
        result = self.session.recv()["result"]
        return result["isError"], result["content"][0]["text"]

    def markdown(self):
        return sorted((self.root / "worklog").rglob("*")) if (self.root / "worklog").exists() else []

    def test_append_goes_through_the_cli_not_markdown(self):
        fake = FakeHE(self.root, owner="technical-cofounder")
        fake.respond("append", APPEND_OK)
        is_error, text = self.call("worklog_append", {"summary": "Shipped the worklog CLI.", "tags": ["a"]})
        self.assertFalse(is_error, text)
        self.assertEqual(json.loads(text)["row_id"], "55b3ae00-6664-4a10-a086-e33404c46b1a")
        self.assertEqual(fake.calls()[0][3], "append")
        self.assertEqual(self.markdown(), [])

    def test_he_owned_preload_still_uses_the_store(self):
        fake = FakeHE(self.root, owner="hyperspace-engine")
        fake.respond("recent", RECENT_OK)
        is_error, text = self.call("worklog_recent", {"n": 1})
        self.assertFalse(is_error, text)
        self.assertEqual(json.loads(text)[0]["summary"], "Shipped the worklog CLI.")

    def test_search_goes_through_the_cli(self):
        fake = FakeHE(self.root, owner="technical-cofounder")
        fake.respond("search", RECENT_OK)
        is_error, text = self.call("worklog_search", {"query": "hsp-v0.1.2"})
        self.assertFalse(is_error, text)
        self.assertEqual(len(json.loads(text)), 1)

    def test_missing_cli_is_isError_with_a_fix_and_no_markdown(self):
        fake = FakeHE(self.root, owner="technical-cofounder")
        fake.python.unlink()
        for name, arguments in (("worklog_append", {"summary": "x"}), ("worklog_recent", {}),
                                ("worklog_search", {"query": "x"})):
            with self.subTest(tool=name):
                is_error, text = self.call(name, arguments)
                self.assertTrue(is_error)
                self.assertIn('Fix: run /technical-cofounder-setup:start (or say "set up hyperspace")', text)
                self.assertNotIn("hyperspace-setup", text)
        self.assertEqual(self.markdown(), [])

    def test_cli_error_is_isError_and_no_markdown(self):
        fake = FakeHE(self.root, owner="technical-cofounder")
        fake.respond("append", NO_STORE, 3)
        is_error, text = self.call("worklog_append", {"summary": "x"})
        self.assertTrue(is_error)
        self.assertIn("exit 3", text)
        self.assertEqual(self.markdown(), [])

    def test_before_the_handshake_the_markdown_path_is_unchanged(self):
        fake = FakeHE(self.root)
        is_error, text = self.call("worklog_append", {"summary": "pending entry"})
        self.assertFalse(is_error, text)
        self.assertTrue(Path(json.loads(text)["file"]).is_file())
        self.assertEqual(fake.calls(), [])


if __name__ == "__main__":
    unittest.main()
