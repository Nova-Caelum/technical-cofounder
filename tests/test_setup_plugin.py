"""Unit tests for the shape of plugins/technical-cofounder-setup: the front
door installed once for the whole computer. It is a skill, a command, scripts
and data: no hooks, no MCP server, no agents, no dependencies. The setup
pieces live here and nowhere in the team plugin, and the skill carries the
instructions the setup conversation depends on.

Standard library only.
"""
import importlib.util
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
# The install section is two boxes the user always uses in order (the founder's pick, 2026-10-08): the typed command,
# then the message for the agent. `/plugin install <name> --marketplace <source>` needs Claude Code 2.1.275 or
# later (code.claude.com/docs/en/plugins/install, read 2026-10-08); the message's step 1 updates anything older.
INSTALL_COMMAND = "/plugin install technical-cofounder-setup --marketplace Nova-Caelum/plugins"
MARKETPLACE_FLOOR = "2.1.275"
BOX_1_LABEL = (
    "Type this into Claude Code (in the desktop app, the Code tab, not Chat) and press Enter. "
    "If it asks where to install, choose Install for you (user scope):"
)
BETWEEN = (
    "Then paste this message. If the command showed an error (Git missing, an unknown command, or Claude Code "
    "older than 2.1.275), paste it anyway: it fixes what is missing."
)
OPENING = (
    "Set up Technical Cofounder for me. I want you to install these plugins from Nova Caelum's catalog at "
    "https://github.com/Nova-Caelum/plugins, which I trust: technical-cofounder-setup now, then technical-cofounder "
    "(my team; it brings hyperspace-engine with it), and super-novacaelum only if I say yes to the research extras."
)
# Words in the message box before this change (the 15-line message), and the most the new one may have: it
# measured 379 when it was written, with the Chat-tab and version guards kept.
WORDS_BEFORE = 442
WORDS_CEILING = 380
CONSENT_TEAM = "Yes, install technical-cofounder from Nova-Caelum/plugins"
CONSENT_EXTRAS = "Yes, install super-novacaelum from Nova-Caelum/plugins"


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


class TheJudgeStep(unittest.TestCase):
    """The engine step says what the verifier's judge does and offers no
    judge, with Explain the difference; its words live in steps.json like
    every other reason. A command line that is not signed in is offered
    `claude auth login`, and "turn on" / "turn off the judge" work later."""

    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.flat = flat(cls.text)
        cls.description = re.search(r"(?m)^description:\s*(.+?)\s*$", cls.text.split("---", 2)[1]).group(1)
        cls.entry = next(e for e in STEPS["install"] if e["id"] == "engine-env")

    def test_steps_json_carries_the_judge_line_and_an_explain_line_per_option(self):
        line = self.entry.get("judge")
        self.assertTrue(isinstance(line, str) and line.strip() and "\n" not in line)
        for needle in ("Claude plan", "No judge"):
            with self.subTest(needle=needle):
                self.assertIn(needle, line)
        explain = self.entry.get("explain")
        self.assertIsInstance(explain, list)
        self.assertEqual(len(explain), 2)
        for text in explain:
            self.assertTrue(isinstance(text, str) and text.strip() and "\n" not in text)

    def test_the_skill_says_the_line_from_steps_json_and_never_restates_it(self):
        self.assertNotIn(self.entry["judge"], self.flat)
        for text in self.entry["explain"]:
            self.assertNotIn(text, self.flat)
        step = flat(heading_body(self.text, "Scan, plan, apply, re-scan"))
        for needle in ("`engine-env`", "`judge` line", EXPLAIN_LABEL, "No judge"):
            with self.subTest(needle=needle):
                self.assertIn(needle, step)

    def test_no_judge_and_turning_it_on_go_through_the_install_script(self):
        for needle in ('judge --project "<project>" --set none', 'judge --project "<project>" --set claude-code',
                       "claude auth login", "--choice judge=", "--choice judge_why="):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.flat)

    def test_the_description_names_turning_the_judge_on_and_off(self):
        for phrase in ("turn on the judge", "turn off the judge"):
            with self.subTest(phrase=phrase):
                self.assertIn(f'"{phrase}"', self.description.lower())


class TheMessage(unittest.TestCase):
    """reference/install-message.md: what a person pastes, in two boxes they
    always use in order. Box 1 is the command they type; box 2 is the message
    for the agent, and it fixes whatever box 1 could not (Git, an old Claude
    Code) and installs the setup plugin itself. The README and the website
    copy it from this file."""

    @classmethod
    def setUpClass(cls):
        cls.text = MESSAGE.read_text(encoding="utf-8")
        cls.blocks = re.findall(r"(?ms)^```text\n(.*?)^```$", cls.text)
        cls.box = cls.blocks[1] if len(cls.blocks) == 2 else ""
        cls.lines = cls.box.splitlines()

    def test_two_boxes_with_one_line_before_the_first_and_one_between(self):
        self.assertEqual(len(self.blocks), 2)
        self.assertEqual(self.text.count("```"), 4)
        before, rest = self.text.split("```text", 1)
        between = rest.split("```", 1)[1].split("```text", 1)[0]
        self.assertEqual(len([line for line in before.splitlines() if line.strip()]), 1)
        self.assertEqual(len([line for line in between.splitlines() if line.strip()]), 1)
        self.assertEqual(self.text.rsplit("```", 1)[1].strip(), "")

    def test_the_first_line_says_to_type_it_into_claude_code_and_press_enter(self):
        label = self.text.split("```text", 1)[0].strip()
        self.assertEqual(label, BOX_1_LABEL)

    def test_the_line_between_says_to_paste_the_message_anyway_after_an_error(self):
        between = self.text.split("```", 2)[2].split("```text", 1)[0].strip()
        self.assertEqual(between, BETWEEN)

    def test_the_message_is_the_agreed_one(self):
        self.assertEqual(self.lines[0][:len(OPENING)], OPENING)
        self.assertEqual([line[:2] for line in self.lines if re.match(r"\d\. ", line)], ["1.", "2.", "3.", "4."])
        for needle in (
            "curl -fsSL https://claude.ai/install.sh | bash",
            "irm https://claude.ai/install.ps1 | iex",
            "`winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements`",
            "`claude plugin marketplace add https://github.com/Nova-Caelum/plugins.git`",
            "`claude plugin install technical-cofounder-setup@nova-caelum`",
            "paste this message again",
            "Run `claude plugin list --json`, find the installPath of technical-cofounder-setup, read skills/setup/SKILL.md "
            "inside it, and follow it from the top, one step at a time.",
            "Tell me what each step is for before you run it.",
            # A command line installed a moment ago is not on this session's PATH.
            "~/.local/bin/claude",
            r"%USERPROFILE%\.local\bin\claude.exe",
            # Git has to be here before the plugin that checks for it can be downloaded.
            "xcode-select --install",
            r"C:\Program Files\Git\cmd\git.exe",
            r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe",
            "https://git-scm.com/downloads/win",
            "and its terminal window, if I used one",
            # Git found but not on this session's PATH needs the restart as much as Git just installed.
            "Whether you just installed it or found it there",
        ):
            with self.subTest(needle=needle[:40]):
                self.assertIn(needle, self.box)

    def test_every_line_of_the_message_starts_where_it_was_agreed(self):
        starts = [
            OPENING,
            "Claude Code may ask me to approve a command or press Run. ",
            "This message is for Claude Code. ",
            "",
            "1. Claude Code: ",
            "2. Git must be installed before anything downloads. ",
            "3. If technical-cofounder-setup is not installed yet, install it: ",
            "4. Run `claude plugin list --json`, ",
        ]
        self.assertEqual(len(self.lines), len(starts))
        for line, start in zip(self.lines, starts):
            with self.subTest(start=start):
                self.assertTrue(line.startswith(start) if start else line == "", line[:60])
                self.assertEqual(line, line.rstrip())

    def test_the_installer_adds_the_catalog_from_the_address_the_message_gives(self):
        source = re.search(r'(?m)^MARKETPLACE_SOURCE = "([^"]+)"', (SETUP / "installer" / "nc_setup.py").read_text(encoding="utf-8"))
        self.assertIn("`claude plugin marketplace add %s`" % source.group(1), self.box)

    def test_step_3_runs_the_commands_the_install_walk_runs(self):
        spec = importlib.util.spec_from_file_location("ci_install_walk", REPO_ROOT / "scripts" / "ci_install_walk.py")
        walk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(walk)
        step = next(line for line in self.lines if line.startswith("3. "))
        self.assertEqual(walk.SETUP, "technical-cofounder-setup@nova-caelum")
        self.assertIn("then `claude plugin install %s`" % walk.SETUP, step)

    def test_the_file_it_points_at_exists_at_that_path_in_the_plugin(self):
        self.assertTrue((SETUP / "skills" / "setup" / "SKILL.md").is_file())


class TheTwoBoxes(unittest.TestCase):
    """The founder's pick, 2026-10-08: a typed command, then the prompt written
    for the agent. The user always does both, in order."""

    @classmethod
    def setUpClass(cls):
        cls.text = MESSAGE.read_text(encoding="utf-8")
        cls.blocks = re.findall(r"(?ms)^```text\n(.*?)^```$", cls.text)
        cls.readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    def test_box_1_is_exactly_the_typed_command_and_nothing_else(self):
        self.assertEqual(self.blocks[0], INSTALL_COMMAND + "\n")

    def test_box_1_is_a_command_claude_code_runs_from_a_line_that_starts_with_a_slash(self):
        # A line that starts with /plugin runs as a command: trailing words would become its arguments.
        self.assertTrue(self.blocks[0].startswith("/plugin install "))
        self.assertEqual(len(self.blocks[0].splitlines()), 1)
        self.assertTrue(self.blocks[0].strip().endswith("--marketplace Nova-Caelum/plugins"))

    def test_the_line_between_the_boxes_covers_git_an_unknown_command_and_an_old_claude_code(self):
        for needle in ("Git missing", "an unknown command", "older than %s" % MARKETPLACE_FLOOR, "paste it anyway",
                       "it fixes what is missing"):
            with self.subTest(needle=needle):
                self.assertIn(needle, BETWEEN)

    def test_the_label_says_which_scope_to_choose(self):
        self.assertIn("choose Install for you (user scope)", BOX_1_LABEL)

    def test_box_2_always_follows_and_installs_the_setup_plugin_itself_when_box_1_did_not(self):
        step = next(line for line in self.blocks[1].splitlines() if line.startswith("3. "))
        self.assertIn("If technical-cofounder-setup is not installed yet, install it: ", step)

    def test_the_message_checks_claude_code_before_git_before_the_install(self):
        steps = [line for line in self.blocks[1].splitlines() if re.match(r"\d\. ", line)]
        self.assertIn("`claude --version` must work and be %s or newer" % CLAUDE_CODE_FLOOR, steps[0])
        self.assertTrue(steps[1].startswith("2. Git must be installed before anything downloads."))
        self.assertTrue(steps[2].startswith("3. If technical-cofounder-setup"))

    def test_the_readme_carries_both_boxes_byte_for_byte_in_order(self):
        blocks = re.findall(r"(?ms)^```text\n(.*?)^```$", self.readme)
        self.assertEqual(blocks, self.blocks)

    def test_the_readme_carries_the_same_two_sentences_around_them_in_order(self):
        step = self.readme.split("### New to building with agents?", 1)[1].split("**2. Follow along.**", 1)[0]
        plain = flat(step.replace("**", ""))
        self.assertIn("1. Install the setup plugin. " + flat(BOX_1_LABEL), plain)
        self.assertIn(flat(BETWEEN), plain)
        self.assertLess(step.index(INSTALL_COMMAND), step.index("Then paste this message."))
        self.assertLess(step.index("Then paste this message."), step.index("Set up Technical Cofounder for me."))
        self.assertLess(plain.index(flat(BOX_1_LABEL)), plain.index(INSTALL_COMMAND))

    def test_the_readme_names_the_chat_tab_before_the_first_box(self):
        step = next(line for line in self.readme.splitlines() if line.startswith("**1. Install the setup plugin.**"))
        self.assertIn("**Code** tab, not Chat", step)

    def test_the_message_is_shorter_than_before(self):
        words = len(self.blocks[1].split())
        self.assertLess(words, WORDS_BEFORE)
        self.assertLessEqual(words, WORDS_CEILING, "the message grew past %d words: %d" % (WORDS_CEILING, words))


class TheInstallGuards(unittest.TestCase):
    """Two guards in the pasted message. A paste into the desktop app's Chat tab,
    which cannot run commands, is sent to the Code tab. A Claude Code too old to
    install the team's dependency, in the command line or in the desktop app, is
    caught and told how to update, because the old install says it worked."""

    @classmethod
    def setUpClass(cls):
        text = MESSAGE.read_text(encoding="utf-8")
        cls.lines = re.findall(r"(?ms)^```text\n(.*?)^```$", text)[1].splitlines()
        cls.readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        cls.step1 = next(i for i, line in enumerate(cls.lines) if line.startswith("1. "))
        cls.chat = [line for line in cls.lines[:cls.step1] if "Chat tab" in line]
        cls.version = [line for line in cls.lines if line.startswith("1. ")]

    def one(self, found, what):
        self.assertEqual(len(found), 1, "exactly one line %s, found %d" % (what, len(found)))
        return found[0]

    def test_a_chat_tab_paste_is_told_to_switch_to_the_code_tab(self):
        line = self.one(self.chat, "before step 1 speaks to the Chat tab")
        for needle in ("If you cannot run commands here", "Code tab", "click New session", "choose Local",
                       "leave the folder empty", "paste this message there"):
            with self.subTest(needle=needle):
                self.assertIn(needle, line)

    def test_the_chat_tab_line_comes_before_anything_an_agent_would_run(self):
        line = self.one(self.chat, "before step 1 speaks to the Chat tab")
        self.assertTrue(self.lines[0].startswith("Set up Technical Cofounder for me."))
        self.assertLess(self.lines.index(line), self.step1)

    def test_the_version_floor_sits_in_step_1(self):
        line = self.one(self.version, "is step 1")
        self.assertIn("`claude --version` must work and be %s or newer" % CLAUDE_CODE_FLOOR, line)

    def test_it_checks_the_command_line_and_the_desktop_app(self):
        line = self.one(self.version, "is step 1")
        for needle in ("`claude --version`", "Claude desktop app", "CLAUDE_CODE_EXECPATH", "run with --version"):
            with self.subTest(needle=needle):
                self.assertIn(needle, line)

    def test_it_names_the_update_route_for_each(self):
        line = self.one(self.version, "is step 1")
        for needle in ("`claude update`", "or install it", "Claude > Check for Updates on a Mac",
                       "Help > Check for Updates on Windows", "paste this message again"):
            with self.subTest(needle=needle):
                self.assertIn(needle, line)

    def test_the_floor_is_there_because_the_team_plugin_depends_on_the_engine(self):
        # If this dependency goes, the floor was found for a different install and has to be found again.
        self.assertIn("hyperspace-engine", manifest(TEAM)["dependencies"])

    def test_the_readme_gives_the_command_line_user_the_same_floor(self):
        veteran = self.readme.split("### Already know your way around?", 1)[1].split("### New to building", 1)[0]
        self.assertIn("Claude Code has to be %s or newer (`claude update`)" % CLAUDE_CODE_FLOOR, flat(veteran))
        self.assertIn("without an error", flat(veteran))


class TheConsent(unittest.TestCase):
    """The safety check reads what the user says and what the agent runs, not
    what a skill file asks for. So before each plugin install the setup skill
    requests, it asks the user to say so in their own words, and installs only
    after that reply."""

    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")
        scan = cls.text.split("\n## Scan, plan, apply, re-scan\n", 1)[1].split("\n## ", 1)[0]
        marker = "- **`team-plugin` when its verdict is `install`, `upgrade` or `repair`**"
        cls.team = flat(scan.split(marker, 1)[1].split("\n   - ", 1)[0]) if marker in scan else ""
        cls.extras = step_section("super")

    def test_the_team_install_waits_for_a_reply_in_their_own_words(self):
        self.assertTrue(self.team, "no `team-plugin` consent bullet in the apply walk")
        for needle in ("technical-cofounder", "Nova-Caelum/plugins", "in their own words",
                       '"%s"' % CONSENT_TEAM, "Run `apply` for it only after that reply"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.team)

    def test_the_team_consent_is_asked_in_the_chat_as_free_text(self):
        self.assertIn("in the chat", self.team)
        self.assertIn("not a pop-up", self.team)

    def test_a_no_stops_there_and_installs_nothing(self):
        self.assertIn("If they say no", self.team)
        self.assertIn("run nothing", self.team)

    def test_the_extras_install_waits_for_a_reply_in_their_own_words(self):
        for needle in ("in their own words", '"%s"' % CONSENT_EXTRAS, "Nova-Caelum/plugins",
                       "Run `super-setup` only after that reply"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.extras)

    def test_the_consent_comes_before_the_install_in_the_extras_step(self):
        self.assertLess(self.extras.index(CONSENT_EXTRAS), self.extras.index("Run `super-setup` only after that reply"))

    def test_the_plain_install_path_says_where_the_consent_goes(self):
        scan = flat(self.text.split("\n## Scan, plan, apply, re-scan\n", 1)[1].split("\n## ", 1)[0])
        self.assertLess(scan.index("`team-plugin` when its verdict is"), scan.index("**`engine-env` when its verdict is `install`**"))


# ── The guide, as a first-time user meets it (round-1 fixes from the first
# live test). Each class below is one finding; the text they pin is the
# setup skill, its steps.json, the profile template and the guide renderer.

import html  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402

EXPLAIN_LABEL = "Explain the difference"
EXPLAIN_RULE = (
    "Every choice you ask them to make ends with one more option, **Explain the difference**: "
    "what they gain or lose with each."
)
# Choice keys nobody is asked for: the install script detects the computer,
# and the worklog view follows the Obsidian answer.
NOT_ASKED = {"os", "worklog_view"}
# Steps that ask a choice no key records: where the project goes, and the
# profile's test drive and desktop-or-CLI questions.
ASKS_UNRECORDED = {"prerequisites", "profile"}
PROFILE_TEMPLATE = SETUP / "template" / "core_text" / "user.md"
DEFAULT_ANSWERING = "Give options with a recommendation and a short why, and say plainly when uncertain."
KEPT_QUESTION = "Anything else that would change how an agent should work with you?"
UNDERSTAND_FIRST = "the first step of any piece of work is Understand"
EXTRAS = (("Exa", "web research"), ("Context7", "library docs"), ("Browserbase", "cloud browser"))
GH_EXE = r"C:\Program Files\GitHub CLI\gh.exe"
GH_PROMPTS = (
    ('"Where do you use GitHub?"', "**GitHub.com**"),
    ('"What is your preferred protocol for Git operations on this host?"', "**HTTPS**"),
    ('"Authenticate Git with your GitHub credentials?"', "**Yes**"),
    ('"How would you like to authenticate GitHub CLI?"', "**Login with a web browser**"),
)


def one_line(value):
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value


def heading_body(text, needle):
    """The text under the first heading that contains `needle`, up to the
    next heading of the same or a higher level, unflattened."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        mark = re.match(r"(#+) ", line)
        if mark and needle in line:
            body = []
            for nxt in lines[i + 1:]:
                other = re.match(r"(#+) ", nxt)
                if other and len(other.group(1)) <= len(mark.group(1)):
                    break
                body.append(nxt)
            return "\n".join(body)
    raise AssertionError(f"no heading containing {needle!r}")


def step_section(step_id):
    """The skill's section for a step: its heading carries (`id`), except
    the project-folder choice, which is asked under Where the project goes."""
    needle = "Where the project goes" if step_id == "prerequisites" else f"(`{step_id}`)"
    return flat(heading_body(SKILL.read_text(encoding="utf-8"), needle))


def asked_steps():
    return [s for s in STEPS["steps"] if set(s["choices"]) - NOT_ASKED or s["id"] in ASKS_UNRECORDED]


class GuideChoices(unittest.TestCase):
    """Every choice the setup asks for offers to explain the difference, and
    what it says then comes from steps.json, like every other reason."""

    def test_how_to_talk_gives_every_choice_an_explain_option(self):
        how = flat(heading_body(SKILL.read_text(encoding="utf-8"), "How to talk"))
        self.assertIn(EXPLAIN_RULE, how)
        self.assertIn("`explain`", how)

    def test_the_steps_that_ask_are_the_ones_expected(self):
        self.assertEqual({s["id"] for s in asked_steps()},
                         {"prerequisites", "editor", "obsidian", "github", "profile", "super"})

    def test_every_step_that_asks_carries_an_explain_line_per_option(self):
        for step in asked_steps():
            with self.subTest(step=step["id"]):
                lines = step.get("explain")
                self.assertIsInstance(lines, list)
                self.assertGreaterEqual(len(lines), 2)
                for line in lines:
                    self.assertTrue(one_line(line), line)

    def test_each_step_that_asks_offers_the_option_where_it_asks(self):
        for step in asked_steps():
            with self.subTest(step=step["id"]):
                self.assertIn(EXPLAIN_LABEL, step_section(step["id"]))

    def test_the_worklog_choice_says_what_the_worklog_is(self):
        obsidian = step_section("obsidian")
        self.assertIn("worklog", obsidian)
        self.assertIn("Hyperspace Engine's console", obsidian)
        explain = next(s for s in STEPS["steps"] if s["id"] == "obsidian").get("explain") or []
        self.assertIn("worklog", " ".join(explain))

    def test_nothing_promises_a_csv_file(self):
        steps = json.dumps(STEPS["steps"]).lower()
        for name, text in (("SKILL.md", SKILL.read_text(encoding="utf-8").lower()), ("steps.json", steps)):
            with self.subTest(file=name):
                self.assertNotIn("csv", text)

    def test_continue_setup_moves_a_later_obsidian_user_over(self):
        cont = flat(SKILL.read_text(encoding="utf-8").split("**Continue setup.**", 1)[1].split("\n## ", 1)[0])
        for needle in ("init_workspace.py", "--obsidian", "obsidian=yes", "worklog_view=obsidian"):
            with self.subTest(needle=needle):
                self.assertIn(needle, cont)


class ProfileInterview(unittest.TestCase):
    """The profile asks only what an agent cannot work out: the energy and
    answer-style questions became defaults, a test drive replaced 'what are
    you building', and it asks desktop app or command line."""

    @classmethod
    def setUpClass(cls):
        body = heading_body(SKILL.read_text(encoding="utf-8"), "(`profile`)")
        cls.flat = flat(body)
        cls.questions = [flat(q) for q in re.split(r"(?m)^\d+\. ", body)[1:]]
        cls.template = PROFILE_TEMPLATE.read_text(encoding="utf-8")

    def test_the_energy_and_answer_style_questions_are_gone(self):
        self.assertTrue(self.questions)
        for question in self.questions:
            with self.subTest(question=question[:40]):
                self.assertNotRegex(question.lower(), r"sharp|tired|options presented|recommendation|uncertain")

    def test_it_opens_with_a_test_drive_not_what_are_you_building(self):
        self.assertIn("test drive", self.questions[0].lower())
        self.assertNotIn("What are you building", self.flat)

    def test_it_asks_desktop_app_or_command_line(self):
        self.assertTrue([q for q in self.questions if "desktop app" in q and "command line (CLI)" in q])

    def test_the_open_question_is_kept(self):
        self.assertTrue([q for q in self.questions if KEPT_QUESTION in q])

    def test_the_template_carries_the_two_defaults(self):
        self.assertRegex(self.template, r"`steady`[^\n]*default")
        self.assertIn(DEFAULT_ANSWERING, self.template)
        for stale in ("<lead with a recommendation", "<how should uncertainty be flagged", '<e.g. "I\'m locked in">'):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, self.template)

    def test_the_template_has_a_line_for_the_app_they_use(self):
        self.assertIn("Where you run your agents: <desktop app, command line (CLI), or both>", self.template)
        self.assertIn("test drive", self.template)


class ClosingText(unittest.TestCase):
    """The closing tells a first-time user how to open their project, what
    the trust prompt is, what the extras buy, and where work starts."""

    @classmethod
    def setUpClass(cls):
        cls.closing = flat(heading_body(SKILL.read_text(encoding="utf-8"), "Closing"))

    def test_it_says_how_to_open_a_session_in_the_project_folder(self):
        for needle in ("Code tab", "new session", "choose the project folder", "`cd`", "`claude`"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.closing)

    def test_it_says_what_the_trust_prompt_means_and_to_accept_it(self):
        self.assertIn("trust this folder", self.closing)
        self.assertIn("their own project", self.closing)

    def test_it_names_the_three_research_extras_and_what_each_buys(self):
        for name, buys in EXTRAS:
            with self.subTest(extra=name):
                self.assertIn(name, self.closing)
                self.assertIn(buys, self.closing.lower())

    def test_it_points_to_understand(self):
        self.assertIn(UNDERSTAND_FIRST, self.closing)


class GitHubOnWindows(unittest.TestCase):
    """A gh installed a moment ago is not on this session's PATH on Windows,
    and gh auth login asks four questions a first-time user cannot guess."""

    @classmethod
    def setUpClass(cls):
        cls.github = step_section("github")

    def test_a_new_gh_is_used_by_its_full_path(self):
        self.assertIn(GH_EXE, self.github)
        self.assertIn("full path", self.github)
        self.assertIn("PATH", self.github)

    def test_each_login_prompt_comes_with_its_answer_in_order(self):
        at = -1
        for prompt, answer in GH_PROMPTS:
            with self.subTest(prompt=prompt):
                self.assertIn(prompt, self.github)
                self.assertIn(answer, self.github)
                self.assertGreater(self.github.index(prompt), at)
                at = self.github.index(prompt)
        self.assertIn("one-time code", self.github)
        self.assertIn("github.com/login/device", self.github)

    def test_they_log_in_from_their_own_terminal_window(self):
        self.assertIn("terminal window", self.github)


class GitHubOnMac(unittest.TestCase):
    """`brew install gh` needs Homebrew, which a first-time Mac user may not
    have and which setup cannot install for them (its installer asks for the
    Mac's password in a terminal). The skill reads the plan's `homebrew` row
    and, when Homebrew is missing, walks them through getting it before it
    asks them to run `brew install gh`."""

    INSTALLER = "/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""

    @classmethod
    def setUpClass(cls):
        cls.github = step_section("github")

    def test_it_reads_the_plans_homebrew_row_on_a_mac(self):
        self.assertIn("`homebrew` row", self.github)
        self.assertIn("Homebrew is not installed", self.github)

    def test_the_homebrew_route_comes_before_brew_install_gh(self):
        self.assertIn(self.INSTALLER, self.github)
        self.assertIn("brew install gh", self.github)
        self.assertLess(self.github.index("Homebrew is not installed"), self.github.index("brew install gh"))
        self.assertLess(self.github.index(self.INSTALLER), self.github.index("brew install gh"))

    def test_the_first_time_user_is_told_what_the_homebrew_installer_asks_of_them(self):
        for needle in ("Terminal", "Mac password", "Next steps", "new Terminal window", "brew --version"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.github)
        self.assertIn("No password goes in the chat", self.github)

    def test_setup_checks_again_instead_of_taking_their_word(self):
        self.assertIn("run `plan` again", self.github)

    def test_a_mac_that_would_rather_not_install_homebrew_can_leave_github_for_later(self):
        self.assertIn("GitHub is optional", self.github)

    def test_a_gh_installed_a_moment_ago_is_used_by_its_full_path_on_a_mac_too(self):
        for path in ("/opt/homebrew/bin/gh", "/usr/local/bin/gh"):
            with self.subTest(path=path):
                self.assertIn(path, self.github)


class ResearchExtras(unittest.TestCase):
    """The extras are three services, each named with what it buys, where
    they are offered and in the reference page the agent reads."""

    def test_part_2_names_each_and_what_it_buys(self):
        part2 = step_section("super")
        for name, buys in EXTRAS:
            with self.subTest(extra=name):
                self.assertIn(name, part2)
                self.assertIn(buys, part2.lower())

    def test_the_extras_step_names_each(self):
        does = next(s for s in STEPS["steps"] if s["id"] == "super")["does"]
        for name, buys in EXTRAS:
            with self.subTest(extra=name):
                self.assertIn(name, does)
                self.assertIn(buys, does.lower())

    def test_the_reference_page_covers_them(self):
        page = flat(heading_body((SETUP / "reference" / "dependencies.md").read_text(encoding="utf-8"),
                                 "Research extras"))
        for name, buys in EXTRAS:
            with self.subTest(extra=name):
                self.assertIn(name, page)
                self.assertIn(buys, page.lower())
        self.assertIn("super-novacaelum", page)


class VerifyPointers(unittest.TestCase):
    """Every step names one place the user can check the claim themselves,
    the skill says it, and the guide shows it on the step's card."""

    def test_every_step_has_one_verify_line(self):
        for step in STEPS["steps"]:
            with self.subTest(step=step["id"]):
                self.assertTrue(one_line(step.get("verify")))
                self.assertNotIn("http", step["verify"].lower())  # the guide pages are offline

    def test_the_skill_says_each_steps_verify_line(self):
        text = SKILL.read_text(encoding="utf-8")
        for title in ("Scan, plan, apply, re-scan", "The guide and the questions"):
            with self.subTest(section=title):
                self.assertIn("`verify`", flat(heading_body(text, title)))

    def test_every_card_shows_its_verify_line(self):
        with tempfile.TemporaryDirectory() as project:
            subprocess.run([sys.executable, str(SETUP / "bin" / "setup_record.py"), "render", project],
                           check=True, capture_output=True)
            pages = "".join((Path(project) / "core_text" / name).read_text(encoding="utf-8")
                            for name in ("setup-guide.html", "setup-extras.html"))
        self.assertEqual(pages.count("<dt>Check it yourself</dt>"), len(STEPS["steps"]))
        for step in STEPS["steps"]:
            with self.subTest(step=step["id"]):
                self.assertIn(html.escape(step.get("verify") or "<missing>"), pages)


class UnderstandFirst(unittest.TestCase):
    """'What to try first' says no run is open yet and that work starts at
    Understand."""

    def test_what_to_try_first_says_no_run_is_open_and_where_work_starts(self):
        first = step_section("first-steps")
        self.assertIn("no run is open yet", first)
        self.assertIn(UNDERSTAND_FIRST, first)


if __name__ == "__main__":
    unittest.main()
