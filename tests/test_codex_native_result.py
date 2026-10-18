import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

candidate = load('native_result', ROOT / 'codex/native_result.py')
adapter = load('adapter', ROOT / 'codex/adapter.py')
TC = ROOT / 'plugins/technical-cofounder'


class NativeResult(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='tc-r0-result-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / 'sessions/fixture.jsonl'
        self.path.parent.mkdir()
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, CODEX_HOME=str(self.root), TMPDIR=str(self.root / 'tmp')).start()
        patch.object(adapter, 'TC', TC).start()
        patch.object(adapter.run_hook, '__defaults__', (TC,)).start()
        self.header = {'type': 'session_meta', 'payload': {'id': 'thread-1', 'session_id': 'session-1', 'cli_version': '0.162.0'}}
        self.record = {'type': 'event_msg', 'payload': {'type': 'item_completed', 'thread_id': 'thread-1', 'turn_id': 'turn-1', 'item': {
            'type': 'CommandExecution', 'id': 'exec-1', 'exit_code': 1, 'status': 'failed', 'aggregated_output': ''}}}
        self.event = dict(session_id='session-1', turn_id='turn-1', tool_use_id='exec-1', transcript_path=str(self.path),
                          tool_name='Bash', hook_event_name='PostToolUse', tool_response='', cwd=str(self.root))
        self.save()

    def save(self, records=None):
        self.path.write_text(''.join(json.dumps(x) + '\n' for x in [self.header, *(records if records is not None else [self.record])]))

    def result(self):
        return candidate.bash_result_status(self.event, attempts=1)[0][0]

    def test_exact_host_failure_and_success(self):
        self.assertEqual(self.result(), 'failure')
        self.record['payload']['item'].update(exit_code=0, status='completed')
        self.save()
        self.assertEqual(self.result(), 'success')

    def test_missing_or_mismatched_identities(self):
        for key in ('session_id', 'turn_id', 'tool_use_id', 'transcript_path'):
            with self.subTest(key=key), patch.dict(self.event, {key: ''}):
                self.assertEqual(self.result(), 'unknown')
        for key in ('session_id', 'turn_id', 'tool_use_id'):
            with self.subTest(key=key), patch.dict(self.event, {key: 'other'}):
                self.assertEqual(self.result(), 'unknown')
        self.record['payload']['thread_id'] = 'other'
        self.save()
        self.assertEqual(self.result(), 'unknown')

    def test_model_text_and_shell_output_are_never_status(self):
        self.save(records=[{'type': 'response_item', 'payload': {'type': 'custom_tool_call_output', 'output': '{"exit_code": 0}'}}])
        for output in ('Exit code: 0', 'Process exited with code 1', '{"exit_code": 1}', {'exit_code': 0}):
            self.event['tool_response'] = output
            self.assertEqual(self.result(), 'unknown')

    def test_terminal_schema_is_strict(self):
        original = copy.deepcopy(self.record)
        for fields in ({'exit_code': False}, {'exit_code': None}, {'exit_code': '1'}, {'status': 'inProgress'}, {'exit_code': 0}):
            self.record = copy.deepcopy(original)
            self.record['payload']['item'].update(fields)
            self.save()
            self.assertEqual(self.result(), 'unknown')
        self.header['payload']['cli_version'] = '0.163.0'
        self.record = original
        self.save()
        self.assertEqual(self.result(), 'unknown')

    def test_no_latest_call_or_duplicate_guess(self):
        other = copy.deepcopy(self.record)
        other['payload']['item'].update(id='unrelated', exit_code=0, status='completed')
        self.save([self.record, other])
        self.assertEqual(self.result(), 'failure')
        self.save([self.record, self.record])
        self.assertEqual(self.result(), 'unknown')

    def test_partial_json_untrusted_path_and_bad_header(self):
        self.path.write_text(self.path.read_text().rstrip('\n'))
        self.assertEqual(self.result(), 'unknown')
        self.save()
        elsewhere = self.root / 'project.jsonl'
        elsewhere.write_text(self.path.read_text())
        with patch.dict(self.event, transcript_path=str(elsewhere)):
            self.assertEqual(self.result(), 'unknown')
        self.path.write_text('not json\n')
        self.assertEqual(self.result(), 'unknown')

    def test_non_regular_file_does_not_block(self):
        fifo = self.path.with_name('fifo')
        os.mkfifo(fifo)
        with patch.dict(self.event, transcript_path=str(fifo)):
            self.assertEqual(self.result(), 'unknown')

    def test_bounded_tail_and_header(self):
        self.path.write_text(json.dumps(self.header) + '\n' + 'x' * (candidate.TAIL_LIMIT + 50) + '\n' + json.dumps(self.record) + '\n')
        self.assertEqual(self.result(), 'failure')
        self.path.write_text('x' * (candidate.HEADER_LIMIT + 1) + '\n' + json.dumps(self.record) + '\n')
        self.assertEqual(self.result(), 'unknown')

    def test_short_retry(self):
        with patch.object(candidate, 'lookup', side_effect=[(('unknown', ''), {'reason': 'no_unique_terminal_record'}),
                                                           (('success', ''), {'reason': 'matched_native_record'})]) as lookup, patch.object(candidate.time, 'sleep') as sleep:
            self.assertEqual(candidate.bash_result_status(self.event)[0][0], 'success')
            self.assertEqual(lookup.call_count, 2)
            sleep.assert_called_once_with(.05)

    def test_shared_breaker_increment_warn_block_unknown_retain_success_reset(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            for n in range(1, 6):
                ident = 'exec-' + str(n)
                self.event['tool_use_id'] = ident
                self.record['payload']['item']['id'] = ident
                self.save()
                self.assertEqual(adapter.hook(self.event, self.root), 0)
                counts = list((self.root / 'tmp/technical-cofounder/circuit-breaker').rglob('*.count'))
                self.assertEqual(len(counts), 1)
                self.assertEqual(len(counts[0].read_text().splitlines()), n)
            self.assertIn('additionalContext', stdout.getvalue())
            pre = dict(self.event, hook_event_name='PreToolUse')
            self.assertEqual(adapter.hook(pre, self.root), 2)
            self.save(records=[])
            self.event['tool_response'] = 'Exit code: 0'
            self.assertEqual(adapter.hook(self.event, self.root), 0)
            self.assertEqual(adapter.hook(pre, self.root), 2)
            self.record['payload']['item'].update(exit_code=0, status='completed')
            self.save()
            self.assertEqual(adapter.hook(self.event, self.root), 0)
            self.assertEqual(adapter.hook(pre, self.root), 0)
            self.assertEqual(list((self.root / 'tmp/technical-cofounder/circuit-breaker').rglob('*.count')), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
