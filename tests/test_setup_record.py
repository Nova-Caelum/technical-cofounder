"""Unit tests for plugins/technical-cofounder-setup/bin/setup_record.py: the setup record
(<project>/core_text/setup.json) and the rendered guide
(<project>/core_text/setup-guide.html for part 1, setup-extras.html for part 2),
both driven by setup/steps.json.

Standard library only. Key-shaped test values are assembled at runtime so this
file never carries one.
"""
import html
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "technical-cofounder-setup"
SCRIPT = PLUGIN_ROOT / "bin" / "setup_record.py"
STEPS = json.loads((PLUGIN_ROOT / "setup" / "steps.json").read_text(encoding="utf-8"))["steps"]
STEP_IDS = [s["id"] for s in STEPS]
PART1 = [s for s in STEPS if s["part"] == 1]
PART2 = [s for s in STEPS if s["part"] == 2]
ASK_LINE = "Questions at any point? Just ask. Type it in the chat and your agent will answer."
PLUGIN_VERSION = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def cli(*args):
    return subprocess.run(["python3", str(SCRIPT), *map(str, args)], capture_output=True, text=True, stdin=subprocess.DEVNULL)


def record(project):
    return json.loads((Path(project) / "core_text" / "setup.json").read_text(encoding="utf-8"))


def files_outside_core_text(project):
    root = Path(project)
    return {
        str(p.relative_to(root)): p.stat().st_mtime_ns
        for p in root.rglob("*")
        if p.is_file() and p.relative_to(root).parts[0] != "core_text"
    }


class Project(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.project = Path(self._td.name)
        self.addCleanup(self._td.cleanup)


class AutoCreateTests(Project):
    def test_every_subcommand_creates_the_record(self):
        for sub in (["status"], ["render"], ["set", "guide", "done"]):
            with self.subTest(sub=sub[0]):
                with tempfile.TemporaryDirectory() as td:
                    args = [sub[0], td, *sub[1:]]
                    r = cli(*args)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertTrue((Path(td) / "core_text" / "setup.json").is_file())

    def test_new_record_shape(self):
        cli("status", self.project)
        rec = record(self.project)
        self.assertEqual(rec["schema_version"], 1)
        self.assertEqual(rec["plugin_version"], PLUGIN_VERSION)
        self.assertEqual(list(rec["steps"]), STEP_IDS)
        for step in STEPS:
            self.assertEqual(rec["steps"][step["id"]], {"status": "pending", "at": None, "part": step["part"]})
        self.assertEqual(rec["choices"], {})
        self.assertTrue(rec["created"].endswith("Z"))
        self.assertEqual(rec["created"], rec["updated"])

    def test_auto_create_is_idempotent(self):
        cli("status", self.project)
        first = (self.project / "core_text" / "setup.json").read_text(encoding="utf-8")
        cli("status", self.project)
        cli("render", self.project)
        self.assertEqual((self.project / "core_text" / "setup.json").read_text(encoding="utf-8"), first)

    def test_existing_record_is_never_overwritten(self):
        (self.project / "core_text").mkdir()
        mine = {"schema_version": 1, "plugin_version": "0.0.1", "created": "c", "updated": "u",
                "steps": {"guide": {"status": "done", "at": "2020-01-01T00:00:00Z"}}, "choices": {"super": "no"}}
        path = self.project / "core_text" / "setup.json"
        path.write_text(json.dumps(mine), encoding="utf-8")
        for sub in ("status", "render"):
            r = cli(sub, self.project)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), mine)

    def test_unreadable_record_is_left_alone(self):
        (self.project / "core_text").mkdir()
        path = self.project / "core_text" / "setup.json"
        path.write_text("{not json", encoding="utf-8")
        r = cli("set", self.project, "guide", "done")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(path.read_text(encoding="utf-8"), "{not json")

    def test_a_step_added_later_reads_as_pending(self):
        (self.project / "core_text").mkdir()
        older = {"schema_version": 1, "plugin_version": "0.0.1", "created": "c", "updated": "u",
                 "steps": {"guide": {"status": "done", "at": "t"}}, "choices": {}}
        (self.project / "core_text" / "setup.json").write_text(json.dumps(older), encoding="utf-8")
        r = cli("status", self.project)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"DONE 1/{len(STEP_IDS)}", r.stdout)
        self.assertRegex(r.stdout, r"(?m)^github\s+pending\b")


class SetTests(Project):
    def test_done_with_a_declared_choice(self):
        r = cli("set", self.project, "github", "done", "--choice", "github=yes")
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = record(self.project)
        self.assertEqual(rec["steps"]["github"]["status"], "done")
        self.assertTrue(rec["steps"]["github"]["at"].endswith("Z"))
        self.assertEqual(rec["choices"], {"github": "yes"})
        self.assertGreaterEqual(rec["updated"], rec["created"])
        self.assertTrue((self.project / "core_text" / "setup-guide.html").is_file())

    def test_workspace_worklog_view(self):
        r = cli("set", self.project, "workspace", "done", "--choice", "worklog_view=csv")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(record(self.project)["choices"], {"worklog_view": "csv"})

    def test_pending_clears_at(self):
        cli("set", self.project, "editor", "done", "--choice", "editor=vscode")
        cli("set", self.project, "editor", "pending")
        editor = next(s for s in STEPS if s["id"] == "editor")
        self.assertEqual(record(self.project)["steps"]["editor"], {"status": "pending", "at": None, "part": 1, "title": editor["title"]})
        self.assertEqual(record(self.project)["choices"], {"editor": "vscode"})

    def test_every_recorded_step_says_which_part_it_belongs_to(self):
        # The team plugin's session briefing reads only this record: it must
        # be able to tell part 1 from part 2 without this plugin's files.
        cli("set", self.project, "github", "done", "--choice", "github=yes")
        cli("set", self.project, "super", "skipped", "--choice", "super=no")
        rec = record(self.project)
        self.assertEqual({sid: entry["part"] for sid, entry in rec["steps"].items()}, {s["id"]: s["part"] for s in STEPS})

    def test_a_skipped_step_carries_what_skipping_costs(self):
        github = next(s for s in STEPS if s["id"] == "github")
        cli("set", self.project, "github", "skipped", "--choice", "github=no")
        entry = record(self.project)["steps"]["github"]
        self.assertEqual(entry["status"], "skipped")
        self.assertEqual(entry["if_skipped"], github["if_skipped"])
        self.assertTrue(entry["at"].endswith("Z"))

    def test_a_step_that_is_set_carries_its_title(self):
        # The team plugin's session briefing names a skipped step by its title,
        # and reads only this record. One rule: whatever the status, the entry
        # `set` writes carries the title steps.json gives the step.
        github = next(s for s in STEPS if s["id"] == "github")
        for status in ("skipped", "done", "pending"):
            with self.subTest(status=status):
                r = cli("set", self.project, "github", status)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(record(self.project)["steps"]["github"]["title"], github["title"])

    def test_only_a_skipped_step_carries_that_text(self):
        cli("set", self.project, "github", "skipped", "--choice", "github=no")
        for status in ("done", "pending"):
            with self.subTest(status=status):
                cli("set", self.project, "github", "skipped")
                cli("set", self.project, "github", status)
                self.assertNotIn("if_skipped", record(self.project)["steps"]["github"])
        self.assertFalse([sid for sid, entry in record(self.project)["steps"].items() if "if_skipped" in entry])

    def test_an_older_record_gains_the_part_when_a_step_is_set(self):
        (self.project / "core_text").mkdir()
        older = {"schema_version": 1, "plugin_version": "0.0.1", "created": "c", "updated": "u",
                 "steps": {"guide": {"status": "done", "at": "t"}, "super": {"status": "pending", "at": None}}, "choices": {}}
        (self.project / "core_text" / "setup.json").write_text(json.dumps(older), encoding="utf-8")
        cli("set", self.project, "editor", "done", "--choice", "editor=vscode")
        rec = record(self.project)
        self.assertEqual(rec["steps"]["guide"], {"status": "done", "at": "t", "part": 1})
        self.assertEqual(rec["steps"]["super"]["part"], 2)
        self.assertEqual({sid: entry["part"] for sid, entry in rec["steps"].items()}, {s["id"]: s["part"] for s in STEPS})

    def _refused(self, *args):
        cli("status", self.project)
        before = (self.project / "core_text" / "setup.json").read_text(encoding="utf-8")
        r = cli("set", self.project, *args)
        self.assertNotEqual(r.returncode, 0, f"accepted: {args}")
        self.assertEqual((self.project / "core_text" / "setup.json").read_text(encoding="utf-8"), before)
        return r

    def test_refuses_unknown_step(self):
        self._refused("no-such-step", "done")

    def test_refuses_unknown_status(self):
        self._refused("guide", "finished")

    def test_refuses_undeclared_choice(self):
        self._refused("guide", "done", "--choice", "super=yes")

    def test_refuses_another_steps_choice(self):
        self._refused("editor", "done", "--choice", "github=yes")

    def test_refuses_choice_without_equals(self):
        self._refused("editor", "done", "--choice", "editor")

    def test_refuses_value_over_40_chars(self):
        self._refused("editor", "done", "--choice", "editor=" + "x" * 41)

    def test_accepts_value_of_40_chars(self):
        r = cli("set", self.project, "editor", "done", "--choice", "editor=" + "x" * 19 + " " + "y" * 20)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_refuses_key_shaped_values_without_echoing_them(self):
        shaped = [
            "sk-" + "A1b2C3d4" * 3,
            "gh" + "p_" + "a1B2c3D4" * 4,
            "AK" + "IA" + "ABCDEFGH12345678",
            "k" * 33,
        ]
        for value in shaped:
            with self.subTest(prefix=value[:3]):
                r = self._refused("editor", "done", "--choice", f"editor={value}")
                self.assertNotIn(value, r.stdout + r.stderr)

    def test_refuses_free_text(self):
        for value in ("I use vim, mostly", "a<b", "someone@example.com"):
            with self.subTest(value=value):
                self._refused("editor", "done", "--choice", f"editor={value}")

    def test_prerequisites_records_the_computer(self):
        for value in ("mac", "windows", "linux"):
            with self.subTest(value=value):
                r = cli("set", self.project, "prerequisites", "done", "--choice", f"os={value}")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(record(self.project)["choices"]["os"], value)

    def test_os_is_refused_on_other_steps(self):
        for step in ("guide", "editor", "github"):
            with self.subTest(step=step):
                self._refused(step, "done", "--choice", "os=mac")

    def test_os_takes_only_mac_windows_or_linux(self):
        for value in ("beos", "Mac", "macos"):
            with self.subTest(value=value):
                r = self._refused("prerequisites", "done", "--choice", f"os={value}")
                self.assertNotIn(value, r.stdout + r.stderr)


class StatusTests(Project):
    def test_counts(self):
        r = cli("status", self.project)
        self.assertIn(f"DONE 0/{len(STEP_IDS)}", r.stdout)
        cli("set", self.project, "guide", "done")
        cli("set", self.project, "prerequisites", "done")
        cli("set", self.project, "obsidian", "skipped")
        r = cli("status", self.project)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"DONE 2/{len(STEP_IDS)}", r.stdout)
        self.assertRegex(r.stdout, r"(?m)^obsidian\s+skipped\s+\S+\s*$")
        self.assertRegex(r.stdout, r"(?m)^guide\s+done\s+1\s*$")
        for sid in STEP_IDS:
            self.assertIn(sid, r.stdout)


class RenderTests(Project):
    def html(self, name="setup-guide.html"):
        return (self.project / "core_text" / name).read_text(encoding="utf-8")

    def test_contains_every_step(self):
        cli("render", self.project)
        for name, steps in (("setup-guide.html", PART1), ("setup-extras.html", PART2)):
            page = self.html(name)
            for s in steps:
                with self.subTest(page=name, step=s["id"]):
                    self.assertIn(html.escape(s["title"]), page)
                    self.assertIn(html.escape(s["does"]), page)

    def test_self_contained(self):
        cli("render", self.project)
        for name in ("setup-guide.html", "setup-extras.html"):
            low = self.html(name).lower()
            for banned in ("<script", "http", "<link", "@import", "url(", "<img", "<iframe"):
                with self.subTest(page=name, banned=banned):
                    self.assertNotIn(banned, low)
            self.assertIn("prefers-color-scheme: dark", low)
            self.assertIn("continue setup", low)
            self.assertIn("ok to skip", low)

    def test_every_step_carries_a_cost(self):
        for s in STEPS:
            with self.subTest(step=s["id"]):
                self.assertIsInstance(s.get("cost"), str)
                self.assertTrue((s.get("cost") or "").strip(), "empty or missing cost")

    def test_a_card_per_step_in_order(self):
        cli("render", self.project)
        page = self.html()
        self.assertEqual(len(re.findall(r'<li class="card\b', page)), len(PART1))
        self.assertEqual(re.findall(r'data-step="([^"]+)"', page), [s["id"] for s in PART1])
        self.assertEqual(re.findall(r'data-step="([^"]+)"', self.html("setup-extras.html")), [s["id"] for s in PART2])

    def test_the_footer_names_the_plugin_that_rendered_the_page(self):
        cli("render", self.project)
        for name in ("setup-guide.html", "setup-extras.html"):
            with self.subTest(page=name):
                footer = self.html(name).split("<footer>", 1)[1]
                self.assertIn(f"technical-cofounder-setup {PLUGIN_VERSION}", footer)

    def test_steps_are_cards_not_a_table(self):
        cli("render", self.project)
        self.assertNotIn("<table", self.html().lower())

    def test_every_cost_and_label_appears(self):
        cli("render", self.project)
        page = self.html()
        for s in PART1:
            with self.subTest(step=s["id"]):
                self.assertIn(html.escape(s.get("cost") or "\0missing"), page)
                self.assertIn(html.escape(s["why"]), page)
                self.assertIn(html.escape(s["if_skipped"]), page)
        for label in (">Why<", ">If you skip<", ">Cost<", ">Required<", ">OK to skip<"):
            with self.subTest(label=label):
                self.assertIn(label, page)
        self.assertEqual(page.count(">Required<"), sum(not s["skippable"] for s in PART1))

    def test_minutes_pill_per_card(self):
        cli("render", self.project)
        pills = re.findall(r'<span class="pill">(\d+) min</span>', self.html())
        self.assertEqual([int(m) for m in pills], [s["minutes"] for s in PART1 if s["minutes"] is not None])

    def test_escapes_text(self):
        cli("status", self.project)
        path = self.project / "core_text" / "setup.json"
        rec = json.loads(path.read_text(encoding="utf-8"))
        rec["plugin_version"] = "<b>bold</b>"
        path.write_text(json.dumps(rec), encoding="utf-8")
        cli("render", self.project)
        page = self.html()
        self.assertNotIn("<b>bold</b>", page)
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", page)

    def test_marks_and_minutes(self):
        cli("set", self.project, "guide", "done")
        cli("set", self.project, "github", "skipped")
        page = self.html()
        self.assertIn("✓", page)
        self.assertIn("Skipped", page)
        self.assertIn("To do", page)
        left = sum(s["minutes"] or 0 for s in PART1 if s["id"] not in ("guide", "github"))
        self.assertIn(f"{left} minutes", page)


class PartsTests(Project):
    """The guide is two pages: part 1 (about 20 minutes) and part 2 (extras)."""

    def setUp(self):
        super().setUp()
        self.r = cli("render", self.project)
        core = self.project.resolve() / "core_text"
        self.guide_path, self.extras_path = core / "setup-guide.html", core / "setup-extras.html"
        self.guide = self.guide_path.read_text(encoding="utf-8")
        self.extras = self.extras_path.read_text(encoding="utf-8")

    def test_part_1_page_excludes_the_super_card(self):
        self.assertNotIn('data-step="super"', self.guide)
        self.assertNotIn(html.escape([s for s in PART2][0]["title"]), self.guide)

    def test_part_1_total_reads_about_20_minutes(self):
        self.assertIn("About 20 minutes", self.guide)
        self.assertEqual(sum(s["minutes"] or 0 for s in PART1) // 5 * 5, 20)

    def test_extras_page_holds_super_under_its_own_title(self):
        self.assertIn('data-step="super"', self.extras)
        self.assertIn("Setup, part 2: extras", self.extras)
        self.assertNotIn('data-step="guide"', self.extras)

    def test_both_pages_carry_the_absolute_extras_path_and_the_ask_line(self):
        for name, page in (("guide", self.guide), ("extras", self.extras)):
            with self.subTest(page=name):
                self.assertTrue(self.extras_path.is_absolute())
                self.assertIn(html.escape(str(self.extras_path)), page)
                self.assertIn(f'href="{self.extras_path.as_uri()}"', page)
                self.assertGreaterEqual(page.count(ASK_LINE), 2, "near the top and in the closing block")

    def test_part_1_page_ends_with_thanks_then_next_steps(self):
        end = self.guide[self.guide.rindex("Thanks for setting up."):]
        self.assertIn("Next steps", end)
        self.assertIn("Setup part 2 (extras) is here:", end)
        self.assertIn(html.escape(str(self.extras_path)), end)

    def test_a_null_minutes_step_renders_without_a_pill(self):
        obsidian = next(s for s in PART1 if s["id"] == "obsidian")
        self.assertIsNone(obsidian["minutes"])
        card = re.search(r'<li class="card[^>]*data-step="obsidian".*?</li>', self.guide, re.S).group(0)
        self.assertNotIn('class="pill"', card)
        self.assertNotIn("None", self.guide)
        self.assertEqual(self.guide.count('class="pill"'), sum(s["minutes"] is not None for s in PART1))

    def test_render_prints_guide_and_extras_paths(self):
        self.assertEqual(self.r.returncode, 0, self.r.stderr)
        lines = self.r.stdout.splitlines()
        self.assertIn(f"GUIDE: {self.guide_path}", lines)
        self.assertIn(f"EXTRAS: {self.extras_path}", lines)

    def test_the_editor_step_is_required(self):
        editor = next(s for s in STEPS if s["id"] == "editor")
        self.assertFalse(editor["skippable"])
        self.assertIn("TextEdit", editor["if_skipped"])
        card = re.search(r'<li class="card[^>]*data-step="editor".*?</li>', self.guide, re.S).group(0)
        self.assertIn(">Required<", card)

    def test_the_obsidian_card_links_the_plugin_copy_by_default(self):
        want = PLUGIN_ROOT / "template" / "OBSIDIAN.md"
        self.assertIn(f'href="{want.as_uri()}"', self.guide)
        self.assertIn("Everything about Obsidian is here, or you can just ask.", self.guide)

    def test_the_obsidian_card_links_the_project_copy_when_it_exists(self):
        mine = self.project.resolve() / "OBSIDIAN.md"
        mine.write_text("# mine\n", encoding="utf-8")
        cli("render", self.project)
        page = self.guide_path.read_text(encoding="utf-8")
        self.assertIn(f'href="{mine.as_uri()}"', page)
        self.assertNotIn((PLUGIN_ROOT / "template" / "OBSIDIAN.md").as_uri(), page)


class WriteScopeTests(Project):
    def test_writes_only_inside_core_text(self):
        (self.project / "README.md").write_text("mine\n", encoding="utf-8")
        (self.project / ".claude").mkdir()
        (self.project / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
        before = files_outside_core_text(self.project)
        cli("status", self.project)
        cli("set", self.project, "github", "done", "--choice", "github=yes")
        cli("set", self.project, "no-such-step", "done")
        cli("render", self.project)
        self.assertEqual(files_outside_core_text(self.project), before)
        self.assertEqual(
            sorted(p.name for p in (self.project / "core_text").iterdir()),
            ["setup-extras.html", "setup-guide.html", "setup.json"],
        )


class UsageTests(unittest.TestCase):
    def test_no_arguments_is_usage_error(self):
        self.assertEqual(cli().returncode, 2)

    def test_missing_project_argument_is_usage_error(self):
        self.assertEqual(cli("status").returncode, 2)


if __name__ == "__main__":
    unittest.main()
