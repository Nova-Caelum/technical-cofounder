"""Tests for the pure parts of scripts/ci_install_walk.py: the stand-in
catalog it builds, the PATH it hands to the programs it starts, and what it
concludes from the output of the first-step script, the install script,
`claude plugin list`, the team's server and its session hook.

Nothing here starts `claude`, installs anything or touches the network. The
walk itself runs in continuous integration, on all three systems.

Standard library only.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "ci_install_walk.py"

_spec = importlib.util.spec_from_file_location("ci_install_walk", SCRIPT)
walk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(walk)

ITEMS = [
    "claude-cli", "git", "uv", "python", "jq", "network", "project-folder",
    "existing-config", "marketplace", "team-plugin", "engine-env", "obsidian",
]
RESTART_AFTER_INSTALL = (
    "Git was installed. Close Claude Code completely, open it again, and paste the same message. "
    "If you started Claude Code from a terminal window, close that window too."
)
RESTART_STALE = (
    "Git is installed, but this session started before it was. Close Claude Code completely, open it "
    "again, and paste the same message. If you started Claude Code from a terminal window, close that window too."
)


class Temp(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name).resolve()


def plan(verdicts=None):
    verdicts = verdicts or {}
    return {"command": "plan", "items": [
        {"id": item, "verdict": verdicts.get(item, "ready"), "detail": "x"} for item in ITEMS]}


def entry(plugin_id, **more):
    return dict({"id": plugin_id, "version": "0.1.0", "scope": "project", "enabled": True,
                 "installPath": "/cache/" + plugin_id.split("@")[0]}, **more)


class StandInCatalog(Temp):
    def setUp(self):
        super().setUp()
        self.catalog = walk.build_marketplace(REPO_ROOT, self.root / "marketplace")
        self.written = json.loads(
            (self.root / "marketplace" / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))

    def test_it_is_named_nova_caelum_and_lists_the_three_plugins(self):
        self.assertEqual(self.written, self.catalog)
        self.assertEqual(self.written["name"], "nova-caelum")
        self.assertEqual([p["name"] for p in self.written["plugins"]],
                         ["technical-cofounder", "technical-cofounder-setup", "hyperspace-engine"])

    def test_the_two_plugins_of_this_repository_are_copies_reached_by_a_relative_path(self):
        for name in ("technical-cofounder", "technical-cofounder-setup"):
            with self.subTest(plugin=name):
                source = next(p["source"] for p in self.written["plugins"] if p["name"] == name)
                self.assertEqual(source, "./plugins/" + name)
                copied = self.root / "marketplace" / "plugins" / name
                original = REPO_ROOT / "plugins" / name
                manifest = Path(".claude-plugin") / "plugin.json"
                self.assertEqual((copied / manifest).read_bytes(), (original / manifest).read_bytes())
        setup = self.root / "marketplace" / "plugins" / "technical-cofounder-setup" / "installer"
        for name in ("bootstrap.sh", "bootstrap.ps1", "nc_setup.py"):
            self.assertEqual((setup / name).read_bytes(),
                             (REPO_ROOT / "plugins" / "technical-cofounder-setup" / "installer" / name).read_bytes())

    def test_the_engine_is_the_pinned_release_over_https(self):
        engine = next(p["source"] for p in self.written["plugins"] if p["name"] == "hyperspace-engine")
        self.assertEqual(engine, {
            "source": "url",
            "url": "https://github.com/Nova-Caelum/hyperspace-engine.git",
            "sha": "ba35bfd90fd31ab99fcf767b20a57db3d4721c11",
        })

    def test_no_compiled_python_is_copied(self):
        self.assertEqual([p for p in (self.root / "marketplace").rglob("__pycache__")], [])
        self.assertEqual([p for p in (self.root / "marketplace").rglob("*.pyc")], [])


class TheFolderEverythingLivesIn(unittest.TestCase):
    def test_its_name_has_a_space_and_an_accent_as_a_home_folder_can(self):
        self.assertIn(" ", walk.ROOT_PREFIX.strip())
        self.assertFalse(walk.ROOT_PREFIX.isascii())


class FirstStepLastLine(unittest.TestCase):
    def test_ok_carries_the_python(self):
        out = "noise\nBOOTSTRAP=OK python=/home/me/.local/share/uv/python/cpython-3.12/bin/python3.12\n\n"
        self.assertEqual(walk.parse_bootstrap(out),
                         ("OK", "/home/me/.local/share/uv/python/cpython-3.12/bin/python3.12"))

    def test_a_windows_path_with_spaces_and_an_accent_comes_through_whole(self):
        out = "bootstrap: x\r\nBOOTSTRAP=OK python=C:/Users/me/Jos\u00e9 M/AppData/Roaming/uv/python/python.exe\r\n"
        self.assertEqual(walk.parse_bootstrap(out),
                         ("OK", "C:/Users/me/Jos\u00e9 M/AppData/Roaming/uv/python/python.exe"))

    def test_the_two_stops_carry_their_reason(self):
        self.assertEqual(walk.parse_bootstrap("BOOTSTRAP=NEEDS_RESTART reason=" + RESTART_STALE + "\n"),
                         ("NEEDS_RESTART", RESTART_STALE))
        self.assertEqual(walk.parse_bootstrap("BOOTSTRAP=NEEDS_YOU reason=Git is missing.\n"),
                         ("NEEDS_YOU", "Git is missing."))

    def test_anything_else_is_no_answer(self):
        for out in ("", "\n\n", "BOOTSTRAP=OK python=/x\nTraceback (most recent call last):\n", "BOOTSTRAP=MAYBE x=y\n"):
            with self.subTest(out=out):
                self.assertEqual(walk.parse_bootstrap(out)[0], None)


class WhichGitBranchTheFirstStepTook(unittest.TestCase):
    def test_git_on_path(self):
        out = "bootstrap: Git is already here: C:\\Program Files\\Git\\cmd\\git.exe\nBOOTSTRAP=OK python=dry-run\n"
        self.assertEqual(walk.git_branch(out), "present")

    def test_git_kept_off_path_is_used_where_it_is(self):
        out = ("bootstrap: Git is already here: C:\\Program Files\\Git\\cmd\\git.exe (not on PATH; using it directly)\n"
               "BOOTSTRAP=OK python=C:/x/python.exe\n")
        self.assertEqual(walk.git_branch(out), "used-directly")

    def test_a_session_older_than_the_install(self):
        self.assertEqual(walk.git_branch("BOOTSTRAP=NEEDS_RESTART reason=" + RESTART_STALE + "\n"), "stale-session")

    def test_the_package_manager_install(self):
        out = ("bootstrap: Installing Git because you're on Windows: it gives your team the command line its safety checks run in.\n"
               "bootstrap: running: winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements\n"
               "BOOTSTRAP=NEEDS_RESTART reason=" + RESTART_AFTER_INSTALL + "\n")
        self.assertEqual(walk.git_branch(out), "package-manager")

    def test_the_direct_download_when_the_package_manager_is_missing(self):
        out = ("bootstrap: Installing Git because you're on Windows: it gives your team the command line its safety checks run in.\n"
               "bootstrap: winget is missing; downloading the Git for Windows installer instead\n"
               "bootstrap: downloading https://github.com/git-for-windows/git/releases/download/v2/Git-2-64-bit.exe\n"
               "bootstrap: the Git installer finished (exit 0)\n"
               "BOOTSTRAP=NEEDS_RESTART reason=" + RESTART_AFTER_INSTALL + "\n")
        self.assertEqual(walk.git_branch(out), "direct-download")

    def test_the_direct_download_after_the_package_manager_failed(self):
        out = ("bootstrap: running: winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements\n"
               "bootstrap: winget did not leave a working Git (exit 1); trying the installer from GitHub\n"
               "bootstrap: the Git installer finished (exit 0)\n"
               "BOOTSTRAP=NEEDS_RESTART reason=" + RESTART_AFTER_INSTALL + "\n")
        self.assertEqual(walk.git_branch(out), "package-manager-failed-then-direct-download")

    def test_a_dry_run_only_decides(self):
        out = ("bootstrap: Installing Git because you're on Windows: it gives your team the command line its safety checks run in.\n"
               "bootstrap: would run: winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements\n"
               "BOOTSTRAP=NEEDS_RESTART reason=" + RESTART_AFTER_INSTALL + "\n")
        self.assertEqual(walk.git_branch(out), "would-install")

    def test_an_install_that_left_no_git(self):
        out = ("bootstrap: winget is missing; downloading the Git for Windows installer instead\n"
               "bootstrap: the Git installer could not be downloaded or run: rate limit\n"
               "BOOTSTRAP=NEEDS_YOU reason=Git could not be installed automatically.\n")
        self.assertEqual(walk.git_branch(out), "install-failed")


class PathWithoutGit(unittest.TestCase):
    FILES = {
        r"C:\Program Files\Git\cmd": {"git.exe"},
        r"C:\Program Files\Git\mingw64\bin": {"git.exe", "curl.exe"},
        r"C:\Program Files\Git\usr\bin": {"bash.exe", "sh.exe"},
        r"C:\Program Files\Git\bin": {"bash.exe", "git.exe"},
        r"C:\Windows\System32": {"bash.exe", "cmd.exe"},
        r"C:\Users\me\AppData\Local\Microsoft\WindowsApps": {"bash.exe", "winget.exe"},
        r"C:\npm\prefix": {"claude.cmd"},
    }

    def holds(self, folder, name):
        return name in self.FILES.get(folder, ())

    def test_every_folder_with_git_or_git_bash_goes_and_windows_own_bash_stays(self):
        path = ";".join(list(self.FILES) + [""])
        kept, removed = walk.path_without_git(path, sep=";", holds=self.holds)
        self.assertEqual(kept.split(";"), [
            r"C:\Windows\System32", r"C:\Users\me\AppData\Local\Microsoft\WindowsApps", r"C:\npm\prefix"])
        self.assertEqual(removed, [
            r"C:\Program Files\Git\cmd", r"C:\Program Files\Git\mingw64\bin",
            r"C:\Program Files\Git\usr\bin", r"C:\Program Files\Git\bin"])

    def test_a_path_with_no_git_is_left_as_it_is(self):
        kept, removed = walk.path_without_git(r"C:\Windows\System32;C:\npm\prefix", sep=";", holds=self.holds)
        self.assertEqual((kept, removed), (r"C:\Windows\System32;C:\npm\prefix", []))


class HidingJq(Temp):
    def tool(self, folder, name, text="#!/bin/sh\necho ran\n"):
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / name
        target.write_text(text)
        target.chmod(0o755)
        return target

    @unittest.skipIf(sys.platform == "win32", "folders are mirrored with links on macOS and Linux")
    def test_a_folder_that_holds_jq_is_replaced_by_one_with_everything_but_jq(self):
        shared, plain = self.root / "usr-bin", self.root / "other"
        self.tool(shared, "jq")
        self.tool(shared, "git")
        self.tool(plain, "claude")
        path = os.pathsep.join([str(shared), str(plain)])
        hidden, changed = walk.path_without_jq(path, self.root / "mirror", system="linux")
        self.assertEqual(changed, [str(shared)])
        self.assertIsNone(shutil.which("jq", path=hidden))
        self.assertNotIn(str(shared), hidden.split(os.pathsep))
        self.assertEqual(hidden.split(os.pathsep)[1], str(plain))
        git = shutil.which("git", path=hidden)
        self.assertIsNotNone(git)
        self.assertEqual(subprocess.run([git], capture_output=True, text=True).stdout, "ran\n")

    def test_on_windows_the_folder_is_left_out(self):
        choco, plain = self.root / "chocolatey" / "bin", self.root / "npm"
        self.tool(choco, "jq.exe")
        self.tool(plain, "claude.cmd")
        hidden, changed = walk.path_without_jq(";".join([str(choco), str(plain)]), self.root / "mirror",
                                               system="windows", sep=";")
        self.assertEqual((hidden, changed), (str(plain), [str(choco)]))

    def test_a_path_with_no_jq_is_left_as_it_is(self):
        plain = self.root / "npm"
        self.tool(plain, "claude")
        self.assertEqual(walk.path_without_jq(str(plain), self.root / "mirror", system="linux"), (str(plain), []))


class APathForARestartedSession(unittest.TestCase):
    def test_the_saved_path_comes_first_and_git_is_only_seen_through_it(self):
        saved = r"C:\Windows\System32;C:\Program Files\Git\cmd;C:\npm\prefix"
        current = r"C:\hostedtoolcache\Python\3.11;C:\Program Files\Git\mingw64\bin;C:\WINDOWS\system32\;C:\npm\prefix"
        fresh = walk.restarted_path(saved, current, is_git=lambda folder: "\\Git\\" in folder)
        self.assertEqual(fresh.split(";"), [
            r"C:\Windows\System32", r"C:\Program Files\Git\cmd", r"C:\npm\prefix", r"C:\hostedtoolcache\Python\3.11"])

    def test_a_saved_path_without_git_gives_a_session_without_git(self):
        fresh = walk.restarted_path(r"C:\Windows\System32", r"C:\Program Files\Git\cmd;C:\tools",
                                    is_git=lambda folder: "\\Git\\" in folder)
        self.assertEqual(fresh, r"C:\Windows\System32;C:\tools")


class SavedPathReads(unittest.TestCase):
    def test_two_reads_agree_whatever_their_letter_case_and_trailing_slashes(self):
        a = r"C:\Windows\system32;C:\Program Files\Git\cmd\;;C:\Tools"
        b = r"C:\WINDOWS\System32;C:\Program Files\Git\cmd;C:\Tools;"
        self.assertEqual(walk.path_entries(a), walk.path_entries(b))
        self.assertTrue(walk.on_path(r"c:\program files\git\CMD\\", a))
        self.assertFalse(walk.on_path(r"C:\Program Files\Git\bin", a))


class ThePlan(unittest.TestCase):
    def test_twelve_items_each_with_one_of_the_six_verdicts_is_fine(self):
        verdicts = {"jq": "install", "project-folder": "install", "git": "needs-restart",
                    "claude-cli": "upgrade", "uv": "repair", "network": "needs-you"}
        self.assertEqual(walk.plan_problems(plan(verdicts)), [])

    def test_a_missing_item_is_named(self):
        doc = plan()
        doc["items"] = [row for row in doc["items"] if row["id"] != "jq"]
        problems = walk.plan_problems(doc)
        self.assertEqual(len(problems), 1)
        self.assertIn("jq", problems[0])

    def test_a_verdict_that_is_not_one_of_the_six_is_named(self):
        problems = walk.plan_problems(plan({"uv": "fine"}))
        self.assertEqual(len(problems), 1)
        self.assertIn("uv", problems[0])
        self.assertIn("fine", problems[0])

    def test_something_that_is_not_a_plan_is_a_problem(self):
        for doc in (None, {}, {"items": "x"}, {"command": "plan", "error": "boom"}):
            with self.subTest(doc=doc):
                self.assertTrue(walk.plan_problems(doc))

    def test_what_is_not_ready(self):
        self.assertEqual(walk.not_ready(plan()), {})
        self.assertEqual(walk.not_ready(plan({"git": "needs-restart"})), {"git": "needs-restart"})
        self.assertEqual(walk.not_ready(None), {"(no document)": "missing"})


class TheSecondApply(unittest.TestCase):
    def test_which_items_were_acted_on(self):
        doc = {"results": [{"id": "jq", "acted": True, "before": "install", "after": "ready"},
                           {"id": "git", "acted": False, "before": "ready", "after": "ready"}]}
        self.assertEqual(walk.acted_on(doc), ["jq"])
        self.assertEqual(walk.acted_on({"results": [{"id": "git", "acted": False}]}), [])
        self.assertEqual(walk.acted_on(None), [])


class InstalledPlugins(unittest.TestCase):
    TEAM, ENGINE = "technical-cofounder@nova-caelum", "hyperspace-engine@nova-caelum"

    def test_both_enabled_with_no_errors_is_fine(self):
        entries = [entry(self.TEAM), entry(self.ENGINE), entry("other@x", enabled=False)]
        self.assertEqual(walk.plugin_problems(entries, [self.TEAM, self.ENGINE]), [])

    def test_missing_switched_off_and_failed_to_load_are_each_named(self):
        entries = [entry(self.TEAM, enabled=False)]
        problems = walk.plugin_problems(entries, [self.TEAM, self.ENGINE])
        self.assertEqual(len(problems), 2)
        entries = [entry(self.TEAM), entry(self.ENGINE, errors=["Dependency is not installed"])]
        problems = walk.plugin_problems(entries, [self.TEAM, self.ENGINE])
        self.assertEqual(len(problems), 1)
        self.assertIn("Dependency is not installed", problems[0])

    def test_an_answer_that_is_not_a_list_is_a_problem(self):
        self.assertTrue(walk.plugin_problems(None, [self.TEAM]))

    def test_the_install_path_of_one_plugin(self):
        entries = [entry(self.TEAM), entry("technical-cofounder-setup@nova-caelum", installPath="/cache/setup/0.1.0")]
        self.assertEqual(walk.install_path(entries, "technical-cofounder-setup@nova-caelum"), "/cache/setup/0.1.0")
        self.assertIsNone(walk.install_path(entries, self.ENGINE))
        self.assertIsNone(walk.install_path(None, self.ENGINE))


class TheTeamsServer(unittest.TestCase):
    def test_its_command_is_the_one_claude_code_would_start(self):
        listed = entry("technical-cofounder@nova-caelum", mcpServers={"caelum-dev-team": {
            "command": "${CLAUDE_PROJECT_DIR}/.hyperspace/env/bin/python",
            "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/server.py"]}})
        self.assertEqual(walk.server_command(listed, "caelum-dev-team", project="/work/p", plugin_root="/cache/team"),
                         ["/work/p/.hyperspace/env/bin/python", "/cache/team/mcp/server.py"])
        self.assertIsNone(walk.server_command(entry("x@y"), "caelum-dev-team", project="/p", plugin_root="/r"))

    def answers(self, *documents):
        return "".join(json.dumps(doc) + "\n" for doc in documents)

    def good(self, summary):
        appended = {"content": [{"type": "text", "text": json.dumps({"summary": summary})}], "isError": False}
        recent = {"content": [{"type": "text", "text": json.dumps([{"summary": "older"}, {"summary": summary}])}],
                  "isError": False}
        return [
            {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                                                 "serverInfo": {"name": "caelum-dev-team", "version": "0.1.0"}}},
            {"jsonrpc": "2.0", "id": 2, "result": appended},
            {"jsonrpc": "2.0", "id": 3, "result": recent},
        ]

    def test_a_valid_start_and_an_entry_read_back_is_fine(self):
        self.assertEqual(walk.server_problems(self.answers(*self.good("walk 1")), "walk 1"), [])

    def test_an_entry_that_does_not_come_back_is_a_problem(self):
        problems = walk.server_problems(self.answers(*self.good("walk 1")), "walk 2")
        self.assertEqual(len(problems), 1)
        self.assertIn("walk 2", problems[0])

    def test_a_tool_error_is_a_problem(self):
        docs = self.good("walk 1")
        docs[1]["result"] = {"content": [{"type": "text", "text": "the store refused"}], "isError": True}
        problems = walk.server_problems(self.answers(*docs), "walk 1")
        self.assertTrue(any("the store refused" in p for p in problems))

    def test_no_answer_to_initialize_is_a_problem(self):
        self.assertTrue(walk.server_problems("", "walk 1"))
        docs = self.good("walk 1")
        docs[0] = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Method not found"}}
        self.assertTrue(any("initialize" in p for p in walk.server_problems(self.answers(*docs), "walk 1")))

    def test_the_requests_are_initialize_then_append_then_recent(self):
        lines = [json.loads(line) for line in walk.server_requests("walk 1", "/work/p").splitlines()]
        self.assertEqual([m.get("method") for m in lines],
                         ["initialize", "notifications/initialized", "tools/call", "tools/call"])
        self.assertEqual([m.get("id") for m in lines], [1, None, 2, 3])
        self.assertEqual(lines[2]["params"]["name"], "worklog_append")
        self.assertEqual(lines[2]["params"]["arguments"]["summary"], "walk 1")
        self.assertEqual(lines[3]["params"]["name"], "worklog_recent")


class TheSessionBriefing(unittest.TestCase):
    HOOKS = {"hooks": {
        "SessionStart": [{"hooks": [{"type": "command", "command": '"${CLAUDE_PLUGIN_ROOT}"/hooks/session-preload.sh'}]}],
        "Stop": [{"hooks": [{"type": "command", "command": '"${CLAUDE_PLUGIN_ROOT}"/hooks/concision-stop.sh'},
                            {"type": "prompt", "prompt": "not a command"}]}],
    }}

    def test_the_commands_claude_code_runs_when_a_session_starts(self):
        self.assertEqual(walk.hook_commands(self.HOOKS, "SessionStart"),
                         ['"${CLAUDE_PLUGIN_ROOT}"/hooks/session-preload.sh'])
        self.assertEqual(walk.hook_commands(self.HOOKS, "Stop"), ['"${CLAUDE_PLUGIN_ROOT}"/hooks/concision-stop.sh'])
        self.assertEqual(walk.hook_commands(self.HOOKS, "PreToolUse"), [])
        self.assertEqual(walk.hook_commands(None, "SessionStart"), [])

    def test_the_team_plugin_declares_its_briefing_for_session_start(self):
        declared = json.loads((REPO_ROOT / "plugins" / "technical-cofounder" / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        commands = walk.hook_commands(declared, "SessionStart")
        self.assertEqual(len(commands), 1)
        self.assertTrue(commands[0].endswith("/hooks/session-preload.sh"))

    def test_a_health_heading_is_found_wherever_it_starts_a_line(self):
        text = "## Tech primer (live)\n\n- technical-cofounder: present\n## Health\n- jq is missing\n"
        self.assertEqual(walk.health_lines(text), ["## Health"])
        self.assertEqual(walk.health_lines("x\r\n## Health check\r\n"), ["## Health check"])

    def test_a_healthy_briefing_has_none(self):
        text = "## Tech primer (live)\n\n- technical-cofounder: present\nyour ## Health is fine\n"
        self.assertEqual(walk.health_lines(text), [])


class TheGuidesPages(unittest.TestCase):
    def test_both_pages_are_read_from_what_the_render_printed(self):
        out = "RENDERED: core_text/setup-guide.html\r\nGUIDE: C:\\p q\\core_text\\setup-guide.html\r\nEXTRAS: C:\\p q\\core_text\\setup-extras.html\r\n"
        self.assertEqual(walk.guide_paths(out), {
            "GUIDE": "C:\\p q\\core_text\\setup-guide.html", "EXTRAS": "C:\\p q\\core_text\\setup-extras.html"})

    def test_a_render_that_printed_neither_gives_neither(self):
        self.assertEqual(walk.guide_paths("usage: setup_record.py\n"), {})
        self.assertEqual(walk.guide_paths(""), {})


class WhatChanged(Temp):
    def test_added_removed_and_changed_files_are_each_named(self):
        (self.root / "kept.txt").write_text("a")
        (self.root / "gone.txt").write_text("b")
        (self.root / "sub").mkdir()
        before = walk.snapshot(self.root)
        self.assertEqual(walk.changes(before, walk.snapshot(self.root)), [])
        (self.root / "gone.txt").unlink()
        (self.root / "sub" / "new.txt").write_text("c")
        (self.root / "kept.txt").write_text("longer")
        found = walk.changes(before, walk.snapshot(self.root))
        self.assertIn("removed: gone.txt", found)
        self.assertIn("added: sub/new.txt", found)
        self.assertIn("changed: kept.txt", found)


class ThePythonTheFirstStepProved(unittest.TestCase):
    def test_new_enough_and_not_one_that_was_already_here_is_fine(self):
        self.assertEqual(walk.python_problems((3, 12, 13), "/uv/python/bin/python3.12",
                                              ["/usr/bin/python3", "/toolcache/python"]), [])

    def test_too_old_is_a_problem(self):
        self.assertTrue(walk.python_problems((3, 10, 9), "/uv/python/bin/python3.10", []))

    def test_one_that_was_already_on_this_machine_is_a_problem(self):
        problems = walk.python_problems((3, 12, 1), "/toolcache/python", ["/usr/bin/python3", "/toolcache/python"])
        self.assertEqual(len(problems), 1)


if __name__ == "__main__":
    unittest.main()
