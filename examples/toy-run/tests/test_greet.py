"""End to end: run greet.py as a user would and check what it prints."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class GreetTests(unittest.TestCase):
    def test_prints_the_greeting_file(self):
        out = subprocess.run(
            [sys.executable, str(ROOT / "greet.py")], capture_output=True, text=True, check=True
        ).stdout.strip()
        self.assertEqual(out, (ROOT / "greeting.txt").read_text(encoding="utf-8").strip())
        self.assertEqual(out, "Hello, world")


if __name__ == "__main__":
    unittest.main()
