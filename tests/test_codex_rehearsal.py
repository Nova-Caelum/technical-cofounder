"""Collector safety boundaries and local transport; never starts Codex/model turns."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

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

    def test_native_review_boundary_is_checked_before_turns(self):
        import copy
        policy = {'granular': {'sandbox_approval': False, 'rules': False,
                              'mcp_elicitations': True, 'request_permissions': False,
                              'skill_approval': False}}
        expected = {'approvalPolicy': policy, 'approvalsReviewer': 'auto_review',
                    'sandbox': {'type': 'workspaceWrite', 'networkAccess': False, 'writableRoots': []},
                    'thread': {'id': 'fixture'}}
        rpc = Mock()
        rpc.call.return_value = expected
        self.assertEqual(runner.start_native_thread(rpc, Path('/tmp/project')), expected)
        requested = rpc.call.call_args.args[1]
        self.assertEqual(requested['approvalPolicy'], policy)
        self.assertEqual(requested['approvalsReviewer'], 'auto_review')
        self.assertEqual(requested['sandbox'], 'workspace-write')
        cases = [dict(approvalPolicy='never'), dict(approvalsReviewer='user'),
                 dict(sandbox={'type': 'dangerFullAccess'}),
                 dict(sandbox={'type': 'workspaceWrite', 'networkAccess': True, 'writableRoots': []}),
                 dict(sandbox={'type': 'workspaceWrite', 'networkAccess': False, 'writableRoots': ['/other']})]
        for change in cases:
            with self.subTest(change=change):
                result = copy.deepcopy(expected); result.update(change)
                rpc.call.return_value = result
                with self.assertRaisesRegex(ValueError, 'boundary'):
                    runner.start_native_thread(rpc, Path('/tmp/project'))

    def test_instruction_samples_cover_bytes_not_long_line_subset(self):
        # Persona paragraphs are long; workspace rules are wrapped to 70 columns.
        # The old >90-character filter silently selected only the persona.
        text = 'Persona paragraph ' + 'x' * 150 + '\n'
        text += ''.join(f'Rule {i:04d}: ' + 'wrapped instruction content ' * 2 + '\n' for i in range(650))
        samples = runner.instruction_samples(text)
        size = len(text.encode())
        self.assertGreater(size, 40000)
        for region, sample in enumerate(samples):
            self.assertGreaterEqual(sample['byte_offset'], region * size / 3)
            self.assertLess(sample['byte_offset'], (region + 1) * size / 3)
            self.assertEqual(text.splitlines()[sample['line'] - 1], sample['expected'])
        self.assertGreater(samples[-1]['byte_offset'], 32768)
        with self.assertRaisesRegex(ValueError, 'each third'):
            runner.instruction_samples('too short')

    def test_friend_prompt_is_the_documented_task(self):
        prompt = (ROOT / 'docs/codex-friend-task.txt').read_text().strip()
        self.assertIn('> ' + prompt, (ROOT / 'docs/codex-friend-test.md').read_text())


if __name__ == '__main__':
    unittest.main()
