"""The setup plugin's setup/steps.json is the one source of every "why" and
"how long" in setup. These tests fail when anything else that says a reason
out loud stops agreeing with it:

  - the install script's item table (every item it can plan has an entry)
  - the two first-step scripts, which run before Python exists and so cannot
    read the file: the reasons they print must be the file's, word for word
  - reference/dependencies.md, the page a person reads: it is checked against
    the file, not generated from it

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
STEPS_FILE = SETUP / "setup" / "steps.json"
PAGE = SETUP / "reference" / "dependencies.md"
README = REPO_ROOT / "README.md"

DOC = json.loads(STEPS_FILE.read_text(encoding="utf-8"))
INSTALL = {entry["id"]: entry for entry in DOC["install"]}

# Items the install script plans that are not tools on the computer, so the
# dependencies page has no row for them: a connection check, the project
# folder, a question about files already there, the plugin catalog and the
# team itself. Every other item must be on the page. A new item is therefore
# either documented or added here on purpose.
NOT_TOOLS = {"network", "project-folder", "existing-config", "marketplace", "team-plugin"}
WINDOWS_ONLY = "Windows only"
MAC_ONLY = "Mac only"


def load_install_script():
    spec = importlib.util.spec_from_file_location("nc_setup_for_reasons", SETUP / "installer" / "nc_setup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def one_line(value):
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value


def page_rows():
    """The rows of the page's at-a-glance table: (tool, item id, needed on, why)."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("|") and "Setup item" in line)
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        tool, item, needed, why = (cell.strip() for cell in line.strip().strip("|").split("|"))
        rows.append((tool, item.strip("`"), needed, why))
    return rows


class OneSource(unittest.TestCase):
    def test_there_is_one_reasons_file_and_it_is_the_setup_plugins(self):
        found = sorted(p.relative_to(REPO_ROOT).as_posix() for p in (REPO_ROOT / "plugins").rglob("steps.json"))
        self.assertEqual(found, ["plugins/technical-cofounder-setup/setup/steps.json"])
        self.assertFalse((TEAM / "setup").exists())

    def test_the_install_script_reads_that_file(self):
        self.assertEqual(load_install_script().STEPS_FILE, STEPS_FILE.resolve())

    def test_every_item_the_script_can_plan_has_a_one_line_reason_and_a_time(self):
        ids = [item.id for item in load_install_script().ITEMS]
        self.assertEqual(sorted(INSTALL), sorted(ids), "steps.json and the script's item table list different items")
        for item_id in ids:
            entry = INSTALL[item_id]
            with self.subTest(item=item_id):
                self.assertTrue(one_line(entry.get("why")), "why is empty or more than one line")
                self.assertIs(type(entry.get("minutes")), int)
                if "why_windows" in entry:
                    self.assertTrue(one_line(entry["why_windows"]), "why_windows is empty or more than one line")

    def test_every_guide_step_has_a_reason_and_a_time_or_none(self):
        self.assertTrue(DOC["steps"])
        for step in DOC["steps"]:
            with self.subTest(step=step["id"]):
                self.assertTrue(one_line(step["why"]))
                self.assertIn(type(step["minutes"]), (int, type(None)))


class FirstStepScripts(unittest.TestCase):
    """They install uv and Python (and Git on Windows) before anything can
    read a JSON file, so each prints its reasons itself."""

    def said(self, script, text):
        body = (SETUP / "installer" / script).read_text(encoding="utf-8")
        self.assertIn(text, body, f"{script} no longer says the reason steps.json carries")

    def test_bootstrap_sh_says_the_files_reasons(self):
        for item_id in ("uv", "python"):
            with self.subTest(item=item_id):
                self.said("bootstrap.sh", INSTALL[item_id]["why"])

    def test_bootstrap_ps1_says_the_files_reasons(self):
        for text in (INSTALL["git"]["why_windows"], INSTALL["uv"]["why"], INSTALL["python"]["why"]):
            with self.subTest(text=text[:30]):
                self.said("bootstrap.ps1", text)


class DependenciesPage(unittest.TestCase):
    def test_every_row_gives_the_reason_steps_json_carries(self):
        rows = page_rows()
        self.assertTrue(rows)
        for tool, item_id, needed, why in rows:
            with self.subTest(tool=tool):
                self.assertIn(item_id, INSTALL, "the page names a setup item the install script does not have")
                entry = INSTALL[item_id]
                want = entry["why_windows"] if needed == WINDOWS_ONLY and "why_windows" in entry else entry["why"]
                self.assertEqual(why, want)

    def test_every_tool_the_script_installs_or_checks_is_on_the_page(self):
        on_page = {item_id for _, item_id, _, _ in page_rows()}
        self.assertEqual(sorted(set(INSTALL) - NOT_TOOLS - on_page), [], "no row on the dependencies page")
        self.assertEqual(sorted(NOT_TOOLS - set(INSTALL)), [], "NOT_TOOLS names an item the script no longer has")
        self.assertEqual(sorted(NOT_TOOLS & on_page), [], "an item is both on the page and in NOT_TOOLS")

    def test_a_windows_reason_has_its_own_row(self):
        windows_rows = {item_id for _, item_id, needed, _ in page_rows() if needed == WINDOWS_ONLY}
        for item_id, entry in INSTALL.items():
            if "why_windows" in entry and item_id not in NOT_TOOLS:
                with self.subTest(item=item_id):
                    self.assertIn(item_id, windows_rows)

    def test_each_tool_on_the_page_has_its_own_section(self):
        text = PAGE.read_text(encoding="utf-8")
        headings = re.findall(r"(?m)^### (.+)$", text)
        for tool, _, _, _ in page_rows():
            with self.subTest(tool=tool):
                self.assertTrue([h for h in headings if h.startswith(tool)], "no '### <tool>' section")

    def test_homebrew_is_listed_as_a_mac_only_tool(self):
        rows = {item_id: (tool, needed) for tool, item_id, needed, _ in page_rows()}
        self.assertEqual(rows.get("homebrew"), ("Homebrew", MAC_ONLY))

    def test_the_homebrew_section_says_what_it_is_for_and_that_setup_does_not_install_it(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn("### Homebrew", text, "no '### Homebrew' section")
        section = text.split("### Homebrew", 1)[1].split("\n### ", 1)[0]
        for needle in ("brew install gh", "Mac password", "https://brew.sh", "Setup never installs"):
            with self.subTest(needle=needle):
                self.assertIn(needle, section)

    def test_the_page_states_the_python_floor_and_that_setup_installs_it(self):
        text = PAGE.read_text(encoding="utf-8")
        section = text.split("### Python", 1)[1].split("\n### ", 1)[0]
        self.assertIn("3.11 or newer", section)
        self.assertIn("installed for you", section)

    def test_the_page_describes_no_local_loop_or_verifier(self):
        text = PAGE.read_text(encoding="utf-8")
        for stale in ("the verifier", "working-loop gates", "Coming in a later version"):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, text)


if __name__ == "__main__":
    unittest.main()



class ReadmeDependencyRow(unittest.TestCase):
    """The README's badge row shows what the page lists; a Mac user without
    Homebrew finds out there that it exists and what it is for."""

    @classmethod
    def setUpClass(cls):
        cls.readme = README.read_text(encoding="utf-8")

    def test_the_row_has_a_homebrew_badge_that_links_to_the_dependencies_page(self):
        badge = re.search(
            r'<a href="([^"]+)"><img src="https://img\.shields\.io/badge/Homebrew[^"]*" alt="([^"]*)"></a>', self.readme)
        self.assertIsNotNone(badge, "no Homebrew badge in the README")
        self.assertEqual(badge.group(1), "plugins/technical-cofounder-setup/reference/dependencies.md")
        self.assertIn("Homebrew", badge.group(2))
        self.assertIn("Mac", badge.group(2))

    def test_it_sits_in_the_same_row_as_the_other_tools(self):
        row = self.readme.split("<!-- Top Row Badges -->", 1)[1].split("</p>", 1)[0]
        for alt in ("Claude Code CLI", "Git", "Python 3.11 or newer", "uv", "jq", "Homebrew"):
            with self.subTest(alt=alt):
                self.assertIn('alt="%s' % alt, row)
