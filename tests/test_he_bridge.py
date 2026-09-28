"""Unit tests for bin/he_bridge.py: Technical Cofounder's side of running on
Hyperspace Engine's worklog store.

The hyperspace CLI is stubbed: FakeHE builds a project with an empty
.hyperspace/graph.db, a config.toml, and a fake .hyperspace/env/bin/python that
logs its argv and replays one canned JSON body (and exit code) per verb. The
canned bodies below are copied from HE's CLI contract (pasted there from real
runs), except where a comment says otherwise. Standard library only.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
import venv
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_ROOT / "plugins" / "base-novacaelum" / "bin"
MCP_DIR = REPO_ROOT / "plugins" / "base-novacaelum" / "mcp"
sys.path.insert(0, str(BIN_DIR))
sys.path.insert(1, str(MCP_DIR))

import he_bridge  # noqa: E402
import worklog  # noqa: E402

try:
    import tomllib
except ImportError:  # Python < 3.11: the bridge must not need it; the parse assertions skip
    tomllib = None

HE_CONFIG = 'judge = "none"\nport = 8791\nuser = "user"\n'

# ── canned bodies, verbatim from the contract ─────────────────────────────
ROW_ID = "55b3ae00-6664-4a10-a086-e33404c46b1a"
APPEND_OK = (
    '{"ok": true, "entry": {"id": "55b3ae00-6664-4a10-a086-e33404c46b1a", "created_at": '
    '"2026-09-27T19:14:18.551522+00:00", "author": "engineer", "project": "workspace", "summary": '
    '"Shipped the worklog CLI.", "detailed": "Full detail body for the contract doc.", "tags": '
    '["hsp-v0.1.2", "worklog"], "work_item_id": null}}'
)
RECENT_OK = (
    '{"ok": true, "entries": [{"id": "55b3ae00-6664-4a10-a086-e33404c46b1a", "author": "engineer", '
    '"project": "workspace", "summary": "Shipped the worklog CLI.", "detailed": "Full detail body for '
    'the contract doc.", "tags": ["hsp-v0.1.2", "worklog"], "client": null, "surface": null, '
    '"work_item_id": null, "created_at": "2026-09-27T19:14:18.551522+00:00", "source_file": null}]}'
)
EMPTY_ENTRIES = '{"ok": true, "entries": []}'
IMPORT_FIRST = '{"ok": true, "imported": 2, "skipped": 0}'
MIRROR_REBUILT = '{"ok": true, "rendered": 1, "skipped": 3}'
SUMMARY_TOO_LONG = '{"ok": false, "error": "summary exceeds 280 characters (got 281)"}'
UNKNOWN_WORK_ITEM = '{"ok": false, "error": "no such work item: \'nope\'"}'
USAGE_ERROR = '{"ok": false, "error": "usage error \\u2014 see stderr"}'
MISSING_DIR = '{"ok": false, "error": "no such directory: <project>/no/such/dir"}'
# Exit 3: the contract states the shape only; this body is from a real run of
# the v0.1.2 CLI against a directory with no store (path shortened).
NO_STORE = '{"ok": false, "error": "no /tmp/x/.hyperspace/graph.db \\u2014 run `hyperspace init` first"}'
# Exit 1: the contract names the case ("something broke, read error") without a
# pasted body; this one is constructed in the contract's {"ok": false, "error"} shape.
UNEXPECTED = '{"ok": false, "error": "OperationalError: database is locked"}'

FAKE_PYTHON = """#!/usr/bin/env python3
import json, sys
from pathlib import Path
here = Path(__file__).resolve().parent
verb = sys.argv[4]
with open(here / "calls.jsonl", "a", encoding="utf-8") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\\n")
body = here / (verb + ".json")
sys.stdout.write(body.read_text(encoding="utf-8") if body.exists() else '{"ok": false, "error": "no canned body"}')
code = here / (verb + ".exit")
sys.exit(int(code.read_text()) if code.exists() else 0)
"""

# The same fake as a module, for Windows: run as `python -m hyperspace.cli`, it
# logs the argv FAKE_PYTHON would have seen and reads env/bin like it does.
FAKE_CLI_MODULE = FAKE_PYTHON.replace("#!/usr/bin/env python3\n", "").replace(
    "here = Path(__file__).resolve().parent\nverb = sys.argv[4]\n",
    "here = Path(sys.prefix) / 'bin'\nsys.argv[1:1] = ['-m', 'hyperspace.cli']\nverb = sys.argv[4]\n",
)


class FakeHE:
    """A project that looks HE-provisioned, with a scripted CLI."""

    def __init__(self, root, owner=None, config=HE_CONFIG, view=None, entries=0):
        self.root = Path(root)
        hs = self.root / ".hyperspace"
        self.bin = hs / "env" / "bin"
        self.bin.mkdir(parents=True)
        (hs / "graph.db").write_bytes(b"")
        if owner is not None:
            config += f'worklog_owner = "{owner}"\n'
        self.config_path = hs / "config.toml"
        self.config_path.write_text(config, encoding="utf-8")
        if os.name == "nt":
            self.python = self._windows_env(hs / "env")
        else:
            self.python = self.bin / "python"
            self.python.write_text(FAKE_PYTHON, encoding="utf-8")
            self.python.chmod(self.python.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        if view is not None:
            record = self.root / "core_text" / "setup.json"
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(json.dumps({"schema_version": 1, "steps": {}, "choices": {"worklog_view": view}}))
        for i in range(entries):
            entry = self.root / "worklog" / "entries" / f"2026090{i + 1}T120000Z-entry-{i}.md"
            entry.parent.mkdir(parents=True, exist_ok=True)
            entry.write_text(f'---\ndate: 2026-09-0{i + 1}T12:00:00Z\nauthor: "a"\nsummary: "e{i}"\ntags: []\n---\n')

    @staticmethod
    def _windows_env(env):
        """Windows cannot exec a script, so the fake CLI is a real venv whose
        Scripts/python.exe runs `-m hyperspace.cli` from a stub package; env/bin
        only holds the canned bodies and the call log."""
        venv.create(env, with_pip=False)
        package = env / "Lib" / "site-packages" / "hyperspace"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "cli.py").write_text(FAKE_CLI_MODULE, encoding="utf-8")
        return env / "Scripts" / "python.exe"

    def respond(self, verb, body, exit_code=0):
        (self.bin / f"{verb}.json").write_text(body, encoding="utf-8")
        (self.bin / f"{verb}.exit").write_text(str(exit_code), encoding="utf-8")

    def calls(self):
        log = self.bin / "calls.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    def config(self):
        return self.config_path.read_text(encoding="utf-8")


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class ConfigDetectionTests(_Tmp):
    def test_no_store_is_tc_alone(self):
        self.assertEqual(he_bridge.mode(self.root), "tc")
        self.assertFalse(he_bridge.uses_store(self.root))

    def test_config_without_store_is_tc_alone(self):
        (self.root / ".hyperspace").mkdir()
        (self.root / ".hyperspace" / "config.toml").write_text(HE_CONFIG + 'worklog_owner = "technical-cofounder"\n')
        self.assertEqual(he_bridge.mode(self.root), "tc")

    def test_store_with_owner_absent_is_pending(self):
        FakeHE(self.root)
        self.assertEqual(he_bridge.mode(self.root), "pending")
        self.assertFalse(he_bridge.uses_store(self.root))

    def test_owner_tc(self):
        FakeHE(self.root, owner="technical-cofounder")
        self.assertEqual(he_bridge.mode(self.root), "tc-preload")
        self.assertTrue(he_bridge.uses_store(self.root))

    def test_owner_he(self):
        FakeHE(self.root, owner="hyperspace-engine")
        self.assertEqual(he_bridge.mode(self.root), "he-preload")
        self.assertTrue(he_bridge.uses_store(self.root))

    def test_single_quotes_and_trailing_comment(self):
        FakeHE(self.root, config=HE_CONFIG + "worklog_owner = 'technical-cofounder'  # set by TC\n")
        self.assertEqual(he_bridge.mode(self.root), "tc-preload")

    def test_blank_owner_counts_as_absent(self):
        FakeHE(self.root, config=HE_CONFIG + 'worklog_owner = "  "\n')
        self.assertEqual(he_bridge.mode(self.root), "pending")

    def test_key_inside_a_table_is_not_top_level(self):
        FakeHE(self.root, config=HE_CONFIG + '[other]\nworklog_owner = "technical-cofounder"\n')
        self.assertEqual(he_bridge.mode(self.root), "pending")



class InterpreterTests(_Tmp):
    """HE's interpreter: env/bin/python on POSIX, env/Scripts/python.exe on
    Windows; each OS checks its own layout first, then the other."""

    def layout(self, *rels):
        for rel in rels:
            path = self.root / ".hyperspace" / "env" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("stub", encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return self.root / ".hyperspace" / "env"

    def on(self, os_name):
        return mock.patch.object(he_bridge, "os", SimpleNamespace(name=os_name))

    def test_windows_picks_scripts_python_exe(self):
        env = self.layout("Scripts/python.exe", "bin/python")
        with self.on("nt"):
            self.assertEqual(he_bridge.interpreter(self.root), env / "Scripts" / "python.exe")

    def test_posix_picks_bin_python(self):
        env = self.layout("Scripts/python.exe", "bin/python")
        with self.on("posix"):
            self.assertEqual(he_bridge.interpreter(self.root), env / "bin" / "python")

    def test_each_os_falls_back_to_the_other_layout(self):
        env = self.layout("Scripts/python.exe")
        with self.on("posix"):
            self.assertEqual(he_bridge.interpreter(self.root), env / "Scripts" / "python.exe")

    def test_missing_on_windows_names_the_windows_path_with_forward_slashes(self):
        FakeHE(self.root, owner="technical-cofounder").python.unlink()
        with self.on("nt"):
            self.assertIsNone(he_bridge.interpreter(self.root))
            with self.assertRaises(he_bridge.BridgeError) as ctx:
                he_bridge.recent(self.root)
        self.assertIn(".hyperspace/env/Scripts/python.exe", str(ctx.exception))
        self.assertNotIn("\\", str(ctx.exception))

class HandshakeTests(_Tmp):
    def test_obsidian_imports_writes_both_keys_and_rebuilds_the_mirror_once(self):
        fake = FakeHE(self.root, view="obsidian", entries=2)
        fake.respond("import", IMPORT_FIRST)
        fake.respond("mirror", MIRROR_REBUILT)
        self.assertIsNone(he_bridge.handshake(self.root))
        config = fake.config()
        self.assertTrue(config.startswith(HE_CONFIG), config)
        self.assertIn('worklog_owner = "technical-cofounder"\n', config)
        self.assertIn('worklog_mirror_dir = "worklog/entries"\n', config)
        calls = fake.calls()
        self.assertEqual([c[3] for c in calls], ["import", "mirror"])
        self.assertIn("--from=worklog/entries", calls[0])
        self.assertIn("--rebuild", calls[1])
        for call in calls:
            self.assertIn(f"--dir={self.root}", call)
            self.assertIn("--json", call)
        self.assertEqual(he_bridge.mode(self.root), "tc-preload")

        self.assertIsNone(he_bridge.handshake(self.root))
        self.assertEqual(fake.config(), config, "second run must leave the keys unchanged")
        self.assertEqual(len(fake.calls()), 2, "second run must not import or rebuild again")

    def test_a_failed_rebuild_is_one_note_naming_the_command_and_never_reimports(self):
        """The import must never run again once the mirror can have rendered
        into worklog/entries: HE's import keys on filename only, so it would
        take HE's own mirror files for new entries. Both keys land after the
        one import; a failed rebuild is reported, not retried."""
        fake = FakeHE(self.root, view="obsidian", entries=1)
        fake.respond("import", IMPORT_FIRST)
        fake.respond("mirror", MIRROR_REBUILT, 1)
        note = he_bridge.handshake(self.root)
        self.assertNotIn("\n", note)
        self.assertIn("hyperspace worklog mirror --rebuild", note)
        self.assertIn("worklog_owner", fake.config())
        self.assertIn("worklog_mirror_dir", fake.config())
        self.assertIsNone(he_bridge.handshake(self.root))
        self.assertEqual([c[3] for c in fake.calls()], ["import", "mirror"])

    @unittest.skipIf(tomllib is None, "tomllib needs Python 3.11+")
    def test_written_config_parses_and_keeps_he_keys(self):
        fake = FakeHE(self.root, view="obsidian", entries=1)
        fake.respond("import", IMPORT_FIRST)
        fake.respond("mirror", MIRROR_REBUILT)
        he_bridge.handshake(self.root)
        data = tomllib.loads(fake.config())
        self.assertEqual(data, {"judge": "none", "port": 8791, "user": "user",
                                "worklog_owner": "technical-cofounder", "worklog_mirror_dir": "worklog/entries"})

    def test_csv_writes_owner_only_and_never_rebuilds(self):
        fake = FakeHE(self.root, view="csv", entries=1)
        fake.respond("import", IMPORT_FIRST)
        he_bridge.handshake(self.root)
        self.assertIn("worklog_owner", fake.config())
        self.assertNotIn("worklog_mirror_dir", fake.config())
        self.assertEqual([c[3] for c in fake.calls()], ["import"])

    def test_no_setup_record_writes_owner_only(self):
        fake = FakeHE(self.root, entries=1)
        fake.respond("import", IMPORT_FIRST)
        he_bridge.handshake(self.root)
        self.assertIn("worklog_owner", fake.config())
        self.assertNotIn("worklog_mirror_dir", fake.config())

    def test_no_entries_folder_skips_the_import_but_still_rebuilds(self):
        fake = FakeHE(self.root, view="obsidian")
        fake.respond("mirror", MIRROR_REBUILT)
        self.assertIsNone(he_bridge.handshake(self.root))
        self.assertEqual([c[3] for c in fake.calls()], ["mirror"])
        self.assertIn("worklog_owner", fake.config())

    def test_owner_already_set_does_nothing(self):
        fake = FakeHE(self.root, owner="hyperspace-engine", view="obsidian", entries=2)
        before = fake.config()
        self.assertIsNone(he_bridge.handshake(self.root))
        self.assertEqual(fake.config(), before)
        self.assertEqual(fake.calls(), [])

    def test_failed_import_writes_no_keys_and_retries_next_time(self):
        fake = FakeHE(self.root, view="obsidian", entries=2)
        fake.respond("import", NO_STORE, 3)
        note = he_bridge.handshake(self.root)
        self.assertIsInstance(note, str)
        self.assertNotIn("\n", note)
        self.assertIn("exit 3", note)
        self.assertEqual(fake.config(), HE_CONFIG)
        fake.respond("import", IMPORT_FIRST)
        fake.respond("mirror", MIRROR_REBUILT)
        self.assertIsNone(he_bridge.handshake(self.root))
        self.assertEqual([c[3] for c in fake.calls()], ["import", "import", "mirror"])
        self.assertIn("worklog_owner", fake.config())

    def test_missing_cli_is_a_one_line_note(self):
        fake = FakeHE(self.root, view="obsidian", entries=1)
        fake.python.unlink()
        note = he_bridge.handshake(self.root)
        self.assertIsInstance(note, str)
        self.assertNotIn("\n", note)
        self.assertEqual(fake.config(), HE_CONFIG)

    def test_tc_alone_is_untouched(self):
        self.assertIsNone(he_bridge.handshake(self.root))
        self.assertFalse((self.root / ".hyperspace").exists())


class TomlAppendTests(_Tmp):
    def test_keys_go_before_the_first_table(self):
        config = HE_CONFIG + "\n[extra]\nk = 1\n"
        fake = FakeHE(self.root, config=config, view="obsidian")
        fake.respond("mirror", MIRROR_REBUILT)
        he_bridge.handshake(self.root)
        text = fake.config()
        self.assertTrue(text.startswith(HE_CONFIG))
        self.assertLess(text.index("worklog_owner"), text.index("[extra]"))
        self.assertTrue(text.endswith("[extra]\nk = 1\n"))
        if tomllib is not None:
            data = tomllib.loads(text)
            self.assertEqual(data["worklog_owner"], "technical-cofounder")
            self.assertEqual(data["extra"], {"k": 1})

    def test_file_without_trailing_newline(self):
        fake = FakeHE(self.root, config='judge = "none"', view="csv")
        he_bridge.handshake(self.root)
        self.assertEqual(fake.config(), 'judge = "none"\nworklog_owner = "technical-cofounder"\n')

    def test_existing_mirror_key_is_never_duplicated(self):
        fake = FakeHE(self.root, config=HE_CONFIG + 'worklog_mirror_dir = "notes/log"\n', view="obsidian")
        fake.respond("mirror", MIRROR_REBUILT)
        he_bridge.handshake(self.root)
        self.assertEqual(fake.config().count("worklog_mirror_dir"), 1)
        if tomllib is not None:
            self.assertEqual(tomllib.loads(fake.config())["worklog_mirror_dir"], "notes/log")


class ResponseMappingTests(_Tmp):
    def setUp(self):
        super().setUp()
        self.fake = FakeHE(self.root, owner="technical-cofounder")

    def test_append_arguments_and_result(self):
        self.fake.respond("append", APPEND_OK)
        result = he_bridge.append(self.root, "Shipped the worklog CLI.", detail="Full detail body for the contract doc.",
                                  author="engineer", tags=["hsp-v0.1.2", "worklog"])
        self.assertEqual(result, {"file": None, "csv_error": None, "row_id": ROW_ID})
        argv = self.fake.calls()[0]
        self.assertEqual(argv[:4], ["-m", "hyperspace.cli", "worklog", "append"])
        for arg in ("--author=engineer", "--summary=Shipped the worklog CLI.",
                    "--detail=Full detail body for the contract doc.", "--tags=hsp-v0.1.2,worklog",
                    f"--dir={self.root}", "--json"):
            self.assertIn(arg, argv)
        self.assertFalse([a for a in argv if a.startswith("--project")], "append must omit --project")

    def test_append_without_detail_or_tags_sends_neither(self):
        self.fake.respond("append", APPEND_OK)
        he_bridge.append(self.root, "x")
        argv = self.fake.calls()[0]
        self.assertFalse([a for a in argv if a.startswith(("--detail", "--tags"))])
        self.assertIn("--author=agent", argv)

    def test_summary_that_looks_like_a_flag_stays_one_argument(self):
        self.fake.respond("append", APPEND_OK)
        he_bridge.append(self.root, "--not-a-flag")
        self.assertIn("--summary=--not-a-flag", self.fake.calls()[0])

    def test_file_is_none_even_when_a_mirror_file_exists(self):
        mirror = self.root / "worklog" / "entries" / "20260927T191418Z-shipped-the-worklog-cli-55b3ae00.md"
        mirror.parent.mkdir(parents=True)
        mirror.write_text("---\n---\n")
        self.fake.respond("append", APPEND_OK)
        self.assertIsNone(he_bridge.append(self.root, "Shipped the worklog CLI.")["file"])

    def test_recent_maps_rows_to_the_tc_shape(self):
        self.fake.respond("recent", RECENT_OK)
        entries = he_bridge.recent(self.root, n=5)
        self.assertEqual(entries, [{
            "date": "2026-09-27T19:14:18Z", "author": "engineer", "summary": "Shipped the worklog CLI.",
            "tags": ["hsp-v0.1.2", "worklog"], "body": "Full detail body for the contract doc.",
            "file": None, "row_id": ROW_ID,
        }])
        self.assertIn("--limit=5", self.fake.calls()[0])
        self.assertEqual(set(entries[0]) - {"row_id"}, {"date", "author", "summary", "tags", "body", "file"})

    def test_imported_row_maps_like_any_other(self):
        row = json.loads(RECENT_OK)["entries"][0]
        row.update(source_file="20260901T120000Z-first.md", detailed=None)
        self.fake.respond("recent", json.dumps({"ok": True, "entries": [row]}))
        entry = he_bridge.recent(self.root)[0]
        self.assertIsNone(entry["file"])
        self.assertEqual(entry["body"], "")

    def test_empty_read(self):
        self.fake.respond("recent", EMPTY_ENTRIES)
        self.assertEqual(he_bridge.recent(self.root), [])

    def test_search_matches_like_tc_does(self):
        rows = json.loads(RECENT_OK)["entries"]
        other = dict(rows[0], id="0840fd76-0c31-4e70-b9a2-2f44fba1eecf", summary="unrelated", detailed=None,
                     tags=["chore"], author="someone")
        self.fake.respond("search", json.dumps({"ok": True, "entries": [rows[0], other]}))
        for query, expected in (("WORKLOG CLI", ["Shipped the worklog CLI."]), ("contract doc", ["Shipped the worklog CLI."]),
                                ("hsp-v0.1.2", ["Shipped the worklog CLI."]), ("someone", ["unrelated"]),
                                ("nonexistent-xyz", [])):
            with self.subTest(query=query):
                self.assertEqual([e["summary"] for e in he_bridge.search(self.root, query)], expected)
        self.assertEqual(self.fake.calls()[0][:4], ["-m", "hyperspace.cli", "worklog", "search"])

    def test_summary_limit_matches_tc_and_is_checked_before_the_cli(self):
        self.assertEqual(he_bridge.SUMMARY_MAX, worklog.MAX_SUMMARY_LEN)
        self.assertEqual(he_bridge.SUMMARY_MAX, 280)
        with self.assertRaises(ValueError):
            he_bridge.append(self.root, "x" * 281)
        self.assertEqual(self.fake.calls(), [])
        self.fake.respond("append", APPEND_OK)
        he_bridge.append(self.root, "x" * 280)
        self.assertEqual(len(self.fake.calls()), 1)

    def test_cli_side_summary_refusal_is_loud(self):
        self.fake.respond("append", SUMMARY_TOO_LONG, 2)
        with self.assertRaisesRegex(he_bridge.BridgeError, "summary exceeds 280 characters"):
            he_bridge.append(self.root, "short enough here")

    def test_a_comma_in_a_tag_is_refused(self):
        with self.assertRaises(ValueError):
            he_bridge.append(self.root, "x", tags=["a,b"])
        self.assertEqual(self.fake.calls(), [])

    def test_every_nonzero_exit_is_a_loud_error_naming_a_fix(self):
        cases = [("append", UNKNOWN_WORK_ITEM, 2), ("append", USAGE_ERROR, 2), ("import", MISSING_DIR, 2),
                 ("recent", NO_STORE, 3), ("recent", UNEXPECTED, 1)]
        for verb, body, code in cases:
            with self.subTest(verb=verb, code=code):
                self.fake.respond(verb, body, code)
                with self.assertRaises(he_bridge.BridgeError) as ctx:
                    he_bridge.run_cli(self.root, verb)
                message = str(ctx.exception)
                self.assertIn(f"exit {code}", message)
                self.assertIn(json.loads(body)["error"], message)
                self.assertIn("Fix:", message)

    def test_unreadable_output_is_loud(self):
        self.fake.respond("recent", "Traceback (most recent call last):", 1)
        with self.assertRaisesRegex(he_bridge.BridgeError, "Fix:"):
            he_bridge.recent(self.root)

    def test_missing_cli_is_loud_and_names_the_fix(self):
        self.fake.python.unlink()
        with self.assertRaises(he_bridge.BridgeError) as ctx:
            he_bridge.append(self.root, "x")
        self.assertIn("hyperspace-setup", str(ctx.exception))
        self.assertIn("markdown", str(ctx.exception))
        self.assertFalse((self.root / "worklog").exists())


class PreloadTests(_Tmp):
    def test_block_heading_entries_and_gear_line(self):
        fake = FakeHE(self.root, owner="technical-cofounder")
        row = dict(json.loads(RECENT_OK)["entries"][0], detailed="d" * 2000)
        fake.respond("recent", json.dumps({"ok": True, "entries": [row]}))
        block = he_bridge.worklog_block(self.root)
        lines = block.splitlines()
        self.assertEqual(lines[0], "## Recent worklog — last 3")
        self.assertIn("Shipped the worklog CLI.", block)
        self.assertIn("--limit=3", fake.calls()[0])
        self.assertEqual(lines[-1], he_bridge.GEAR_LINE)
        self.assertIn("gear*", he_bridge.GEAR_LINE)
        self.assertLess(len(block), 1000, "a long detail is capped")

    def test_block_says_so_when_empty(self):
        fake = FakeHE(self.root, owner="technical-cofounder")
        fake.respond("recent", EMPTY_ENTRIES)
        self.assertIn("(no worklog entries yet)", he_bridge.worklog_block(self.root))

    def test_block_reports_a_cli_failure_in_one_line(self):
        fake = FakeHE(self.root, owner="technical-cofounder")
        fake.respond("recent", NO_STORE, 3)
        failures = [ln for ln in he_bridge.worklog_block(self.root).splitlines() if "unavailable" in ln]
        self.assertEqual(len(failures), 1)
        self.assertIn("exit 3", failures[0])

    def test_preload_runs_the_handshake_quietly_then_prints_the_block(self):
        fake = FakeHE(self.root, view="obsidian", entries=2)
        fake.respond("import", IMPORT_FIRST)
        fake.respond("mirror", MIRROR_REBUILT)
        fake.respond("recent", RECENT_OK)
        out = he_bridge.preload_text(self.root)
        self.assertTrue(out.startswith("## Recent worklog — last 3"), out)
        self.assertIn("worklog_owner", fake.config())

    def test_preload_prints_nothing_when_he_owns_the_preload(self):
        FakeHE(self.root, owner="hyperspace-engine")
        self.assertEqual(he_bridge.preload_text(self.root), "")

    def test_preload_after_a_failed_rebuild_is_the_note_then_the_block(self):
        fake = FakeHE(self.root, view="obsidian", entries=1)
        fake.respond("import", IMPORT_FIRST)
        fake.respond("mirror", MIRROR_REBUILT, 1)
        fake.respond("recent", RECENT_OK)
        lines = he_bridge.preload_text(self.root).splitlines()
        self.assertIn("mirror --rebuild", lines[0])
        self.assertEqual(lines[1], "## Recent worklog — last 3")

    def test_preload_after_a_failed_handshake_is_one_note_and_no_block(self):
        fake = FakeHE(self.root, view="obsidian", entries=1)
        fake.respond("import", NO_STORE, 3)
        out = he_bridge.preload_text(self.root)
        self.assertEqual(len(out.splitlines()), 1, out)
        self.assertNotIn("## Recent worklog", out)


if __name__ == "__main__":
    unittest.main()
