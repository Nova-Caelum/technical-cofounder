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
MCP_DIR = REPO_ROOT / "plugins" / "base-novacaelum" / "mcp"
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
            bufsize=1,
        )

    def send(self, message):
        self.proc.stdin.write(json.dumps(message) + "\n")
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

    def test_tools_list_names_all_four_tools(self):
        self.session.send({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        resp = self.session.recv()
        names = {t["name"] for t in resp["result"]["tools"]}
        self.assertEqual(names, {"worklog_append", "worklog_recent", "worklog_search", "verify"})

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

    def test_tools_call_verify_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.txt").write_text("x", encoding="utf-8")
            criteria_path = tmp_path / "criteria.json"
            criteria_path.write_text(
                json.dumps(
                    {
                        "id": "rt",
                        "criteria": [
                            {"statement": "exists", "verification": {"kind": "file_state", "path": "a.txt", "assertion": "exists"}}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.session.send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "verify", "arguments": {"criteria_file": str(criteria_path), "root": tmp}},
                }
            )
            resp = self.session.recv()
            self.assertFalse(resp["result"]["isError"])
            verdict = json.loads(resp["result"]["content"][0]["text"])
            self.assertEqual(verdict["overall"], "pass")


if __name__ == "__main__":
    unittest.main()
