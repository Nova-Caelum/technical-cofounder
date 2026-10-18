"""Bounded stdio RPC with notification collection and approval refusal."""
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time

class RPC:
    def __init__(self, command, env, stderr, observe, cwd=None, jsonrpc=False):
        self.jsonrpc = jsonrpc
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=stderr, text=True, env=env,
            start_new_session=True, cwd=cwd)
        self.queue = queue.Queue()
        self.observe = observe
        self.next_id = 0
        self.messages = []
        def read():
            try:
                for line in self.process.stdout:
                    self.queue.put(json.loads(line))
            except Exception as exc:
                self.queue.put({'reader_error': str(exc)})
            finally:
                self.queue.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def send(self, value):
        if self.jsonrpc:
            value = dict(value, jsonrpc='2.0')
        self.process.stdin.write(json.dumps(value) + '\n')
        self.process.stdin.flush()

    def receive(self, deadline):
        while time.monotonic() < deadline:
            self.observe(None)
            try:
                value = self.queue.get(timeout=.025)
            except queue.Empty:
                continue
            if value is None:
                raise RuntimeError('app-server closed; see stderr.txt')
            if 'reader_error' in value:
                raise RuntimeError(value['reader_error'])
            self.messages.append(value)
            self.observe(value)
            if 'method' in value and 'id' in value:
                # Never grant approvals or synthesize a human response.
                self.send({'id': value['id'], 'error': {
                    'code': -32000, 'message': 'Rehearsal collector cannot answer interactive requests'}})
            return value
        raise TimeoutError('app-server diagnostic timed out')

    def call(self, method, params, seconds=45):
        self.next_id += 1
        ident = self.next_id
        self.send({'id': ident, 'method': method, 'params': params})
        deadline = time.monotonic() + seconds
        while True:
            value = self.receive(deadline)
            if value.get('id') == ident and 'method' not in value:
                if 'error' in value:
                    raise RuntimeError(method + ': ' + json.dumps(value['error']))
                return value['result']

    def close(self):
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait()
        self.reader.join(timeout=2)
        self.process.stdin.close()
        self.process.stdout.close()


def self_test():
    # Exercise interleaved notifications, responses, and refusal of server requests.
    mock = '''import json,sys
for line in sys.stdin:
 v=json.loads(line)
 if 'method' not in v: continue
 if v['method']=='initialize':
  print(json.dumps({'method':'hook/started','params':{'run':{'eventName':'sessionStart'}}}),flush=True)
  print(json.dumps({'id':v['id'],'result':{'ok':True}}),flush=True)
 elif v['method']=='test':
  print(json.dumps({'id':99,'method':'approval','params':{}}),flush=True)
  answer=json.loads(sys.stdin.readline())
  print(json.dumps({'id':v['id'],'result':{'denied':'error' in answer}}),flush=True)
'''
    seen = []
    with open(os.devnull, 'w') as err:
        rpc = RPC([sys.executable, '-c', mock], dict(os.environ), err, lambda x: seen.append(x) if x else None)
        try:
            assert rpc.call('initialize', {})['ok']
            assert seen[0]['method'] == 'hook/started'
            assert rpc.call('test', {})['denied']
        finally:
            rpc.close()
    print('PASS: interleaved notifications, RPC responses, approval refusal, process cleanup')
