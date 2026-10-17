"""Collector safety boundaries and local transport; never starts Codex/model turns."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rehearse_codex', ROOT / 'scripts/rehearse_codex.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Rehearsal(unittest.TestCase):
    def test_rpc_notifications_and_approval_refusal(self):
        runner.rpc_module.self_test()

    def test_live_requires_external_runner(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, CODEX_THREAD_ID='agent'):
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/rehearse_codex.py'), '--root', d,
                                     '--tc-ref', 'HEAD', '--runner', 'user-terminal', '--turns'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('A4', result.stderr)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_unknown_probes_rejected(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/rehearse_codex.py'), '--tc-ref', 'HEAD',
                                 '--probes', 'R1,R3'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Only R1', result.stderr)

    def test_unowned_root_and_resolved_vault_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'keep').write_text('user data')
            with patch.object(sys, 'argv', ['rehearse', '--root', d, '--tc-ref', 'HEAD']):
                with self.assertRaises(SystemExit) as caught:
                    runner.main()
                self.assertEqual(caught.exception.code, 2)
            vault = root / 'vault'; vault.mkdir(); (vault / '.obsidian').mkdir()
            alias = root / 'alias'; alias.symlink_to(vault, target_is_directory=True)
            with patch.object(sys, 'argv', ['rehearse', '--root', str(alias), '--tc-ref', 'HEAD']):
                with self.assertRaises(SystemExit) as caught:
                    runner.main()
                self.assertEqual(caught.exception.code, 2)
            self.assertEqual((root / 'keep').read_text(), 'user data')
            self.assertEqual(list(vault.iterdir()), [vault / '.obsidian'])

    def test_managed_edit_cannot_be_accepted_as_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root / '.codex').mkdir()
            path = root / 'AGENTS.md'; path.write_text('managed')
            runner.write(root / '.codex/technical-cofounder-install.json', {'files': {'AGENTS.md': {'sha256': runner.sha(path)}}})
            self.assertIn('AGENTS.md', runner.managed(root))
            path.write_text('edited')
            with self.assertRaisesRegex(ValueError, 'changed'):
                runner.managed(root)

    def test_six_hooks_all_must_be_trusted_and_enabled(self):
        p = Path('/tmp/project')
        hooks = [{'sourcePath': str(p / '.codex/hooks.json'), 'enabled': True, 'trustStatus': 'trusted'} for _ in range(6)]
        response = {'data': [{'hooks': hooks}]}
        self.assertTrue(runner.trusted_hooks(response, p))
        hooks[0]['trustStatus'] = 'untrusted'
        self.assertFalse(runner.trusted_hooks(response, p))
        hooks[0]['trustStatus'] = 'trusted'; hooks[0]['enabled'] = False
        self.assertFalse(runner.trusted_hooks(response, p))
        hooks.pop(0)
        self.assertFalse(runner.trusted_hooks(response, p))

    def test_failure_is_saved_without_marking_prepared(self):
        with tempfile.TemporaryDirectory() as d, patch.object(runner, 'source', side_effect=RuntimeError('clone failed')):
            with patch.object(sys, 'argv', ['rehearse', '--root', d, '--tc-ref', 'fixture']):
                self.assertEqual(runner.main(), 1)
            state = json.loads((Path(d) / 'rehearsal.json').read_text())
            self.assertFalse(state['prepared'])
            result = json.loads(next(Path(d).glob('evidence/*/results.json')).read_text())
            self.assertEqual(result['status'], 'collection_error')
            self.assertFalse(result['verifier_closed'])

    def test_friend_prompt_is_the_documented_task(self):
        prompt = (ROOT / 'docs/codex-friend-task.txt').read_text().strip()
        self.assertIn('> ' + prompt, (ROOT / 'docs/codex-friend-test.md').read_text())


if __name__ == '__main__':
    unittest.main()
