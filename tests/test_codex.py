"""Codex install and host-boundary regressions; no model/network calls."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


installer = load('codex_installer', ROOT / 'scripts/install_codex.py')
adapter = load('codex_adapter', ROOT / 'codex/adapter.py')


class ResultBoundary(unittest.TestCase):
    def test_explicit_process_results(self):
        for value in ({'exit_code': 1, 'output': 'failure'},):
            self.assertEqual(adapter.result_status(value)[0], 'failure')
        self.assertEqual(adapter.result_status({'exit_code': 0})[0], 'success')
        self.assertEqual(adapter.result_status('Process exit code: 0\nOutput:\nok')[0], 'unknown')

    def test_mcp_errors(self):
        self.assertEqual(adapter.result_status({'isError': True, 'content': [{'text': 'failed'}]})[0], 'failure')
        self.assertEqual(adapter.result_status({'isError': False, 'content': []})[0], 'success')

    def test_ambiguous_results_are_not_success(self):
        for value in (None, {}, {'exit_code': None}, {'exit_code': False}, 'apparently successful', 'Exit code: 0', '{"exit_code": 0}', {'output': 'failure'}, {'isError': 'false'}):
            self.assertEqual(adapter.result_status(value)[0], 'unknown')

    def test_thread_scope_does_not_forge_session_authority(self):
        a = adapter.scoped({'transcript_path': '/tmp/thread-a'})
        b = adapter.scoped({'transcript_path': '/tmp/thread-b'})
        self.assertNotEqual(a['agent_id'], b['agent_id'])
        self.assertNotIn('session_id', a)
        self.assertEqual(adapter.scoped({'agent_id': 'explicit', 'transcript_path': 'x'})['agent_id'], 'explicit')


@unittest.skipIf(sys.platform == 'win32', 'First Codex distribution targets macOS/Linux')
class Install(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tc-codex-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "friend's project"
        self.engine = self.base / 'engine'
        self.engine.mkdir()
        for path, text in {
            'pyproject.toml': '[project]\nname="fixture"\nversion="0.0.0"\n',
            'skills/acing-hyperspace/SKILL.md': '---\nname: acing-hyperspace\ndescription: Fixture router\n---\nUse ${CLAUDE_PLUGIN_ROOT}/bin/example.py\n',
            'hooks/session-start.sh': '#!/bin/sh\necho "engine fixture primer"\n',
            'hyperspace/__init__.py': '',
        }.items():
            target = self.engine / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        for args in (['init', '-q'], ['add', '.'], ['-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture']):
            subprocess.run(['git', '-C', str(self.engine), *args], check=True, capture_output=True)
        self.rev = installer.git(self.engine, 'rev-parse', 'HEAD')
        self.addCleanup(patch.stopall)
        patch.object(installer, 'ENGINE_REV', self.rev).start()
        self.env = dict(os.environ, HOME=str(self.base / 'home'), CODEX_HOME=str(self.base / 'codex-home'), TMPDIR=str(self.base / 'tmp'))
        Path(self.env['HOME']).mkdir()
        Path(self.env['TMPDIR']).mkdir()

    def install(self):
        return installer.install(self.project, self.engine, Path(sys.executable))

    def file(self, rel, data):
        p = self.project / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data)
        return p

    def invoke(self, name, **extra):
        event = dict(hook_event_name=name, cwd=str(self.project), session_id='test-session', tool_name=extra.pop('tool_name', 'fixture_command'), **extra)
        return subprocess.run([sys.executable, '-I', str(self.project / installer.RUNTIME / 'adapter.py'), 'hook', '--project', str(self.project)],
                              input=json.dumps(event), text=True, capture_output=True, env=self.env, timeout=30)

    def test_host_engine_lookup_uses_pinned_snapshot(self):
        engine_script = self.engine / 'bin/drive_map.py'
        engine_script.parent.mkdir()
        engine_script.write_text('# fixture generator\n')
        subprocess.run(['git', '-C', str(self.engine), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.engine), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'generator'], check=True)
        with patch.object(installer, 'ENGINE_REV', installer.git(self.engine, 'rev-parse', 'HEAD')):
            self.install()
        installed = self.project / installer.RUNTIME
        with patch.object(adapter, 'ENGINE', installed / 'hyperspace-engine'):
            env = adapter.environment(self.project)
        command = [sys.executable, '-I', str(installed / 'technical-cofounder/bin/drive_map_pointer.py'), 'locate', str(self.project)]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(installed / 'hyperspace-engine/bin/drive_map.py'))
        env['TC_ENGINE_PLUGIN_ROOT'] = str(self.base / 'missing')
        self.assertEqual(subprocess.run(command, env=env, capture_output=True).returncode, 1)

    def test_pinned_engine_cache_fetch_reuse_and_dirty_refusal(self):
        with patch.object(Path, 'home', return_value=self.base / 'cache-home'), patch.object(installer, 'ENGINE_URL', str(self.engine)):
            cached = installer.cached_engine()
            self.assertEqual(installer.git(cached, 'rev-parse', 'HEAD'), self.rev)
            with patch.object(installer, 'ENGINE_URL', str(self.base / 'nonexistent-remote')):
                self.assertEqual(installer.cached_engine(), cached)
            (cached / 'pyproject.toml').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'not clean'):
                installer.cached_engine()

    def test_install_preserves_existing_content_and_is_idempotent(self):
        self.file('AGENTS.md', 'User rule: keep tests concise.\n')
        self.file('.codex/config.toml', 'model = "my-model"\n[mcp_servers.user_server]\ncommand = "user-command"\n')
        self.file('.codex/hooks.json', json.dumps({'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'echo user-hook'}]}]}}))
        self.file('core_text/user.md', 'existing profile\n')
        first = self.install()
        self.assertEqual(first, self.install())
        self.assertEqual((self.project / 'core_text/user.md').read_text(), 'existing profile\n')
        self.assertTrue((self.project / 'AGENTS.md').read_text().startswith('User rule'))
        config = tomllib.loads((self.project / '.codex/config.toml').read_text())
        self.assertEqual(config['model'], 'my-model')
        self.assertEqual(len(config['mcp_servers']), 3)
        hooks = json.loads((self.project / '.codex/hooks.json').read_text())
        self.assertEqual(len(hooks['hooks']['Stop']), 2)
        for role in ('technical-cofounder', 'engineer', 'devops-lead', 'lead-fde'):
            data = tomllib.loads((self.project / '.codex/agents' / (role + '.toml')).read_text())
            self.assertEqual(data['name'], role)
            self.assertNotIn('model', data)
            self.assertIn('Codex host contract', data['developer_instructions'])
        self.assertLess((self.project / 'AGENTS.md').stat().st_size, 131072)
        self.assertEqual(config['project_doc_max_bytes'], 131072)
        rules = (self.project / installer.RUNTIME / 'workspace-rules.md').read_text()
        self.assertIn(rules, (self.project / 'AGENTS.md').read_text())

    def test_existing_40k_instructions_are_preserved(self):
        original = 'User instructions.\n' * 2300
        self.file('AGENTS.md', original)
        self.install()
        self.assertTrue((self.project / 'AGENTS.md').read_text().startswith(original.rstrip()))

    def test_budget_conflict_refuses_before_writes(self):
        self.file('.codex/config.toml', 'project_doc_max_bytes = 32768\n')
        with self.assertRaisesRegex(ValueError, 'reconcile'):
            self.install()
        self.assertFalse((self.project / installer.RUNTIME).exists())

    def test_larger_user_budget_is_preserved(self):
        self.file('.codex/config.toml', 'project_doc_max_bytes = 262144\n')
        self.install()
        self.assertEqual(tomllib.loads((self.project / '.codex/config.toml').read_text())['project_doc_max_bytes'], 262144)

    def test_hook_definitions_stable_and_execute_from_subdirectory(self):
        self.install()
        first = (self.project / '.codex/hooks.json').read_bytes()
        original = self.project
        self.project = self.base / 'second project'
        self.install()
        self.assertEqual(first, (self.project / '.codex/hooks.json').read_bytes())
        subprocess.run(['git', 'init', '-q', str(original)], check=True)
        sub = original / 'work/nested'
        sub.mkdir(parents=True)
        hooks = json.loads(first)['hooks']['UserPromptSubmit']
        command = hooks[0]['hooks'][0]['command']
        result = subprocess.run(command, shell=True, cwd=sub, env=self.env, text=True,
                                input=json.dumps(dict(hook_event_name='UserPromptSubmit', cwd=str(sub), session_id='stable', prompt='Be brief')),
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('OUTPUT CONTRACT', result.stdout)

    def test_wrong_project_cwd_is_refused(self):
        self.install()
        other = self.base / 'unrelated'
        subprocess.run(['git', 'init', '-q', str(other)], check=True)
        result = subprocess.run([sys.executable, '-I', str(self.project / installer.RUNTIME / 'adapter.py'), 'hook'],
                                input=json.dumps(dict(cwd=str(other), hook_event_name='UserPromptSubmit')),
                                text=True, capture_output=True, env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('does not resolve to this installation', result.stderr)

    def test_trace_is_opt_in_and_contains_no_prompt(self):
        self.install()
        target = self.base / 'trace.jsonl'
        self.invoke('UserPromptSubmit', prompt='PRIVATE-CONTENT')
        self.assertFalse(target.exists())
        self.env['TC_HOOK_TRACE'] = str(target)
        result = self.invoke('UserPromptSubmit', prompt='PRIVATE-CONTENT', source='startup')
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [json.loads(line) for line in target.read_text().splitlines()]
        self.assertEqual(rows[0]['event'], 'UserPromptSubmit')
        self.assertEqual(rows[0]['source'], 'startup')
        self.assertIsInstance(rows[0]['timestamp'], float)
        self.assertNotIn('PRIVATE-CONTENT', target.read_text())
        target.unlink()
        target.symlink_to(self.base / 'must-not-write')
        self.assertEqual(self.invoke('UserPromptSubmit', prompt='brief').returncode, 0)
        self.assertFalse((self.base / 'must-not-write').exists())

    def test_shared_guards_and_trust_gate_are_byte_identical(self):
        self.install()
        for rel in ('hooks/circuit-breaker.sh', 'hooks/lib/normalize-error.sed', 'bin/launch_env.py'):
            self.assertEqual((ROOT / 'plugins/technical-cofounder' / rel).read_bytes(),
                             (self.project / installer.RUNTIME / 'technical-cofounder' / rel).read_bytes())
        for path in (self.project / '.agents/skills').rglob('*.md'):
            self.assertNotIn('${CLAUDE_PLUGIN_ROOT}', path.read_text())
        self.assertEqual(len(list((self.project / '.agents/skills').glob('*/SKILL.md'))), 14)  # 12 TC + one fixture HSE + setup

    def test_edited_managed_file_refuses_without_writes(self):
        self.install()
        manifest = (self.project / installer.MANIFEST).read_bytes()
        self.file('AGENTS.md', 'local change')
        with self.assertRaisesRegex(ValueError, 'changed locally'):
            self.install()
        self.assertEqual((self.project / installer.MANIFEST).read_bytes(), manifest)
        self.assertEqual((self.project / 'AGENTS.md').read_text(), 'local change')

    def test_collision_preflight_does_not_create_runtime(self):
        self.file('.agents/skills/assumption-check/SKILL.md', 'my own skill')
        with self.assertRaisesRegex(ValueError, 'collision'):
            self.install()
        self.assertFalse((self.project / installer.RUNTIME).exists())

    def test_mcp_collision_is_not_overwritten(self):
        self.file('.codex/config.toml', '[mcp_servers.hyperspace]\ncommand="mine"\n')
        with self.assertRaisesRegex(ValueError, 'collision'):
            self.install()
        self.assertFalse((self.project / installer.RUNTIME).exists())

    def test_symlink_is_rejected_before_any_write(self):
        self.project.mkdir()
        elsewhere = self.base / 'elsewhere'
        elsewhere.mkdir()
        (self.project / '.codex').symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.install()
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_dirty_engine_is_rejected(self):
        (self.engine / 'pyproject.toml').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'clean at pinned revision'):
            self.install()
        self.assertFalse(self.project.exists())

    def test_untracked_engine_files_never_installed(self):
        (self.engine / '.env').write_text('FAKE_PRIVATE_DATA=not-a-real-key')
        (self.engine / 'skills/acing-hyperspace/private.txt').write_text('untracked')
        self.install()
        self.assertFalse((self.project / installer.RUNTIME / 'hyperspace-engine/.env').exists())
        self.assertFalse((self.project / '.agents/skills/acing-hyperspace/private.txt').exists())

    def test_existing_instruction_budget_overflow_refuses_before_writes(self):
        original = 'Existing detailed rule.\n' * 6500
        self.file('AGENTS.md', original)
        with self.assertRaisesRegex(ValueError, '131072-byte budget'):
            self.install()
        self.assertEqual((self.project / 'AGENTS.md').read_text(), original)
        self.assertFalse((self.project / installer.RUNTIME).exists())

    def test_unowned_managed_marker_is_refused(self):
        self.file('AGENTS.md', installer.BEGIN + '\nExisting instructions\n' + installer.END)
        with self.assertRaisesRegex(ValueError, 'without installation manifest'):
            self.install()
        self.assertFalse((self.project / installer.RUNTIME).exists())

    def test_missing_hook_dependency_refuses_before_writes(self):
        with patch.object(installer.shutil, 'which', side_effect=lambda name: None if name == 'jq' else '/usr/bin/' + name):
            with self.assertRaisesRegex(ValueError, 'Required tools are missing: jq'):
                self.install()
        self.assertFalse(self.project.exists())

    def test_legacy_profile_not_shadowed(self):
        self.file('user.md', 'legacy profile')
        self.install()
        self.assertFalse((self.project / 'core_text/user.md').exists())

    @unittest.skipUnless(shutil.which('jq') and shutil.which('bash'), 'Shared hooks require bash and jq')
    def test_circuit_breaker_warns_blocks_and_resets(self):
        self.install()
        for n in range(1, 6):
            result = self.invoke('PostToolUse', tool_response={'exit_code': 1, 'output': 'permission denied'})
            self.assertEqual(result.returncode, 0, result.stderr)
            if n == 3:
                self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['hookEventName'], 'PostToolUse')
        blocked = self.invoke('PreToolUse')
        self.assertEqual(blocked.returncode, 2, blocked.stderr)
        self.assertIn('BLOCKED', blocked.stderr)
        self.invoke('PostToolUse', tool_response={'output': 'unknown format'})
        self.assertEqual(self.invoke('PreToolUse').returncode, 2)
        self.invoke('PostToolUse', tool_response={'exit_code': 0})
        self.assertEqual(self.invoke('PreToolUse').returncode, 0)

    @unittest.skipUnless(shutil.which('jq') and shutil.which('bash'), 'Shared hooks require bash and jq')
    def test_agent_isolation_and_mcp_failure(self):
        self.install()
        for _ in range(5):
            self.invoke('PostToolUse', transcript_path='/tmp/child-a', tool_response={'isError': True, 'content': [{'text': 'denied'}]})
        self.assertEqual(self.invoke('PreToolUse', transcript_path='/tmp/child-a').returncode, 2)
        self.assertEqual(self.invoke('PreToolUse', transcript_path='/tmp/child-b').returncode, 0)
        self.invoke('PostToolUse', transcript_path='/tmp/child-b', tool_response={'isError': False})
        self.assertEqual(self.invoke('PreToolUse', transcript_path='/tmp/child-a').returncode, 2)

    @unittest.skipUnless(shutil.which('jq') and shutil.which('bash'), 'Shared hooks require bash and jq')
    def test_prompt_stop_and_retry_guard(self):
        self.install()
        prompt = self.invoke('UserPromptSubmit', prompt='Please be brief.')
        self.assertIn('OUTPUT CONTRACT', prompt.stdout)
        long = self.invoke('Stop', last_assistant_message='word ' * 701, stop_hook_active=False)
        self.assertEqual(json.loads(long.stdout)['decision'], 'block')
        retry = self.invoke('Stop', last_assistant_message='word ' * 701, stop_hook_active=True)
        self.assertFalse(retry.stdout)
        short = self.invoke('Stop', last_assistant_message='done', stop_hook_active=False)
        self.assertFalse(short.stdout)

    def test_patch_additions_use_shared_drive_policy(self):
        self.install()
        self.file('core_text/drive-map.md', '# Map\n')
        old = adapter.TC
        with patch.object(adapter, 'TC', self.project / installer.RUNTIME / 'technical-cofounder'):
            event = {'tool_name': 'apply_patch', 'tool_input': {'input': '*** Begin Patch\n*** Add File: work/new.py\n+pass\n*** End Patch'}, 'cwd': str(self.project)}
            self.assertIn('drive-map', adapter.drive_context(event, self.project))
            event['tool_input']['input'] = '*** Add File: .codex/internal.py\n+pass'
            self.assertEqual(adapter.drive_context(event, self.project), '')
            event['tool_input']['input'] = '*** Add File: ../outside.py\n+pass'
            self.assertEqual(adapter.drive_context(event, self.project), '')

    def test_unprovisioned_mcp_refuses_before_project_interpreter(self):
        self.install()
        evil = self.file('.hyperspace/env/bin/python', '#!/bin/sh\ntouch "' + str(self.base / 'unsafe-executed') + '"\n')
        evil.chmod(0o755)
        result = subprocess.run([sys.executable, '-I', str(self.project / installer.RUNTIME / 'adapter.py'),
                                 'mcp', '--project', str(self.project), '--server', 'team'], env=self.env, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / 'unsafe-executed').exists())


if __name__ == '__main__':
    unittest.main()
