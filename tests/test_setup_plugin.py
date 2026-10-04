"""Unit tests for the shape of plugins/technical-cofounder-setup: the front
door installed once for the whole computer. It is a skill, a command, scripts
and data: no hooks, no MCP server, no agents, no dependencies. The setup
pieces live here and nowhere in the team plugin, and the skill carries the
instructions the setup conversation depends on.

Standard library only.
"""
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SETUP = REPO_ROOT / "plugins" / "technical-cofounder-setup"
TEAM = REPO_ROOT / "plugins" / "technical-cofounder"
SKILL = SETUP / "skills" / "setup" / "SKILL.md"
MESSAGE = SETUP / "reference" / "install-message.md"
STEPS = json.loads((SETUP / "setup" / "steps.json").read_text(encoding="utf-8"))

ROOT_FALLBACK = (
    "If `${CLAUDE_PLUGIN_ROOT}` is not set, the plugin root is the folder two levels above this file; "
    "use that absolute path wherever this skill says `${CLAUDE_PLUGIN_ROOT}`."
)
TRIGGERS = (
    "set me up", "set up", "get started", "install", "onboard me", "continue setup",
    "start another project", "something is broken with my setup",
)
# One exact sentence per instruction the narration rests on.
NARRATION = (
    "Say the reason and the time before you run the step.",
    "One step at a time.",
    'The re-scan is the only source of "done".',
)
# A shell call from the agent is cut off after two minutes unless it asks for
# longer, and a cut-off call prints no last line and no JSON.
FIRST_STEP_TIMEOUT = (
    "Run it with a ten-minute timeout on the tool call.",
    "A call that ends with no `BOOTSTRAP=` last line was cut off, not failed: run the same command again.",
)
APPLY_TIMEOUT = (
    "Run every `apply` with a ten-minute timeout on the tool call.",
    "A call that ends with no JSON document was cut off, not failed: run the same command again.",
)
PATH_AS_PRINTED = "On Windows it comes with forward slashes: use it as printed, always inside double quotes."
TERMINAL_TOO = "If they started Claude Code from a terminal window, they close that window too."
PROJECTS_DEFAULT = "a folder with that name in `Projects` inside their home folder, on every system."
ONEDRIVE = (
    "If the folder they choose has `OneDrive` in its path, say once that synced folders slow the workspace down "
    "and offer the `Projects` default again; their choice stands."
)
ASK = "If anything is unclear, just ask me."
# The oldest Claude Code on which `claude plugin install technical-cofounder@nova-caelum` brings its
# dependency, Hyperspace Engine, with it. Found by running the install on 2.1.92, 2.1.109 and 2.1.110:
# the first two say "Successfully installed" and leave the engine out, 2.1.110 adds "(+ 1 dependency:
# hyperspace-engine)". The changelog entry for 2.1.110 says the same: "Fixed plugin install not honoring
# dependencies declared in plugin.json when the marketplace entry omits them".
CLAUDE_CODE_FLOOR = "2.1.110"
GUIDE_STEPS = ("editor", "obsidian", "github", "workspace", "first-steps", "profile")


def manifest(plugin):
    return json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))


def flat(text):
    return " ".join(text.split())


class Manifest(unittest.TestCase):
    def test_name_version_and_description(self):
        m = manifest(SETUP)
        self.assertEqual(m["name"], "technical-cofounder-setup")
        self.assertEqual(m["version"], "0.1.0")
        self.assertTrue(m["description"].strip())
        self.assertEqual(m["description"].strip().count(". "), 0, "one sentence")

    def test_carries_the_team_plugins_author_and_addresses(self):
        mine, team = manifest(SETUP), manifest(TEAM)
        for field in ("author", "homepage", "repository", "license"):
            with self.subTest(field=field):
                self.assertEqual(mine[field], team[field])
        self.assertEqual(mine["license"], "Apache-2.0")

    def test_depends_on_nothing(self):
        self.assertNotIn("dependencies", manifest(SETUP))

    def test_it_is_a_skill_a_command_scripts_and_data(self):
        for absent in ("hooks", "agents", ".mcp.json", "mcp", "settings.json"):
            with self.subTest(absent=absent):
                self.assertFalse((SETUP / absent).exists())
        self.assertEqual(sorted(p.name for p in (SETUP / "skills").iterdir()), ["setup"])
        self.assertEqual(sorted(p.name for p in (SETUP / "commands").iterdir()), ["start.md"])


class TheMove(unittest.TestCase):
    def test_the_setup_pieces_left_the_team_plugin(self):
        for gone in ("skills/setup", "commands/quick-start.md", "commands/onboard.md", "bin/setup_record.py",
                     "bin/init_workspace.py", "template", "reference/dependencies.md", "setup"):
            with self.subTest(gone=gone):
                self.assertFalse((TEAM / gone).exists())

    def test_and_are_in_the_setup_plugin(self):
        for here in ("skills/setup/SKILL.md", "commands/start.md", "bin/setup_record.py", "bin/init_workspace.py",
                     "template/CLAUDE.md", "reference/dependencies.md", "reference/install-message.md",
                     "setup/steps.json", "installer/nc_setup.py", "installer/bootstrap.sh", "installer/bootstrap.ps1"):
            with self.subTest(here=here):
                self.assertTrue((SETUP / here).is_file())

    def test_what_stays_in_the_team_plugin_is_still_there(self):
        for stays in ("skills/super-setup/SKILL.md", "skills/secrets-setup/SKILL.md", "skills/contact-nova-caelum/SKILL.md",
                      "reference/without-super.md", "bin/contact.py", "bin/redact.py", "bin/he_bridge.py"):
            with self.subTest(stays=stays):
                self.assertTrue((TEAM / stays).is_file())

    def test_no_shipped_file_names_a_command_that_no_longer_exists(self):
        for path in sorted((REPO_ROOT / "plugins").rglob("*")):
            if not path.is_file() or path.suffix not in (".md", ".sh", ".py", ".json", ".ps1"):
                continue
            text = path.read_text(encoding="utf-8")
            for gone in ("technical-cofounder:quick-start", "technical-cofounder:onboard"):
                with self.subTest(file=path.relative_to(REPO_ROOT).as_posix(), gone=gone):
                    self.assertNotIn(gone, text)

    def test_the_start_command_hands_over_to_the_setup_skill(self):
        text = (SETUP / "commands" / "start.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\ndescription:"))
        self.assertIn("setup skill", text)


class TheSkill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.flat = flat(cls.text)
        front = cls.text.split("---", 2)[1]
        cls.name = re.search(r"(?m)^name:\s*(.+?)\s*$", front).group(1)
        cls.description = re.search(r"(?m)^description:\s*(.+?)\s*$", front).group(1)

    def test_it_is_the_setup_skill(self):
        self.assertEqual(self.name, "setup")

    def test_the_description_names_every_trigger_phrase(self):
        for phrase in TRIGGERS:
            with self.subTest(phrase=phrase):
                self.assertIn(f'"{phrase}"', self.description.lower())

    def test_it_says_where_the_plugin_root_is_before_anything_else(self):
        head = flat(self.text.split("\n## ", 1)[0])
        self.assertIn(ROOT_FALLBACK, head)

    def test_it_carries_the_three_narration_instructions(self):
        for sentence in NARRATION:
            with self.subTest(sentence=sentence):
                self.assertIn(sentence, self.flat)

    def section(self, title):
        return flat(self.text.split("\n## %s\n" % title, 1)[1].split("\n## ", 1)[0])

    def test_the_slow_calls_get_ten_minutes_and_a_cut_off_call_is_run_again(self):
        first_step = self.section("First step")
        for sentence in FIRST_STEP_TIMEOUT:
            with self.subTest(section="First step", sentence=sentence):
                self.assertIn(sentence, first_step)
        scan = self.section("Scan, plan, apply, re-scan")
        for sentence in APPLY_TIMEOUT:
            with self.subTest(section="Scan, plan, apply, re-scan", sentence=sentence):
                self.assertIn(sentence, scan)

    def test_the_python_path_is_used_as_the_first_step_printed_it(self):
        # A backslash is an escape in Git Bash, so the path is never retyped.
        self.assertIn(PATH_AS_PRINTED, self.section("First step"))

    def test_a_restart_means_the_terminal_window_too(self):
        self.assertIn(TERMINAL_TOO, self.section("First step"))
        self.assertIn(TERMINAL_TOO, self.section("Scan, plan, apply, re-scan"))

    def test_the_project_goes_in_projects_on_every_system_and_onedrive_is_named_once(self):
        where = self.section("Where the project goes")
        self.assertIn(PROJECTS_DEFAULT, where)
        self.assertIn(ONEDRIVE, where)
        self.assertNotIn("Documents folder on Windows, or", where)

    def test_it_never_restates_a_reason_that_lives_in_steps_json(self):
        for entry in STEPS["install"]:
            for key in ("why", "why_windows"):
                if key in entry:
                    with self.subTest(item=entry["id"], key=key):
                        self.assertNotIn(entry[key], self.flat)

    def test_it_names_the_first_step_scripts_and_every_verb_it_runs(self):
        for needle in ("installer/bootstrap.sh", "installer/bootstrap.ps1", "installer/nc_setup.py",
                       "BOOTSTRAP=OK", "BOOTSTRAP=NEEDS_RESTART", "BOOTSTRAP=NEEDS_YOU",
                       "plan --project", "apply --project", "--item", "ack --project", "scan --project", "--record",
                       "bin/setup_record.py", "bin/init_workspace.py"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.text)

    def test_it_never_runs_every_item_in_one_command(self):
        self.assertNotIn("--all", self.text)

    def test_it_runs_scripts_with_the_python_the_first_step_proved(self):
        # The `python3` on PATH may be years old, or missing on Windows.
        self.assertNotIn('python3 "', self.text)
        self.assertNotIn("python3 ${", self.text)

    def test_it_names_each_guide_step_it_still_runs(self):
        for step in GUIDE_STEPS:
            with self.subTest(step=step):
                self.assertIn(f"(`{step}`)", self.text)

    def test_it_says_you_can_just_ask_early_and_at_the_end(self):
        self.assertGreaterEqual(self.flat.count(ASK), 2)
        closing = self.text.split("\n## Closing", 1)[1].split("\n## ", 1)[0]
        self.assertIn(ASK, flat(closing))
        how_to_talk = self.text.split("\n## How to talk", 1)[1].split("\n## ", 1)[0]
        self.assertIn(ASK, flat(how_to_talk))

    def test_it_never_asks_for_a_secret_or_overwrites_a_file(self):
        self.assertIn("Never ask for a key, token or password in chat.", self.flat)
        self.assertIn("Never overwrite or delete a file.", self.flat)

    def test_the_closing_gives_the_one_next_action(self):
        closing = flat(self.text.split("\n## Closing", 1)[1].split("\n## ", 1)[0])
        self.assertIn("Open Claude Code in `<absolute project path>`. Your technical cofounder will be there.", closing)
        self.assertIn("EXTRAS:", closing)

    def test_the_guide_opens_as_a_page_with_the_path_as_the_fallback(self):
        self.assertIn("You can view the setup guide here:", self.flat)
        self.assertIn("Never print the HTML in the chat.", self.flat)
        self.assertIn("about 20 minutes", self.flat)

    def test_it_no_longer_checks_tools_itself(self):
        for stale in ("python3 --version", "git --version", "~/.claude/settings.json", "Manage app execution aliases"):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, self.text)


class TheMessage(unittest.TestCase):
    """reference/install-message.md: the one message a person pastes. The
    README and the website copy it from this file."""

    @classmethod
    def setUpClass(cls):
        cls.text = MESSAGE.read_text(encoding="utf-8")
        cls.blocks = re.findall(r"(?ms)^```text\n(.*?)^```$", cls.text)

    def test_one_introduction_line_then_one_fenced_block(self):
        self.assertEqual(len(self.blocks), 1)
        self.assertEqual(self.text.count("```"), 2)
        before = [line for line in self.text.split("```text", 1)[0].splitlines() if line.strip()]
        self.assertEqual(len(before), 1)
        self.assertEqual(self.text.split("```", 2)[2].strip(), "")

    def test_the_message_is_the_agreed_one(self):
        lines = self.blocks[0].splitlines()
        self.assertEqual(lines[0], "Set up Technical Cofounder for me, from https://github.com/Nova-Caelum/plugins")
        self.assertEqual([line[:2] for line in lines if re.match(r"\d\. ", line)], ["1.", "2.", "3.", "4."])
        for needle in (
            "curl -fsSL https://claude.ai/install.sh | bash",
            "irm https://claude.ai/install.ps1 | iex",
            "   winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements",
            "   claude plugin marketplace add https://github.com/Nova-Caelum/plugins.git",
            "   claude plugin install technical-cofounder-setup@nova-caelum",
            "close Claude Code completely, open it again and paste this same message",
            "Run `claude plugin list --json`, find the installPath of technical-cofounder-setup, read skills/setup/SKILL.md "
            "inside it, and follow it from the top.",
            "Tell me what each step is for before you run it, and go one step at a time.",
            # A command line installed a moment ago is not on this session's PATH.
            "~/.local/bin/claude on macOS or Linux",
            r"%USERPROFILE%\.local\bin\claude.exe on Windows",
            # Git has to be here before the plugin that checks for it can be downloaded.
            "xcode-select --install",
            r"C:\Program Files\Git\cmd\git.exe",
            r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe",
            "https://git-scm.com/downloads/win",
            "close that window too",
        ):
            with self.subTest(needle=needle[:40]):
                self.assertIn(needle, self.blocks[0])

    def test_every_line_of_the_message_starts_where_it_was_agreed(self):
        # The Chat-tab line straight under the ask, so a paste into Chat meets
        # it first. Numbered steps at the margin; commands three spaces in,
        # alone on their line, so they can be copied whole (so is the version
        # check under step 1); what belongs under the Windows bullet five
        # spaces in.
        starts = [
            "Set up Technical Cofounder for me, ",
            "This message is for Claude Code. ",
            "",
            "1. If `claude --version` does not work here, ",
            "   Once `claude --version` works, ",
            "2. Git has to be on this computer before anything can be downloaded. ",
            "   - On a Mac, if `xcode-select -p` fails: ",
            "   - On Windows, if `git --version` does not work: ",
            "   winget install ",
            "     If winget is not found, ",
            "     Then, or if one of those two files was already there, ",
            "3. Run these two commands:",
            "   claude plugin marketplace add ",
            "   claude plugin install ",
            "4. Run `claude plugin list --json`, ",
        ]
        lines = self.blocks[0].splitlines()
        self.assertEqual(len(lines), len(starts))
        for line, start in zip(lines, starts):
            with self.subTest(start=start):
                self.assertTrue(line.startswith(start) if start else line == "", line[:60])
                self.assertEqual(line, line.rstrip())

    def test_the_installer_adds_the_catalog_from_the_address_the_message_gives(self):
        source = re.search(r'(?m)^MARKETPLACE_SOURCE = "([^"]+)"', (SETUP / "installer" / "nc_setup.py").read_text(encoding="utf-8"))
        self.assertIn("   claude plugin marketplace add %s\n" % source.group(1), self.blocks[0])

    def test_the_readme_carries_the_same_message_byte_for_byte(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        blocks = re.findall(r"(?ms)^```text\n(.*?)^```$", readme)
        self.assertEqual(blocks, self.blocks)

    def test_the_file_it_points_at_exists_at_that_path_in_the_plugin(self):
        self.assertTrue((SETUP / "skills" / "setup" / "SKILL.md").is_file())


class TheInstallGuards(unittest.TestCase):
    """Two guards in the pasted message. A paste into the desktop app's Chat tab,
    which cannot run commands, is sent to the Code tab. A Claude Code too old to
    install the team's dependency, in the command line or in the desktop app, is
    caught and told how to update, because the old install says it worked."""

    @classmethod
    def setUpClass(cls):
        text = MESSAGE.read_text(encoding="utf-8")
        cls.lines = re.findall(r"(?ms)^```text\n(.*?)^```$", text)[0].splitlines()
        cls.readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        cls.step1 = next(i for i, line in enumerate(cls.lines) if line.startswith("1. "))
        cls.step2 = next(i for i, line in enumerate(cls.lines) if line.startswith("2. "))
        cls.chat = [line for line in cls.lines[:cls.step1] if "Chat tab" in line]
        cls.version = [line for line in cls.lines[cls.step1 + 1:cls.step2] if CLAUDE_CODE_FLOOR in line]

    def one(self, found, what):
        self.assertEqual(len(found), 1, "exactly one line %s, found %d" % (what, len(found)))
        return found[0]

    def test_a_chat_tab_paste_is_told_to_switch_to_the_code_tab(self):
        line = self.one(self.chat, "before step 1 speaks to the Chat tab")
        for needle in ("If you cannot run commands on this computer", "Code tab", "New session", "Local",
                       "leave the folder empty", "paste this same message there"):
            with self.subTest(needle=needle):
                self.assertIn(needle, line)

    def test_the_chat_tab_line_comes_before_anything_an_agent_would_run(self):
        line = self.one(self.chat, "before step 1 speaks to the Chat tab")
        self.assertTrue(self.lines[0].startswith("Set up Technical Cofounder for me, "))
        self.assertLess(self.lines.index(line), self.step1)

    def test_the_version_floor_sits_under_step_1_as_one_line(self):
        line = self.one(self.version, "between step 1 and step 2 names the floor")
        self.assertTrue(line.startswith("   Once `claude --version` works, "), line[:60])

    def test_it_checks_the_command_line_and_the_desktop_app(self):
        line = self.one(self.version, "between step 1 and step 2 names the floor")
        for needle in ("`claude --version`", "Claude desktop app", "CLAUDE_CODE_EXECPATH", "with `--version`"):
            with self.subTest(needle=needle):
                self.assertIn(needle, line)

    def test_it_names_the_update_route_for_each(self):
        line = self.one(self.version, "between step 1 and step 2 names the floor")
        for needle in ("`claude update`", "run the install command above again and use its full path",
                       "Claude > Check for Updates on a Mac", "Help > Check for Updates on Windows",
                       "paste this same message"):
            with self.subTest(needle=needle):
                self.assertIn(needle, line)

    def test_the_floor_is_there_because_the_team_plugin_depends_on_the_engine(self):
        # If this dependency goes, the floor was found for a different install and has to be found again.
        self.assertIn("hyperspace-engine", manifest(TEAM)["dependencies"])

    def test_the_readme_sends_a_chat_tab_paste_to_the_code_tab(self):
        step = next(line for line in self.readme.splitlines() if line.startswith("**1. Give this to your agent.**"))
        self.assertIn("**Code** tab, not Chat", step)

    def test_the_readme_gives_the_command_line_user_the_same_floor(self):
        veteran = self.readme.split("### Already know your way around?", 1)[1].split("### New to building", 1)[0]
        self.assertIn("Claude Code has to be %s or newer (`claude update`)" % CLAUDE_CODE_FLOOR, flat(veteran))
        self.assertIn("without an error", flat(veteran))


if __name__ == "__main__":
    unittest.main()
