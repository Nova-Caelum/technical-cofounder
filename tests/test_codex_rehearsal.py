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

    def test_live_negotiates_granular_capability_before_starting_thread(self):
        events = []
        def call(method, params, **kwargs):
            events.append(method)
            if method == 'initialize':
                self.assertIs(params.get('capabilities', {}).get('experimentalApi'), True)
                return {}
            if method == 'hooks/list':
                self.assertEqual(events, ['initialize', 'initialized', 'hooks/list'])
                return {}
            if method == 'thread/start':
                self.assertIn('granular', params['approvalPolicy'])
                return {'thread': {'id': 'fixture'}, 'approvalPolicy': params['approvalPolicy'],
                        'approvalsReviewer': 'auto_review',
                        'sandbox': {'type': 'workspaceWrite', 'networkAccess': False, 'writableRoots': []}}
            self.fail('Unexpected RPC: ' + method)
        rpc = Mock()
        rpc.call.side_effect = call
        rpc.send.side_effect = lambda message: events.append(message['method'])
        with tempfile.TemporaryDirectory() as d, patch.object(runner, 'RPC', return_value=rpc), \
                patch.object(runner, 'trusted_hooks', return_value=True), \
                patch.object(runner, 'check_runtime', return_value={}), \
                patch.object(runner, 'turn', side_effect=RuntimeError('stop before model turn')):
            root = Path(d)
            out = root / 'R1-fixture'; out.mkdir()
            with self.assertRaisesRegex(RuntimeError, 'stop before model turn'):
                runner.live(root / 'project', root / 'second', out)
            self.assertEqual(events, ['initialize', 'initialized', 'hooks/list', 'thread/start'])
            saved = json.loads((out / 'live-collection.json').read_text())
            self.assertEqual(saved['turns'], [])
            rpc.close.assert_called_once()

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

    def test_each_collection_uses_fresh_paths_and_fails_closed_on_collision(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            first = runner.fixture_scope(project, 'R1-first')
            second = runner.fixture_scope(project, 'R1-second')
            self.assertNotEqual(first['drive_path'], second['drive_path'])
            self.assertNotEqual(first['friend_dir'], second['friend_dir'])
            self.assertNotEqual(first['external_id'], second['external_id'])
            old = project / first['friend_dir']; old.mkdir(parents=True)
            (old / 'keep.txt').write_text('old evidence')
            with self.assertRaisesRegex(ValueError, 'exists'):
                runner.fixture_scope(project, 'R1-first')
            self.assertEqual((old / 'keep.txt').read_text(), 'old evidence')
            with self.assertRaises(ValueError):
                runner.fixture_scope(project, '../escape')
            (project / 'work' / 'r1-R1-second').symlink_to('/tmp')
            with self.assertRaisesRegex(ValueError, 'exists'):
                runner.fixture_scope(project, 'R1-second')

    def test_friend_task_files_graph_before_build_and_uses_registered_tests(self):
        prompt = (ROOT / 'docs/codex-friend-task.txt').read_text()
        self.assertIn('before creating implementation or test files', prompt)
        self.assertIn('check_id=tests', prompt)
        self.assertIn('pytest', prompt)
        self.assertIn('read back', prompt)
        scope = {'friend_dir': 'work/unique/greeting', 'external_id': 'R1-unique', 'drive_path': 'work/unique/drive.py'}
        staged = runner.friend_prompt(scope)
        self.assertIn('work/unique/greeting', staged)
        self.assertIn('R1-unique', staged)
        self.assertNotIn('Run $tc-setup', staged)
        self.assertIn('judge=none', staged)

    def test_check_environment_rejects_symlink_before_install(self):
        with tempfile.TemporaryDirectory() as d, patch.object(runner, 'run') as run:
            root = Path(d); project = root / 'project'; project.mkdir()
            (project / '.venv').symlink_to('/tmp', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                runner.prepare_checks(project, root)
            run.assert_not_called()

    def test_check_environment_preserves_unowned_venv(self):
        with tempfile.TemporaryDirectory() as d, patch.object(runner, 'run') as run:
            root = Path(d); venv = root / '.venv'; venv.mkdir()
            (venv / 'keep').write_text('user-owned environment')
            with self.assertRaisesRegex(ValueError, 'unowned'):
                runner.prepare_checks(root, root)
            run.assert_not_called()
            self.assertEqual((venv / 'keep').read_text(), 'user-owned environment')

    def test_preflight_uses_installed_verifier_and_checks_version(self):
        selected = {'python': '/project/.venv/bin/python3', 'tests': ['-m', 'pytest', '-q']}
        with tempfile.TemporaryDirectory() as d, patch.object(runner, 'run') as run:
            root = Path(d)
            run.side_effect = [Mock(stdout=json.dumps(selected)), Mock(stdout='pytest 8.4.2\n')]
            self.assertEqual(runner.check_runtime(root, root)['pytest_version'], 'pytest 8.4.2')
            self.assertIn('_resolve_interpreter', run.call_args_list[0].args[0][-1])
            self.assertEqual(run.call_args_list[1].args[0], [selected['python'], '-I', '-m', 'pytest', '--version'])
            run.side_effect = [Mock(stdout=json.dumps(selected)), Mock(stdout='pytest 7.0.0\n')]
            with self.assertRaisesRegex(ValueError, 'prepare-checks'):
                runner.check_runtime(root, root)
            run.side_effect = [Mock(stdout=json.dumps(dict(selected, tests=['-m', 'unittest'])))]
            with self.assertRaisesRegex(ValueError, 'command changed'):
                runner.check_runtime(root, root)

    def test_missing_test_runner_stops_before_native_server(self):
        with tempfile.TemporaryDirectory() as d, patch.object(runner, 'RPC') as rpc, \
                patch.object(runner, 'check_runtime', side_effect=ValueError('pytest missing')):
            root = Path(d)
            with self.assertRaisesRegex(ValueError, 'pytest missing'):
                runner.live(root / 'project', root / 'second', root)
            rpc.assert_not_called()

    def test_friend_prompt_is_the_documented_task(self):
        prompt = (ROOT / 'docs/codex-friend-task.txt').read_text().strip()
        self.assertIn('> ' + prompt, (ROOT / 'docs/codex-friend-test.md').read_text())


if __name__ == '__main__':
    unittest.main()
