"""Anthropic's plugin directory refuses COMMAND_PATH_COMPUTED when a hook script
it follows runs a computed path or an inline program (portal probes e-h,
2026-10-13: only the circuit-breaker + drive-map-write group blocked)."""
import re
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "plugins" / "technical-cofounder" / "hooks"
INLINE = re.compile(r"""\b(awk\s+'|perl\s+-e|python3?\s+-c|node\s+-e)""")
COMPUTED_EXEC = re.compile(r"""^\s*exec\s+"\$(?!\{CLAUDE_PLUGIN_ROOT\})""")


class PortalCommandPathTests(unittest.TestCase):
    def scripts(self):
        return sorted(HOOKS.glob("*.sh")) + sorted((HOOKS / "lib").glob("*.sh"))

    def test_no_hook_script_runs_an_inline_program(self):
        for path in self.scripts():
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                self.assertIsNone(INLINE.search(line), f"{path.name}:{n}: {line.strip()}")

    def test_no_hook_script_execs_a_computed_path(self):
        for path in self.scripts():
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(COMPUTED_EXEC.search(line), f"{path.name}:{n}: {line.strip()}")


if __name__ == "__main__":
    unittest.main()
