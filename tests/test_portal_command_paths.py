"""Anthropic's plugin directory refuses COMMAND_PATH_COMPUTED when a hook script
it follows runs a computed path or an inline program (portal probes e-h,
2026-10-13: only the circuit-breaker + drive-map-write group blocked)."""
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_plugin_hooks import BASH

HOOKS = Path(__file__).resolve().parents[1] / "plugins" / "technical-cofounder" / "hooks"
INLINE = re.compile(r"""\b(awk\s+'|perl\s+-e|python3?\s+-c|node\s+-e)""")
UNQUOTED_GLOB = re.compile(r'"\*|[^\s\'"]\*\.[A-Za-z]+(\s|;|$)')
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

    def test_normalization_uses_a_literal_external_sed_program(self):
        # q blocked, r and s passed (portal validation, 2026-10-13). Protect s's
        # validated representation, without claiming all inline sed is banned.
        script = (HOOKS / "circuit-breaker.sh").read_text(encoding="utf-8")
        body = script.split("normalize_error_class() {", 1)[1].split("\n}\n", 1)[0]
        commands = [line for line in body.splitlines() if "| sed " in line]
        self.assertEqual(len(commands), 1)
        self.assertIn('sed -E -f "${CLAUDE_PLUGIN_ROOT}/hooks/lib/normalize-error.sed"', commands[0])
        self.assertTrue((HOOKS / "lib" / "normalize-error.sed").is_file())

    def test_normalization_preserves_error_classes(self):
        script = (HOOKS / "circuit-breaker.sh").read_text(encoding="utf-8")
        body = script.split("normalize_error_class() {", 1)[1].split("\n}\n", 1)[0]
        program = 'set -euo pipefail\nnormalize_error_class() {' + body + '\n}\n'
        program += 'for sample in "$@"; do normalize_error_class "$sample"; printf "\\0"; done\n'
        cases = [
            ("", "<no-error-text>"),
            ("FAIL 123", "fail <n>"),
            ("missing 'alpha' and \"beta\"", "missing <lit> and <lit>"),
            ("at /opt/project/file.txt code 0xDEADBEEF", "at <path> code <hex>"),
            ("ID 550e8400-e29b-41d4-a716-446655440000", "id <uuid>"),
            ("TOKEN ABCDEFGHIJKLMNOPQRSTUVWXYZ", "token <token>"),
            ("Alpha\n\nBeta\t  Gamma\n", "alpha beta gamma"),
            ("x " * 300, "x " * 250),
        ]
        # A plugin location containing spaces must still find its sed file.
        with tempfile.TemporaryDirectory(prefix="portal plugin ") as tmp:
            root = Path(tmp)
            target = root / "hooks" / "lib"
            target.mkdir(parents=True)
            (target / "normalize-error.sed").write_bytes((HOOKS / "lib" / "normalize-error.sed").read_bytes())
            result = subprocess.run(
                [BASH, "-c", program, "normalization-test", *[raw for raw, _ in cases]],
                env={**os.environ, "CLAUDE_PLUGIN_ROOT": root.as_posix()},
                capture_output=True, text=True, encoding="utf-8",
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split("\0")[:-1], [expected for _, expected in cases])

    def test_no_hook_script_uses_a_shell_glob_on_a_path(self):
        # Keep path globs out of commands followed by the portal. Probe s
        # passed with the quoted find patterns; i/j did not isolate globs.
        for path in self.scripts():
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith("#") or "-name " in line:
                    continue
                self.assertIsNone(UNQUOTED_GLOB.search(line), f"{path.name}:{n}: {line.strip()}")


if __name__ == "__main__":
    unittest.main()
