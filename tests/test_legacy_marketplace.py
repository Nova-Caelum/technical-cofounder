"""The repository-root marketplace is the old install address, kept on purpose.

Its entries name folders that were later renamed (plugins/base-novacaelum is now
plugins/technical-cofounder). That is correct only while each entry stays pinned
to a commit where its folder exists. These tests keep it that way, so the file
never points at a folder that is missing at its pinned commit.
"""
import json
import pathlib
import subprocess
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
REPO_URL = "https://github.com/Nova-Caelum/technical-cofounder.git"


def git(*args):
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True)


class LegacyMarketplaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(MARKETPLACE.read_text(encoding="utf-8"))

    def test_every_entry_is_pinned_to_one_commit_of_this_repository(self):
        for entry in self.data["plugins"]:
            with self.subTest(plugin=entry["name"]):
                source = entry["source"]
                self.assertEqual(source["source"], "git-subdir")
                self.assertEqual(source["url"], REPO_URL)
                self.assertRegex(source["sha"], r"^[0-9a-f]{40}$")

    def test_every_pinned_folder_exists_at_its_commit(self):
        for entry in self.data["plugins"]:
            source = entry["source"]
            if git("cat-file", "-e", source["sha"] + "^{commit}").returncode != 0:
                self.skipTest("pinned commit not in this checkout (shallow clone)")
            with self.subTest(plugin=entry["name"]):
                manifest = "%s:%s/.claude-plugin/plugin.json" % (source["sha"], source["path"])
                shown = git("show", manifest)
                self.assertEqual(shown.returncode, 0, "%s is missing at its pinned commit" % source["path"])
                self.assertEqual(json.loads(shown.stdout)["name"], entry["name"])

    def test_descriptions_say_this_is_the_old_address(self):
        self.assertIn("old install address", self.data["description"])
        for entry in self.data["plugins"]:
            with self.subTest(plugin=entry["name"]):
                self.assertIn("Nova-Caelum/plugins", entry["description"])


if __name__ == "__main__":
    unittest.main()
