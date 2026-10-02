"""Unit tests for plugins/technical-cofounder/registry/check_registry.py: the
`with_engine` block is required in the plugin's own registry and optional in
a project's own (ROOT is a project's .claude/ folder), where a missing block
reads as empty so registries written before the field existed still pass.

Standard library only.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "technical-cofounder"
CHECK = PLUGIN_ROOT / "registry" / "check_registry.py"

AGENT_FILE = """---
name: bookkeeper
description: Keeps the project's books.
---

# Bookkeeper

You keep the books. Reach for `assumption-check` before you state a number.
"""


def run_check(script, *args):
    return subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=120,
    )


class Scratch(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)


class PluginRegistry(Scratch):
    """The plugin's own registry: every entry must say what it uses from the engine."""

    def copy_of_the_plugin(self):
        copy = self.tmp / "technical-cofounder"
        shutil.copytree(PLUGIN_ROOT, copy, ignore=shutil.ignore_patterns("__pycache__"))
        return copy

    def test_the_shipped_registry_passes(self):
        r = run_check(CHECK)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("REGISTRY OK: 4 agents", r.stdout)

    def test_an_entry_without_with_engine_fails(self):
        copy = self.copy_of_the_plugin()
        path = copy / "registry" / "agents.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        del next(a for a in registry["agents"] if a["name"] == "lead-fde")["with_engine"]
        path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        r = run_check(copy / "registry" / "check_registry.py")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("lead-fde: field 'with_engine' missing", r.stdout)

    def test_the_same_holds_when_the_plugin_root_is_passed_by_name(self):
        copy = self.copy_of_the_plugin()
        path = copy / "registry" / "agents.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        del next(a for a in registry["agents"] if a["name"] == "engineer")["with_engine"]
        path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        r = run_check(copy / "registry" / "check_registry.py", copy)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("engineer: field 'with_engine' missing", r.stdout)


class ProjectRegistry(Scratch):
    """A project's own registry, under its .claude/ folder."""

    def project(self, **entry):
        root = self.tmp / "my-project" / ".claude"
        (root / "agents").mkdir(parents=True)
        (root / "registry").mkdir()
        (root / "agents" / "bookkeeper.md").write_text(AGENT_FILE, encoding="utf-8")
        agent = {"name": "bookkeeper", "role": "executor-builder", "use_when": "The books need keeping.",
                 "skills": ["assumption-check"], "mcp_tools": [], "with_super": {}}
        agent.update(entry)
        registry = {"schema_version": 1, "roles": {"executor-builder": "Builds to a spec."}, "agents": [agent]}
        (root / "registry" / "agents.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
        return root

    def test_a_registry_written_before_with_engine_existed_still_passes(self):
        r = run_check(CHECK, self.project())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("REGISTRY OK: 1 agents", r.stdout)
        self.assertIn("+engine: 0 skills, 0 servers", r.stdout)

    def test_a_with_engine_block_that_is_there_is_still_checked(self):
        root = self.project(with_engine={"skills": ["gear5-build"], "mcp_servers": ["hyperspace"]})
        r = run_check(CHECK, root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("bookkeeper: registry lists 'gear5-build' but agents/bookkeeper.md never names it", r.stdout)

    def test_a_with_engine_that_is_not_an_object_fails(self):
        r = run_check(CHECK, self.project(with_engine=["gear5-build"]))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("bookkeeper: field 'with_engine' missing, empty or not a dict", r.stdout)

    def test_the_other_fields_stay_required_in_a_project(self):
        root = self.project()
        path = root / "registry" / "agents.json"
        registry = json.loads(path.read_text(encoding="utf-8"))
        del registry["agents"][0]["with_super"]
        path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        r = run_check(CHECK, root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("bookkeeper: field 'with_super' missing", r.stdout)


if __name__ == "__main__":
    unittest.main()
