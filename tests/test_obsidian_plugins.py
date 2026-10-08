"""Tests for the Obsidian starter: the helper that adds the viewers a user says yes to
(plugins/technical-cofounder-setup/bin/obsidian_plugins.py), the list it installs from
(setup/obsidian-plugins.json), and the words the setup skill and OBSIDIAN.md use around them.

No plugin files ship in the template. The helper fetches each plugin's pinned release
files over HTTPS from the author's GitHub release, checks them against the list's
SHA-256 pins, and only then puts them in `.obsidian/plugins/<id>/` and the id in
`community-plugins.json`. Nothing here touches the network: the fetch is replaced.

Standard library only.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_setup_plugin import flat, step_section

REPO_ROOT = Path(__file__).resolve().parent.parent
SETUP = REPO_ROOT / "plugins" / "technical-cofounder-setup"
HELPER = SETUP / "bin" / "obsidian_plugins.py"
INIT = SETUP / "bin" / "init_workspace.py"
SHIPPED = SETUP / "setup" / "obsidian-plugins.json"
SKILL = SETUP / "skills" / "setup" / "SKILL.md"
GUIDE = SETUP / "template" / "OBSIDIAN.md"

# Licences the list may carry. A plugin under any other licence is a deliberate edit to this set.
LICENCES = {"MIT"}

DEMO = "demo-viewer"
SERVED = {
    "main.js": b"module.exports = class DemoViewer {};\n",
    "manifest.json": b'{"id": "demo-viewer", "name": "Demo Viewer", "version": "1.0.0", "minAppVersion": "1.5.0"}\n',
    "styles.css": b".demo-viewer { color: inherit; }\n",
}


def load():
    spec = importlib.util.spec_from_file_location("obsidian_plugins", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def entry(plugin_id=DEMO, files=None, **more):
    files = SERVED if files is None else files
    base = {
        "id": plugin_id, "name": "Demo Viewer", "repo": "someone/obsidian-demo-viewer", "tag": "1.0.0",
        "licence": "MIT", "read_only": True, "for": "Opens demo files, read-only.",
        "files": {name: sha(data) for name, data in files.items()},
    }
    base.update(more)
    return base


class Fetcher:
    """Stands in for the HTTPS download: serves bytes by file name, records every URL."""

    def __init__(self, served=None, fail=()):
        self.served = dict(SERVED if served is None else served)
        self.fail = set(fail)
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        name = url.rsplit("/", 1)[-1]
        if name in self.fail:
            raise OSError("connection reset")
        return self.served[name]


class Case(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.root = Path(self._td.name).resolve()
        self.project = self.root / "my-project"
        self.project.mkdir()
        self.catalog = self.root / "plugins.json"
        self.write_catalog([entry(), entry("other-viewer", name="Other Viewer")])
        self.op = load()

    def write_catalog(self, plugins):
        self.catalog.write_text(json.dumps({"about": "test", "plugins": plugins}), encoding="utf-8")

    def run_helper(self, *argv, fetch=None):
        fetch = fetch or Fetcher()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = self.op.main([str(a) for a in argv], fetch=fetch, catalog=self.catalog)
        text = out.getvalue()
        return code, (json.loads(text) if text.strip() else None), err.getvalue()

    def install(self, plugin_id=DEMO, fetch=None, project=None):
        return self.run_helper("install", "--project", project or self.project, "--plugin", plugin_id, fetch=fetch)

    @property
    def plugins_dir(self):
        return self.project / ".obsidian" / "plugins"

    @property
    def enabled_file(self):
        return self.project / ".obsidian" / "community-plugins.json"

    def enabled(self):
        return json.loads(self.enabled_file.read_text(encoding="utf-8"))


class InstallsAPlugin(Case):
    def test_its_pinned_files_land_in_the_plugin_folder_under_its_id(self):
        code, doc, _ = self.install()
        self.assertEqual(code, 0)
        self.assertEqual(doc["result"], "installed")
        folder = self.plugins_dir / DEMO
        self.assertEqual(sorted(p.name for p in folder.iterdir()), sorted(SERVED))
        for name, data in SERVED.items():
            with self.subTest(file=name):
                self.assertEqual((folder / name).read_bytes(), data)

    def test_the_files_come_from_the_authors_github_release_over_https(self):
        fetch = Fetcher()
        self.install(fetch=fetch)
        self.assertEqual(sorted(fetch.urls), sorted(
            "https://github.com/someone/obsidian-demo-viewer/releases/download/1.0.0/%s" % name for name in SERVED))

    def test_a_plugin_with_no_stylesheet_is_installed_without_asking_for_one(self):
        files = {k: v for k, v in SERVED.items() if k != "styles.css"}
        self.write_catalog([entry(files=files)])
        fetch = Fetcher()
        code, _, _ = self.install(fetch=fetch)
        self.assertEqual(code, 0)
        self.assertFalse(any(url.endswith("styles.css") for url in fetch.urls))
        self.assertFalse((self.plugins_dir / DEMO / "styles.css").exists())

    def test_the_id_is_added_to_community_plugins_json(self):
        self.install()
        self.assertEqual(self.enabled(), [DEMO])

    def test_the_id_is_added_once_however_often_it_is_installed(self):
        self.install()
        fetch = Fetcher()
        code, doc, _ = self.install(fetch=fetch)
        self.assertEqual(code, 0)
        self.assertEqual(doc["result"], "already")
        self.assertEqual(fetch.urls, [])
        self.assertEqual(self.enabled(), [DEMO])

    def test_ids_already_in_the_list_stay_where_they_were(self):
        self.enabled_file.parent.mkdir(parents=True)
        self.enabled_file.write_text('["mine", "also-mine"]\n', encoding="utf-8")
        self.install()
        self.assertEqual(self.enabled(), ["mine", "also-mine", DEMO])

    def test_two_plugins_are_two_entries(self):
        self.install(DEMO)
        self.install("other-viewer")
        self.assertEqual(self.enabled(), [DEMO, "other-viewer"])

    def test_the_report_says_what_happened_in_a_sentence(self):
        _, doc, _ = self.install()
        self.assertEqual(doc["command"], "install")
        self.assertEqual(doc["plugin"], DEMO)
        self.assertTrue(doc["detail"].strip())
        self.assertNotIn("\n", doc["detail"])


class NeverLeavesHalfAnInstall(Case):
    def assert_nothing_left(self):
        self.assertFalse((self.plugins_dir / DEMO).exists())
        leftovers = [p.name for p in self.plugins_dir.iterdir()] if self.plugins_dir.exists() else []
        self.assertEqual(leftovers, [], "a staging folder or part-file was left behind")
        self.assertFalse(self.enabled_file.exists(), "the plugin was listed without being installed")
        self.assertFalse(Path(str(self.enabled_file) + ".part").exists(), "a half-written list was left behind")

    def test_a_download_that_fails_leaves_no_folder_and_no_list_entry(self):
        code, doc, _ = self.install(fetch=Fetcher(fail={"styles.css"}))
        self.assertEqual(code, 1)
        self.assertEqual(doc["result"], "failed")
        self.assertIn("styles.css", doc["detail"])
        self.assert_nothing_left()

    def test_a_download_that_fails_on_the_first_file_leaves_nothing_either(self):
        code, _, _ = self.install(fetch=Fetcher(fail={"main.js"}))
        self.assertEqual(code, 1)
        self.assert_nothing_left()

    def test_a_file_that_is_not_the_pinned_one_is_refused_the_same_way(self):
        served = dict(SERVED, **{"main.js": b"module.exports = class Tampered {};\n"})
        code, doc, _ = self.install(fetch=Fetcher(served=served))
        self.assertEqual(code, 1)
        self.assertIn("main.js", doc["detail"])
        self.assertIn("does not match", doc["detail"])
        self.assert_nothing_left()

    def test_a_list_that_cannot_be_written_takes_the_installed_folder_back_out(self):
        real = self.op.os.replace

        def replace(source, target):
            if Path(target).name == "community-plugins.json":
                raise OSError("disk full")
            return real(source, target)

        with mock.patch.object(self.op.os, "replace", replace):
            code, doc, _ = self.install()
        self.assertEqual(code, 1)
        self.assertIn("disk full", doc["detail"])
        self.assert_nothing_left()

    def test_a_failure_does_not_touch_ids_already_listed(self):
        self.enabled_file.parent.mkdir(parents=True)
        self.enabled_file.write_text('["mine"]\n', encoding="utf-8")
        self.install(fetch=Fetcher(fail={"manifest.json"}))
        self.assertEqual(self.enabled(), ["mine"])
        self.assertFalse((self.plugins_dir / DEMO).exists())

    def test_a_retry_after_a_failure_installs_cleanly(self):
        self.install(fetch=Fetcher(fail={"styles.css"}))
        code, doc, _ = self.install()
        self.assertEqual((code, doc["result"]), (0, "installed"))
        self.assertEqual(self.enabled(), [DEMO])


class OnlyWhatIsOnTheList(Case):
    def refused(self, plugin_id):
        fetch = Fetcher()
        code, doc, err = self.install(plugin_id, fetch=fetch)
        self.assertEqual(code, 2)
        self.assertIsNone(doc)
        self.assertIn(plugin_id, err)
        self.assertEqual(fetch.urls, [], "something was fetched for an id that is not on the list")
        self.assertFalse((self.project / ".obsidian").exists(), "a folder was made for a refused plugin")

    def test_an_id_that_is_not_on_the_list_is_refused_and_nothing_is_fetched(self):
        self.refused("obsidian-dataview")

    def test_an_id_that_would_leave_the_plugins_folder_is_refused_too(self):
        self.refused("../../escape")

    def test_an_empty_id_is_refused(self):
        self.refused("")


class RefusesWhatItCannotDoSafely(Case):
    def test_a_project_that_is_not_a_folder_is_refused(self):
        fetch = Fetcher()
        code, _, err = self.install(project=self.root / "no-such-folder", fetch=fetch)
        self.assertEqual(code, 2)
        self.assertIn("no-such-folder", err)
        self.assertEqual(fetch.urls, [])

    def test_a_plugin_folder_that_is_already_there_is_never_overwritten(self):
        mine = self.plugins_dir / DEMO
        mine.mkdir(parents=True)
        (mine / "main.js").write_text("// my own copy\n", encoding="utf-8")
        fetch = Fetcher()
        code, doc, _ = self.install(fetch=fetch)
        self.assertEqual((code, doc["result"]), (0, "already"))
        self.assertEqual((mine / "main.js").read_text(encoding="utf-8"), "// my own copy\n")
        self.assertEqual(fetch.urls, [])

    def test_a_list_file_that_is_not_a_json_list_is_refused_untouched_and_before_any_download(self):
        self.enabled_file.parent.mkdir(parents=True)
        self.enabled_file.write_text("{this is not json", encoding="utf-8")
        fetch = Fetcher()
        code, doc, _ = self.install(fetch=fetch)
        self.assertEqual(code, 1)
        self.assertIn("community-plugins.json", doc["detail"])
        self.assertEqual(self.enabled_file.read_text(encoding="utf-8"), "{this is not json")
        self.assertEqual(fetch.urls, [])
        self.assertFalse((self.plugins_dir / DEMO).exists())

    def test_bad_usage_exits_2(self):
        for argv in ([], ["install"], ["install", "--project", str(self.project)], ["frobnicate"]):
            with self.subTest(argv=argv):
                code, _, _ = self.run_helper(*argv)
                self.assertEqual(code, 2)


class TheList(Case):
    def test_list_names_every_plugin_with_what_it_is_for(self):
        code, doc, _ = self.run_helper("list")
        self.assertEqual(code, 0)
        self.assertEqual([p["id"] for p in doc["plugins"]], [DEMO, "other-viewer"])
        for plugin in doc["plugins"]:
            with self.subTest(plugin=plugin["id"]):
                for key in ("id", "name", "for", "licence", "repo", "tag"):
                    self.assertTrue(plugin[key])


class TheShippedList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads(SHIPPED.read_text(encoding="utf-8"))
        cls.plugins = cls.doc["plugins"]

    def test_there_are_plugins_and_each_id_is_unique(self):
        ids = [p["id"] for p in self.plugins]
        self.assertTrue(ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_each_entry_names_its_repository_release_licence_and_purpose(self):
        for plugin in self.plugins:
            with self.subTest(plugin=plugin["id"]):
                self.assertRegex(plugin["id"], r"^[a-z0-9][a-z0-9-]*$")
                self.assertRegex(plugin["repo"], r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
                self.assertRegex(plugin["tag"], r"^[A-Za-z0-9_.-]+$")
                self.assertTrue(plugin["name"].strip() and plugin["for"].strip())
                self.assertNotIn("\n", plugin["for"])

    def test_every_plugin_is_under_a_licence_that_was_read_and_is_read_only(self):
        for plugin in self.plugins:
            with self.subTest(plugin=plugin["id"]):
                self.assertIn(plugin["licence"], LICENCES)
                self.assertIs(plugin["read_only"], True)

    def test_every_file_is_pinned_by_sha256_and_main_js_and_the_manifest_are_there(self):
        for plugin in self.plugins:
            with self.subTest(plugin=plugin["id"]):
                self.assertLessEqual({"main.js", "manifest.json"}, set(plugin["files"]))
                self.assertLessEqual(set(plugin["files"]), {"main.js", "manifest.json", "styles.css"})
                for name, digest in plugin["files"].items():
                    self.assertRegex(digest, r"^[0-9a-f]{64}$", name)

    def test_dataview_stays_off_the_list(self):
        self.assertNotIn("dataview", [p["id"] for p in self.plugins])

    def test_the_list_covers_word_powerpoint_sqlite_json_and_html(self):
        purposes = " ".join(p["for"].lower() for p in self.plugins)
        for kind in ("word", "powerpoint", "sqlite", "json", "html"):
            with self.subTest(kind=kind):
                self.assertIn(kind, purposes)

    def test_the_real_helper_reads_the_shipped_list(self):
        out = subprocess.run([sys.executable, "-I", str(HELPER), "list"], capture_output=True, text=True, check=True)
        self.assertEqual([p["id"] for p in json.loads(out.stdout)["plugins"]], [p["id"] for p in self.plugins])


class AfterTheWorkspaceStep(Case):
    """The skill offers the viewers at the Obsidian step, before the workspace step copies the
    starter `.obsidian/` in. The copy never overwrites, so the list the helper wrote survives."""

    def test_the_workspace_copy_keeps_the_enabled_list_and_adds_the_rest(self):
        self.install()
        out = subprocess.run([sys.executable, "-I", str(INIT), str(self.project), "--obsidian", "--no-super"],
                             capture_output=True, text=True, check=True)
        self.assertIn("SKIPPED: .obsidian/community-plugins.json", out.stdout.replace("\\", "/"))
        self.assertEqual(self.enabled(), [DEMO])
        self.assertTrue((self.plugins_dir / DEMO / "main.js").is_file())
        self.assertTrue((self.project / ".obsidian" / "core-plugins.json").is_file())


class TheObsidianStepSaysIt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.step = step_section("obsidian")
        cls.skill = flat(SKILL.read_text(encoding="utf-8"))

    def test_it_pitches_obsidian_in_a_line_instead_of_declining_to(self):
        self.assertNotIn("don't sell it", self.step)
        self.assertIn("free", self.step)
        self.assertIn("reads every file in this project", self.step)

    def test_it_gives_the_download_link(self):
        self.assertIn("https://obsidian.md/download", self.step)

    def test_it_keeps_the_explain_the_difference_option(self):
        self.assertIn("Yes / No / **Explain the difference**", self.step)

    def test_it_offers_obsidian_md_without_being_asked(self):
        self.assertIn("OBSIDIAN.md", self.step)
        self.assertIn("without being asked", self.step)

    def test_it_installs_viewers_only_through_the_helper_and_only_from_its_list(self):
        for needle in ("obsidian_plugins.py", " list", " install --project", "--plugin", "not on that list"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.step)

    def test_each_viewer_needs_its_own_yes_in_their_own_words(self):
        self.assertIn("in their own words", self.step)
        self.assertIn("that plugin", self.step)

    def test_it_names_what_the_viewers_are_for_and_that_they_run_code(self):
        for needle in ("Word", "PowerPoint", "SQLite", "JSON", "HTML", "community plugins", "read-only"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.step)

    def test_it_says_what_to_click_when_obsidian_asks_whether_to_trust_the_vault(self):
        for needle in ("Do you trust the author of this vault", "Trust author and enable plugins",
                       "Restricted Mode", "Turn on community plugins"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.step)

    def test_the_theme_is_a_one_line_pointer_not_a_download(self):
        self.assertIn("Minimal", self.step)
        self.assertIn("Settings → Appearance → Themes", self.step)

    def test_a_later_switch_to_obsidian_offers_the_viewers_too(self):
        later = flat(self.skill.split("**Obsidian later.**", 1)[1].split(" ## ", 1)[0])
        self.assertIn("obsidian_plugins.py", later)

    def test_the_html_viewer_scripts_switch_is_called_out(self):
        self.assertIn("scripts", self.step.lower())


class TheGuideSaysIt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guide = flat(GUIDE.read_text(encoding="utf-8"))   # the page is wrapped by hand
        cls.plugins = json.loads(SHIPPED.read_text(encoding="utf-8"))["plugins"]

    def test_it_no_longer_says_the_folder_enables_only_built_in_plugins(self):
        self.assertNotIn("enables only Obsidian's own built-in plugins", self.guide)

    def test_it_says_what_to_click_at_the_trust_prompt_and_after_restricted_mode(self):
        for needle in ("Do you trust the author of this vault", "Trust author and enable plugins",
                       "Browse vault in Restricted Mode", "Turn on community plugins"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.guide)

    def test_it_names_every_viewer_setup_can_add(self):
        for plugin in self.plugins:
            with self.subTest(plugin=plugin["id"]):
                self.assertIn(plugin["name"], self.guide)

    def test_it_says_the_viewers_are_other_peoples_code_and_that_html_scripts_stay_off(self):
        self.assertIn("other people", self.guide)
        self.assertRegex(self.guide, r"(?i)scripts[^.]*\boff\b")

    def test_it_points_at_the_minimal_theme_with_the_click_path(self):
        self.assertIn("Minimal", self.guide)
        self.assertIn("Settings → Appearance → Themes", self.guide)


if __name__ == "__main__":
    unittest.main()
