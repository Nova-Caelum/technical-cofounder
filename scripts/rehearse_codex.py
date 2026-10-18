#!/usr/bin/env python3
"""Reproducible R1 collection, never an automatic readiness or verifier pass.

Without --turns: clone exact refs, install twice, provision, doctor, exercise
installed guards and the local worklog. With --turns: reuse that installation
and collect native hook/trust/command/compaction evidence. Live turns must run
from the user's Terminal or a Claude Code shell (plan A4). No trust mutation.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('rehearsal_rpc', HERE / 'codex_rehearsal_rpc.py')
rpc_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpc_module)
RPC = rpc_module.RPC
RUNTIME = '.codex/technical-cofounder'


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def managed(project):
    manifest = json.loads((project / '.codex/technical-cofounder-install.json').read_text())
    observed = {p: sha(project / p) for p in manifest['files']}
    if any(observed[p] != v['sha256'] for p, v in manifest['files'].items()):
        raise ValueError('Managed install changed; reconcile before rehearsal')
    return observed


def run(command, cwd, out, label, env=None, seconds=600, input=None, expected=0):
    result = subprocess.run(command, cwd=cwd, env=env, input=input, capture_output=True,
                            text=True, timeout=seconds)
    (out / (label + '.stdout')).write_text(result.stdout)
    (out / (label + '.stderr')).write_text(result.stderr)
    if result.returncode != expected:
        raise RuntimeError(label + ': exit ' + str(result.returncode) + '; inspect saved output')
    return result


def source(url, ref, dest, out, label):
    if not dest.exists():
        run(['git', 'clone', '--no-hardlinks', url, str(dest)], out, out, label + '-clone')
        run(['git', 'checkout', '--detach', ref], dest, out, label + '-checkout')
    actual = run(['git', 'rev-parse', 'HEAD'], dest, out, label + '-head').stdout.strip()
    wanted = run(['git', 'rev-parse', ref + '^{commit}'], dest, out, label + '-ref').stdout.strip()
    dirty = run(['git', 'status', '--porcelain', '--untracked-files=no'], dest, out, label + '-dirty').stdout
    if actual != wanted or dirty:
        raise ValueError(label + ' source is not clean at requested ref')
    return actual


def counters(tmp):
    return {str(p.relative_to(tmp)): len(p.read_text().splitlines())
            for p in (tmp / 'technical-cofounder/circuit-breaker').rglob('*.count')}


def deterministic(project, out):
    tmp = out / 'tmp'; tmp.mkdir()
    home = out / 'fixture-codex-home'; (home / 'sessions').mkdir(parents=True)
    env = dict(os.environ, TMPDIR=str(tmp) + '/', CODEX_HOME=str(home), TC_HOOK_TRACE=str(out / 'deterministic-hooks.jsonl'))
    base = [sys.executable, '-I', str(project / RUNTIME / 'adapter.py'), 'hook', '--project', str(project)]
    def hook(label, name, expected=0, **values):
        event = dict(hook_event_name=name, cwd=str(project), session_id='rehearsal-fixture', **values)
        return run(base, project, out, label, env, input=json.dumps(event), expected=expected)
    session = hook('session-start', 'SessionStart', source='startup')
    if 'Drive map: core_text/drive-map.md' not in session.stdout or not (project / 'core_text/drive-map.md').is_file():
        raise ValueError('SessionStart did not generate the project drive map')
    freshness = run([sys.executable, '-I', str(project / RUNTIME / 'adapter.py'), 'freshness', '--project', str(project)],
                    project, out, 'freshness', env, seconds=90)
    prompt = hook('prompt', 'UserPromptSubmit', prompt='Be brief.')
    if 'OUTPUT CONTRACT' not in prompt.stdout:
        raise ValueError('Prompt contract missing')
    stop = hook('stop', 'Stop', last_assistant_message='word ' * 701, stop_hook_active=False)
    if json.loads(stop.stdout).get('decision') != 'block':
        raise ValueError('Stop did not request retry')
    if hook('stop-retry', 'Stop', last_assistant_message='word ' * 701, stop_hook_active=True).stdout.strip():
        raise ValueError('Stop retry guard failed')
    transcript = home / 'sessions/fixture.jsonl'
    header = {'type': 'session_meta', 'payload': {'id': 'fixture-thread', 'session_id': 'rehearsal-fixture', 'cli_version': '0.162.0'}}
    counts = []
    for n in range(1, 6):
        event = dict(tool_name='Bash', transcript_path=str(transcript), turn_id='fixture-turn', tool_use_id='fixture-' + str(n), tool_response='Exit code: 0')
        item = {'type': 'event_msg', 'payload': {'type': 'item_completed', 'thread_id': 'fixture-thread', 'turn_id': 'fixture-turn', 'item': {
            'type': 'CommandExecution', 'id': event['tool_use_id'], 'exit_code': 1, 'status': 'failed', 'aggregated_output': 'permission denied'}}}
        transcript.write_text(json.dumps(header) + '\n' + json.dumps(item) + '\n')
        result = hook('breaker-failure-' + str(n), 'PostToolUse', **event)
        current = counters(tmp); counts.append(current)
        if list(current.values()) != [n]:
            raise ValueError('Breaker count mismatch')
        if n == 3 and 'additionalContext' not in result.stdout:
            raise ValueError('Third failure did not warn')
    hook('breaker-blocked', 'PreToolUse', expected=2, **event)
    transcript.write_text(json.dumps(header) + '\n')
    hook('breaker-unknown', 'PostToolUse', **event)
    hook('breaker-still-blocked', 'PreToolUse', expected=2, **event)
    item['payload']['item'].update(exit_code=0, status='completed')
    transcript.write_text(json.dumps(header) + '\n' + json.dumps(item) + '\n')
    hook('breaker-success', 'PostToolUse', **event)
    if counters(tmp):
        raise ValueError('Success did not clear counter')
    hook('breaker-unblocked', 'PreToolUse', **event)
    patch = hook('drive-context', 'PreToolUse', tool_name='apply_patch', tool_input={'input': '*** Add File: work/rehearsal-not-created.py\n+pass'})
    if 'New file: check core_text/drive-map.md for where it belongs.' not in patch.stdout:
        raise ValueError('Drive context missing')
    return {'status': 'pass', 'breaker_counts': counts, 'session_start_bytes': len(session.stdout.encode()),
            'session_start_estimated_tokens': (len(session.stdout.encode()) + 3) // 4,
            'freshness_bytes': len(freshness.stdout.encode()),
            'combined_session_estimated_tokens': (len(session.stdout.encode()) + len(freshness.stdout.encode()) + 3) // 4,
            'trace': 'deterministic-hooks.jsonl', 'scope': 'synthetic adapter dispatch; not native hook execution'}


def worklog(project, out):
    command = [sys.executable, '-I', str(project / RUNTIME / 'adapter.py'), 'mcp', '--project', str(project), '--server', 'team']
    messages = []
    with (out / 'worklog.stderr').open('w') as err:
        rpc = RPC(command, dict(os.environ), err, lambda v: messages.append(v) if v else None, cwd=project, jsonrpc=True)
        try:
            rpc.call('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'tc-rehearsal', 'version': '1'}})
            rpc.send({'method': 'notifications/initialized'})
            token = 'R1-rehearsal-' + uuid.uuid4().hex
            appended = rpc.call('tools/call', {'name': 'worklog_append', 'arguments': {'summary': token, 'author': 'rehearsal', 'tags': ['tc-codex', 'R1']}})
            found = rpc.call('tools/call', {'name': 'worklog_search', 'arguments': {'query': token}})
            if appended.get('isError') or found.get('isError') or token not in json.dumps(found):
                raise ValueError('Worklog append/readback failed')
            return {'status': 'pass', 'token': token, 'append': appended, 'readback': found}
        finally:
            rpc.close()
            write(out / 'worklog-protocol.json', messages)


def trusted_hooks(result, project):
    hooks = [h for group in result.get('data', []) for h in group.get('hooks', [])
             if h.get('sourcePath') == str(project / '.codex/hooks.json')]
    return len(hooks) == 6 and all(h.get('enabled') and h.get('trustStatus') == 'trusted' for h in hooks)


def turn(rpc, thread_id, prompt, seconds=600):
    offset = len(rpc.messages)
    started = rpc.call('turn/start', {'threadId': thread_id, 'input': [{'type': 'text', 'text': prompt}]})
    turn_id = started['turn']['id']
    deadline = time.monotonic() + seconds
    while True:
        done = next((v for v in rpc.messages[offset:] if v.get('method') == 'turn/completed'
                     and v['params'].get('threadId') == thread_id and v['params']['turn']['id'] == turn_id), None)
        if done:
            if done['params']['turn']['status'] != 'completed':
                raise ValueError('Native turn did not complete: ' + turn_id)
            return {'turn_id': turn_id, 'completion': done, 'protocol_offset': offset}
        rpc.receive(deadline)


def instruction_samples(text):
    """Sample actual byte positions, including wrapped rules beyond 32 KiB."""
    total = len(text.encode())
    candidates = []
    offset = 0
    fenced = False
    for number, raw in enumerate(text.splitlines(keepends=True), 1):
        line = raw.rstrip('\r\n')
        if line.lstrip().startswith('```'):
            fenced = not fenced
        if (not fenced and 50 <= len(line) <= 700 and
                not line.lstrip().startswith(('```', '|', '#'))):
            candidates.append({'line': number, 'byte_offset': offset, 'expected': line})
        offset += len(raw.encode())
    chosen = []
    for region, target in enumerate((0.05, 0.5, 0.95)):
        options = [c for c in candidates if region * total / 3 <= c['byte_offset'] < (region + 1) * total / 3
                   and sum(x['expected'].startswith(c['expected'][:24]) for x in candidates) == 1]
        if not options:
            raise ValueError('Cannot sample a unique instruction from each third of AGENTS.md')
        chosen.append(min(options, key=lambda c: abs(c['byte_offset'] - total * target)))
    return chosen


def start_native_thread(rpc, project):
    # Review MCP requests individually; never grant sandbox escapes or fabricate
    # user approval. Unhandled interactive requests still fail closed in RPC.
    policy = {'granular': {'sandbox_approval': False, 'rules': False,
                          'mcp_elicitations': True, 'request_permissions': False,
                          'skill_approval': False}}
    result = rpc.call('thread/start', {
        'cwd': str(project), 'model': 'gpt-6.1-sol',
        'approvalPolicy': policy, 'approvalsReviewer': 'auto_review',
        'sandbox': 'workspace-write'}, seconds=120)
    sandbox = result.get('sandbox', {})
    if (result.get('approvalPolicy') != policy or
            result.get('approvalsReviewer') != 'auto_review' or
            sandbox.get('type') != 'workspaceWrite' or
            sandbox.get('networkAccess') is not False or
            sandbox.get('writableRoots')):
        raise ValueError('Native thread did not retain the requested review/sandbox boundary')
    return result


def live(project, second, out):
    tmp = out / 'live-tmp'; tmp.mkdir()
    trace = out / 'native-hooks.jsonl'
    env = dict(os.environ, TMPDIR=str(tmp) + '/', TC_HOOK_TRACE=str(trace))
    data = {'status': 'collecting', 'turns': [], 'counter_changes': []}
    last = None
    def observe(value):
        nonlocal last
        now = counters(tmp)
        if now != last:
            data['counter_changes'].append({'timestamp': time.time(), 'counts': now})
            last = now
        if value:
            with (out / 'protocol.jsonl').open('a') as stream:
                stream.write(json.dumps(value) + '\n')
    with (out / 'native.stderr').open('w') as err:
        rpc = RPC(['codex', 'app-server', '--stdio'], env, err, observe, cwd=project)
        try:
            # Granular approvals are experimental in the native app-server API.
            rpc.call('initialize', {'clientInfo': {'name': 'tc_r1_rehearsal', 'version': '1'},
                                    'capabilities': {'experimentalApi': True}})
            rpc.send({'method': 'initialized'})
            data['hooks'] = rpc.call('hooks/list', {'cwds': [str(project), str(second)]})
            if not trusted_hooks(data['hooks'], project):
                data['status'] = 'requires_hook_trust'
                data['action'] = 'Review project and six generated definitions in codex /hooks, then rerun; no trust was changed.'
                return data
            data['second_project_trusted'] = trusted_hooks(data['hooks'], second)
            thread = start_native_thread(rpc, project)
            data['native_policy'] = {k: thread[k] for k in ('approvalPolicy', 'approvalsReviewer', 'sandbox')}
            tid = thread['thread']['id']; data['thread_id'] = tid
            for command in ('false', 'true'):
                prompt = ('R1 hook probe. Make exactly ONE exec_command shell call with command ' + repr(command) +
                          '. Then reply done. Do not inspect files, retry, delegate, or call any other tool. This expected command result is the test.')
                result = turn(rpc, tid, prompt)
                result.update(label=command, counters_after=counters(tmp))
                data['turns'].append(result)
            patch_prompt = ('Use apply_patch to add work/r1-drive-probe.py containing probe = True. '
                            'Use the project drive map to place this file. Do not use a shell to create it. '
                            'Report any drive-map context supplied by the hook, then stop.')
            data['turns'].append(dict(label='apply-patch-drive', **turn(rpc, tid, patch_prompt)))
            stop_prompt = ('Controlled Stop-hook test in a disposable project. For this test only, '
                           'make the first final reply contain exactly 710 numbered words, from word1 to word710, '
                           'separated by spaces. Do not write a file or use tools. The hook is expected to reject '
                           'this first response; if it asks for a retry, reply with the single word done. '
                           'Do not disable or edit any hook.')
            data['turns'].append(dict(label='stop-retry', **turn(rpc, tid, stop_prompt)))
            # Quote actual generated instructions, not a substitute AGENTS fixture.
            instructions = (project / 'AGENTS.md').read_text()
            chosen = instruction_samples(instructions)
            data['instruction_bytes'] = len(instructions.encode())
            data['instruction_samples'] = chosen
            quote_prompt = ('Without reading any file or using any tool, quote the complete original instruction line beginning with each of these prefixes: ' +
                            json.dumps([sample['expected'][:24] for sample in chosen]) + '. If unavailable say so; do not guess.')
            data['turns'].append(dict(label='instructions-before-compact', **turn(rpc, tid, quote_prompt)))
            offset = len(rpc.messages)
            rpc.call('thread/compact/start', {'threadId': tid})
            deadline = time.monotonic() + 600
            while not any(v.get('method') == 'item/completed' and v.get('params', {}).get('threadId') == tid
                          and v['params'].get('item', {}).get('type') == 'contextCompaction' for v in rpc.messages[offset:]):
                rpc.receive(deadline)
            data['compaction_observed'] = True
            data['turns'].append(dict(label='instructions-after-compact', **turn(rpc, tid, quote_prompt)))
            if data['second_project_trusted']:
                other = start_native_thread(rpc, second)
                data['turns'].append(dict(label='second-project', **turn(rpc, other['thread']['id'], 'Make one exec_command call with command true, then reply done. No other tools.')))
            # The source-controlled prompt is shared verbatim with friend-test step 4.
            friend_path = project.parent / 'sources/tc/docs/codex-friend-task.txt'
            data['friend_task_sha256'] = sha(friend_path)
            friend_prompt = ('This is the R1 staged rehearsal. The engine is already provisioned with judge=none; '
                             'preserve that setting in this row. Judge, tier routing and complete setup are later '
                             'rows, so record those gaps explicitly. Stay inside this disposable project.\n\n' +
                             friend_path.read_text().removeprefix('Run $tc-setup, preserving my existing profile. Then '))
            data['friend_staging'] = 'R1 omits setup sentence per plan; shared build/verify task unchanged'
            data['friend_effective_prompt_sha256'] = hashlib.sha256(friend_prompt.encode()).hexdigest()
            data['turns'].append(dict(label='friend-step-4', **turn(rpc, tid, friend_prompt, seconds=1200)))
            data['status'] = 'collected_needs_review'
            return data
        except Exception as exc:
            data.update(status='collection_error', error=type(exc).__name__ + ': ' + str(exc))
            raise
        finally:
            rpc.close()
            write(out / 'live-collection.json', data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.home() / 'NovaCaelum_code/tc-rehearsal/r1')
    parser.add_argument('--tc-ref', required=True)
    parser.add_argument('--engine-ref', default='45472d4260b65ecec1f194bdd044fba9880f42e4')
    parser.add_argument('--tc-source', default='https://github.com/Nova-Caelum/technical-cofounder.git')
    parser.add_argument('--engine-source', default='https://github.com/Nova-Caelum/hyperspace-engine.git')
    parser.add_argument('--probes', default='R1')
    parser.add_argument('--turns', action='store_true')
    parser.add_argument('--runner', choices=['user-terminal', 'claude-code-shell'])
    args = parser.parse_args()
    if args.probes != 'R1':
        parser.error('Only R1 is implemented; later rows must add explicit probes')
    if args.turns and (not args.runner or os.environ.get('CODEX_THREAD_ID') or os.environ.get('CODEX_SANDBOX')):
        parser.error('A4: --turns requires an external Terminal/Claude Code runner, never the Codex sandbox')
    root = args.root.expanduser().resolve()
    if any((parent / '.obsidian').is_dir() for parent in (root, *root.parents)):
        parser.error('Rehearsal executable projects must be outside the synced vault')
    if root.exists() and not (root / 'rehearsal.json').exists() and any(root.iterdir()):
        parser.error('Use an empty or previously owned rehearsal root')
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / 'rehearsal.json'
    if not state_path.exists():
        write(state_path, {'requested_refs': {'tc': args.tc_ref, 'engine': args.engine_ref}, 'prepared': False})
    out = root / 'evidence' / ('R1-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
    out.mkdir(parents=True)
    print('Evidence:', out, flush=True)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    data = {'row': 'R1', 'status': 'collecting', 'runner': args.runner or 'codex-deterministic',
            'script_sha256': sha(Path(__file__)), 'requested_refs': {'tc': args.tc_ref, 'engine': args.engine_ref},
            'verifier_closed': False}
    project, second = root / 'project', root / 'second-project'
    trust_path = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'config.toml'
    data['global_config_before'] = sha(trust_path) if trust_path.exists() else None
    try:
        if args.turns:
            if state.get('requested_refs') != data['requested_refs'] or not state.get('prepared'):
                raise ValueError('Prepare these exact refs first without --turns')
            data['versions'] = {'codex': run(['codex', '--version'], root, out, 'codex-version').stdout.strip(), 'python': sys.version}
            data['managed_before'] = managed(project)
            data['managed_second_before'] = managed(second)
            data['live'] = live(project, second, out)
            data['managed_unchanged'] = data['managed_before'] == managed(project) and data['managed_second_before'] == managed(second)
            data['status'] = data['live']['status']
        else:
            if state and state.get('requested_refs') != data['requested_refs']:
                raise ValueError('Use a new root for different refs; preserve the previous rehearsal')
            write(state_path, {'requested_refs': data['requested_refs'], 'prepared': False})
            data['versions'] = {'codex': run(['codex', '--version'], root, out, 'codex-version').stdout.strip(), 'python': sys.version, 'platform': sys.platform}
            sources = root / 'sources'; sources.mkdir(exist_ok=True)
            tc, engine = sources / 'tc', sources / 'engine'
            data['revisions'] = {'tc': source(args.tc_source, args.tc_ref, tc, out, 'tc'),
                                 'engine': source(args.engine_source, args.engine_ref, engine, out, 'engine')}
            data['fresh_project'] = not (project / '.codex/technical-cofounder-install.json').exists()
            for p, label in ((project, 'primary'), (second, 'secondary')):
                p.mkdir(exist_ok=True)
                run(['git', 'init', '-q', str(p)], root, out, label + '-git')
                command = [sys.executable, str(tc / 'scripts/install_codex.py'), '--project', str(p), '--engine-source', str(engine)]
                run(command, root, out, label + '-install')
                before = managed(p)
                run(command, root, out, label + '-reinstall')
                if before != managed(p):
                    raise ValueError('Reinstall changed managed files')
                run([sys.executable, '-I', str(p / RUNTIME / 'adapter.py'), 'provision', '--project', str(p), '--judge', 'none'], p, out, label + '-provision')
                run([str(p / '.hyperspace/env/bin/hyperspace'), 'doctor', '--dir', str(p)], p, out, label + '-doctor')
            data['hook_definitions_identical'] = (project / '.codex/hooks.json').read_bytes() == (second / '.codex/hooks.json').read_bytes()
            if not data['hook_definitions_identical']:
                raise ValueError('Hook definitions differ across projects')
            data['deterministic'] = deterministic(project, out)
            data['worklog'] = worklog(project, out)
            data['managed'] = managed(project)
            data['status'] = 'deterministic_pass_live_pending'
            write(state_path, {'requested_refs': data['requested_refs'], 'prepared': True, 'evidence': str(out), 'revisions': data['revisions']})
    except Exception as exc:
        data['status'] = 'collection_error'
        data['error'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        data['global_config_after'] = sha(trust_path) if trust_path.exists() else None
        data['global_config_unchanged'] = data['global_config_before'] == data['global_config_after']
        if not data['global_config_unchanged']:
            data['status'] = 'collection_error'
            data['error'] = 'Global configuration changed during collection; investigate before accepting evidence'
        write(out / 'results.json', data)
    print(data['status'] + ': ' + str(out / 'results.json'), flush=True)
    return 1 if data['status'] in ('collection_error', 'requires_hook_trust') else 0


if __name__ == '__main__':
    sys.exit(main())
