#!/usr/bin/env python3
"""Codex host boundary. Shared TC/HSE policy remains in the installed snapshot."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
TC = ROOT / 'technical-cofounder'
ENGINE = ROOT / 'hyperspace-engine'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def host_text(text):
    text = text.replace('/technical-cofounder-setup:start', '$tc-setup')
    text = re.sub(r'/(?:technical-cofounder|hyperspace-engine):([\w-]+)', r'$\1', text)
    return text.replace('Claude Code', 'Codex').replace('claude auth login', 'codex login')


def environment(project, root=TC):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project), CLAUDE_PLUGIN_ROOT=str(root))
    # Never put Codex telemetry/stamps into the Claude user's directories.
    env['TC_ENGINE_PLUGIN_ROOT'] = str(ENGINE)
    env['CLAUDE_PLUGIN_DATA'] = str(Path(env.get('CODEX_HOME', Path.home() / '.codex')) / 'technical-cofounder')
    return env


def result_status(value):
    """Return (success|failure|unknown, error). No speculative success resets.

    Codex tool_response is a JSON value, not a stable universal result schema.
    Only explicit terminal process status or MCP isError is authoritative here.
    """
    if isinstance(value, dict):
        if isinstance(value.get('isError'), bool):
            return ('failure', json.dumps(value.get('content', []))) if value['isError'] else ('success', '')
        code = value.get('exit_code')
        if isinstance(code, int) and not isinstance(code, bool):
            return ('failure', str(value.get('output', value.get('stderr', 'process failed')))) if code else ('success', '')
        return 'unknown', ''
    return 'unknown', ''


def trace(event, phase, **metadata):
    """Opt-in metadata only: never prompts, command text, output or credentials."""
    target = os.environ.get('TC_HOOK_TRACE')
    if not target:
        return
    entry = dict(timestamp=time.time(), event=event.get('hook_event_name'),
                 source=event.get('source'), phase=phase,
                 session_id=event.get('session_id'), turn_id=event.get('turn_id'),
                 tool_use_id=event.get('tool_use_id'), **metadata)
    try:
        fd = os.open(target, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            import stat
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError('trace destination is not a regular file')
            os.write(fd, (json.dumps(entry) + '\n').encode())
        finally:
            os.close(fd)
    except OSError as exc:
        print('TC hook trace unavailable: ' + type(exc).__name__, file=sys.stderr)


def project_root(explicit, event=None):
    if explicit:
        return explicit.resolve()
    cwd = (event or {}).get('cwd') or os.getcwd()
    root = Path(subprocess.check_output(['git', '-C', cwd, 'rev-parse', '--show-toplevel'], text=True).strip()).resolve()
    if root != ROOT.parent.parent:
        raise ValueError('Hook cwd does not resolve to this installation')
    return root


def scoped(event):
    event = dict(event)
    # Codex subagents share session_id. Their transcript paths identify threads.
    # Keep the session key intact: missing session_id never gains block authority.
    if not event.get('agent_id') and event.get('transcript_path'):
        event['agent_id'] = hashlib.sha256(str(event['transcript_path']).encode()).hexdigest()[:24]
    return event


def run_hook(script, event, project, root=TC):
    result = subprocess.run(['bash', str(root / 'hooks' / script)], input=json.dumps(event),
                            text=True, capture_output=True, cwd=project, env=environment(project, root), timeout=20)
    return result.returncode, result.stdout, result.stderr


def drive_context(event, project):
    policy = module('tc_drive_write', TC / 'hooks/drive_map_write.py')
    payload = event.get('tool_input') or {}
    targets = []
    if event.get('tool_name') == 'Write' and payload.get('file_path'):
        targets.append(payload['file_path'])
    patch = payload.get('input', payload.get('patch', payload.get('command', '')))
    if event.get('tool_name') in ('apply_patch', 'functions.apply_patch') and isinstance(patch, str):
        targets.extend(re.findall(r'^\*\*\* Add File: (.+)$', patch, re.M))
    for target in targets:
        path = Path(target)
        if not path.is_absolute():
            path = Path(event.get('cwd') or project) / path
        if not path.exists() and policy.under_a_map(path, project):
            return policy.LINE
    return ''


def hook(event, project):
    event = scoped(event)
    trace(event, 'entered', **({'stop_hook_active': event.get('stop_hook_active'),
          'response_words': len(event['last_assistant_message'].split()) if isinstance(event.get('last_assistant_message'), str) else None}
          if event.get('hook_event_name') == 'Stop' else {}))
    name = event.get('hook_event_name')
    scripts = {'SessionStart': ['session-preload.sh'], 'UserPromptSubmit': ['concision-budget.sh', 'concision-contract.sh'],
               'Stop': ['concision-stop.sh'], 'PreToolUse': ['circuit-breaker.sh'], 'PostToolUse': ['circuit-breaker.sh']}.get(name, [])
    if name == 'PostToolUse':
        if event.get('tool_name') == 'Bash':
            native = module('tc_native_result', ROOT / 'native_result.py')
            (status, error), details = native.bash_result_status(event)
            trace(event, 'result', status=status, **details)
        else:
            status, error = result_status(event.get('tool_response'))
            trace(event, 'result', status=status, reason='structured_response')
        if status == 'unknown':
            print('TC circuit breaker: unrecognized tool result; counters retained.', file=sys.stderr)
            return 0
        if status == 'failure':
            event.update(hook_event_name='PostToolUseFailure', error=error)
    if name == 'Stop' and not isinstance(event.get('last_assistant_message'), str):
        print('TC concision: no assistant message supplied; cannot count words.', file=sys.stderr)
        return 0
    outputs = []
    for script in scripts:
        code, out, err = run_hook(script, event, project)
        trace(event, 'handler_finished', handler=script, exit_code=code)
        if err:
            print(host_text(err), file=sys.stderr, end='')
        if code == 2:
            return 2
        if code:
            print('TC hook failed: ' + script, file=sys.stderr)
        if out.strip():
            outputs.append(host_text(out.strip()))
    if name == 'SessionStart':
        code, out, err = run_hook('session-start.sh', event, project, ENGINE)
        trace(event, 'handler_finished', handler='session-start.sh', exit_code=code)
        if out.strip():
            outputs.append(host_text(out.strip()).replace('${CLAUDE_PLUGIN_ROOT}', str(ENGINE)))
        if err:
            print(host_text(err), file=sys.stderr, end='')
    if name == 'PreToolUse':
        context = drive_context(event, project)
        if context:
            trace(event, 'drive_context', injected=True)
            outputs.append(json.dumps({'hookSpecificOutput': {'hookEventName': name, 'additionalContext': context}}))
    # Prompt/session hooks accept plain text. Tool hooks require one JSON object.
    if name in ('SessionStart', 'UserPromptSubmit'):
        print('\n\n'.join(outputs))
    else:
        contexts = []
        for out in outputs:
            obj = json.loads(out)
            if obj.get('decision') == 'block':
                trace(event, 'decision', decision='block')
                print(json.dumps(obj))
                return 0
            context = obj.get('hookSpecificOutput', {}).get('additionalContext')
            if context:
                contexts.append(context)
        if contexts:
            print(json.dumps({'hookSpecificOutput': {'hookEventName': name, 'additionalContext': '\n'.join(contexts)}}))
    return 0


def freshness(project):
    os.environ.update(environment(project))
    shared = module('tc_cli_freshness', TC / 'bin/cli_freshness.py')
    shared.TOOLS = tuple(t for t in shared.TOOLS if t.key not in ('claude', 'git')) + (
        shared.Tool('codex', 'Codex CLI', 'openai/codex', brew='codex'),)
    original = shared.tag_version
    shared.tag_version = lambda url: original(url.replace('/tag/rust-v', '/tag/v'))
    return shared.main()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['hook', 'freshness', 'mcp', 'provision'])
    parser.add_argument('--project', type=Path)
    parser.add_argument('--server', choices=['team', 'hyperspace'])
    parser.add_argument('--judge', choices=['none', 'codex'], default='none')
    args = parser.parse_args()
    event = json.load(sys.stdin) if args.action == 'hook' else None
    project = project_root(args.project, event)
    os.chdir(project)
    if args.action == 'hook':
        return hook(event, project)
    if args.action == 'freshness':
        return freshness(project)
    if args.action == 'mcp':
        if not args.server:
            parser.error('--server is required for mcp')
        target = [str(TC / 'mcp/server.py')] if args.server == 'team' else ['-P', '-m', 'hyperspace.mcp']
        # System Python enters the unchanged provenance gate BEFORE project code.
        os.execve(sys.executable, [sys.executable, '-I', str(TC / 'bin/launch_env.py'), 'run', *target], environment(project))
    if args.action == 'provision':
        os.execve(sys.executable, [sys.executable, '-I', str(ENGINE / 'bin/hyperspace_setup.py'),
                  '--dir', str(project), '--provision', '--judge', args.judge], environment(project, ENGINE))
    return 0


if __name__ == '__main__':
    try:
        code = main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print('TC Codex adapter: ' + type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
        code = 1
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)  # freshness can have a bounded background lookup still running
