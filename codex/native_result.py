"""Version-gated exact-call lookup for observed Codex 0.162.0 rollouts.

Rollouts are not a stable API. Unknown schema, absent records, or unmatched
identities retain counters. No status is inferred from shell stdout.
"""
import json
import os
from pathlib import Path
import stat
import time

HEADER_LIMIT = 256 * 1024
TAIL_LIMIT = 2 * 1024 * 1024


def lookup(event):
    info = {'reason': 'missing_identity'}
    if not all(isinstance(event.get(k), str) and event[k]
               for k in ('session_id', 'turn_id', 'tool_use_id', 'transcript_path')):
        return ('unknown', ''), info
    try:
        path = Path(event['transcript_path']).resolve()
        home = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')).resolve()
    except (OSError, ValueError, RuntimeError):
        return ('unknown', ''), {'reason': 'invalid_transcript_path'}
    if not any(path.is_relative_to(home / name) for name in ('sessions', 'archived_sessions')):
        return ('unknown', ''), {'reason': 'outside_session_store'}
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return ('unknown', ''), {'reason': 'not_regular_file'}
            header = stream.readline(HEADER_LIMIT + 1)
            if len(header) > HEADER_LIMIT or not header.endswith(b'\n'):
                return ('unknown', ''), {'reason': 'invalid_header'}
            meta = json.loads(header)
            payload = meta.get('payload', {})
            if meta.get('type') != 'session_meta' or not isinstance(payload, dict):
                return ('unknown', ''), {'reason': 'invalid_header'}
            if payload.get('cli_version') != '0.162.0':
                return ('unknown', ''), {'reason': 'unsupported_version'}
            thread = payload.get('id')
            if not isinstance(thread, str) or not thread or payload.get('session_id') != event['session_id']:
                return ('unknown', ''), {'reason': 'session_mismatch'}
            size = os.fstat(stream.fileno()).st_size
            offset = max(len(header), size - TAIL_LIMIT)
            stream.seek(offset)
            tail = stream.read(TAIL_LIMIT)
            if offset > len(header):
                tail = tail.partition(b'\n')[2]  # discard any partial first record
    except (OSError, ValueError, TypeError, AttributeError):
        return ('unknown', ''), {'reason': 'unreadable_transcript'}
    matches = []
    for line in tail.splitlines(keepends=True):
        if not line.endswith(b'\n'):
            continue
        try:
            record = json.loads(line)
            p = record.get('payload', {})
            if record.get('type') != 'event_msg' or not isinstance(p, dict) or p.get('type') != 'item_completed':
                continue
            item = p.get('item', {})
            if not isinstance(item, dict) or item.get('type') != 'CommandExecution':
                continue
            if (p.get('thread_id'), p.get('turn_id'), item.get('id')) != (thread, event['turn_id'], event['tool_use_id']):
                continue
            matches.append(item)
        except (ValueError, TypeError, AttributeError):
            continue
    if len(matches) != 1:
        return ('unknown', ''), {'reason': 'no_unique_terminal_record', 'matches': len(matches)}
    item = matches[0]
    code = item.get('exit_code')
    if type(code) is not int or item.get('status') != ('failed' if code else 'completed'):
        return ('unknown', ''), {'reason': 'invalid_terminal_status'}
    output = item.get('aggregated_output')
    error = output[:8000] if isinstance(output, str) and output else 'process exited with code ' + str(code)
    return (('failure', error) if code else ('success', '')), {'reason': 'matched_native_record', 'exit_code': code}


def bash_result_status(event, attempts=6):
    # A short bounded retry allows a buffered record to appear. This cannot make
    # an absent or changed host contract pass; live proof is still required.
    for attempt in range(attempts):
        result, info = lookup(event)
        if result[0] != 'unknown' or info['reason'] != 'no_unique_terminal_record':
            break
        if attempt + 1 < attempts:
            time.sleep(.05)
    return result, dict(info, attempts=attempt + 1)
