"""Outbound Mesh connector for native CLI profiles and OpenAI-compatible APIs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import logging
from pathlib import Path
import secrets
import threading
import time
from types import SimpleNamespace
from urllib.parse import quote, urlsplit
from urllib.request import urlopen

import websocket

from gateway.platforms import Platform, runtime_key
from control_center.office import engine, namespace, validate_office, dispatch_native_mission
from control_center.office_identity import project, synchronize


class Runtime:
    def __init__(self, platform, bindings):
        self.platform, self.bindings = platform, bindings
        self.jobs, self.busy = {}, set()
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=4)

    def participant_busy(self, agent):
        with self.lock:
            return self.bindings.get(agent) in self.busy

    def chat_admission(self, agent):
        row = self.platform.rows.get(self.bindings.get(agent), {})
        return {'available': bool(row.get('enabled')) and not self.participant_busy(agent),
                'reason': 'ready' if row.get('enabled') else 'runtime_agent_disabled_or_unavailable'}

    def complete(self, agent, body):
        runtime = self.bindings.get(agent)
        if not runtime:
            raise ValueError('runtime_binding_required')
        with self.lock:
            if runtime in self.busy:
                raise ValueError('mesh_agent_busy')
            self.busy.add(runtime)
        try:
            return self.platform.complete(runtime, body)
        finally:
            with self.lock:
                self.busy.discard(runtime)

    def chat(self, agent, text, **kwargs):
        if not self.chat_admission(agent)['available']:
            raise ValueError('mesh_agent_busy')
        ident = secrets.token_hex(16)
        with self.lock:
            # Bound completed receipts; active work is never evicted.
            for key in list(self.jobs):
                if self.jobs[key].get('done') and len(self.jobs) >= 128:
                    del self.jobs[key]
            if len(self.jobs) >= 128:
                raise ValueError('mesh_jobs_full')
            self.jobs[ident] = {'agent_id': agent, 'job_id': ident, 'done': False, 'state': 'running'}
        def run():
            try:
                result = self.complete(agent, {'messages': [{'role': 'user', 'content': text}]})
                reply = result['choices'][0]['message'].get('content')
                if not isinstance(reply, str):
                    raise ValueError('runtime_returned_no_text')
                receipt = {'result': {'reply': reply}, 'state': 'completed'}
            except Exception as exc:
                # Runtime stderr, endpoint URLs and credentials remain on the host.
                logging.exception('Native task failed')
                receipt = {'error': str(exc) if isinstance(exc, ValueError) else 'runtime_execution_failed', 'state': 'failed'}
            with self.lock:
                self.jobs[ident].update(done=True, **receipt)
        self.pool.submit(run)
        return {'job_id': ident, 'state': 'running'}

    def get(self, agent, ident):
        with self.lock:
            row = self.jobs.get(ident)
            if not row or row['agent_id'] != agent:
                raise ValueError('runtime_job_unavailable')
            return dict(row)


class Connector:
    def __init__(self, config, home=None):
        self.config = config
        self.home = Path(home or Path.home())
        self.gateway = config['agent_id']
        if not __import__('re').fullmatch(r'[A-Za-z0-9_-]{1,48}', self.gateway):
            raise ValueError('invalid_gateway_id')
        self.platform = Platform(config, self.home)
        self.prime = runtime_key(config['prime'])
        self.provider = SimpleNamespace(bindings={})
        self.runtime = Runtime(self.platform, self.provider.bindings)
        self.lock = threading.RLock()
        self.refresh()

    def refresh(self):
        rows = self.platform.discover()
        if self.prime not in self.platform.rows or not self.platform.rows[self.prime]['enabled']:
            raise ValueError('enabled_prime_agent_required')
        # Match Mesh's existing long-ID child namespace exactly.
        for row in rows:
            rid = row['runtime_id']
            suffix = rid if __import__('re').fullmatch(r'[A-Za-z0-9_-]{1,28}', rid) else 'role_' + hashlib.sha256(rid.encode()).hexdigest()[:24]
            row['id'] = self.gateway if rid == self.prime else self.gateway + '--' + suffix
        bindings = {r['id']: r['runtime_id'] for r in rows}
        self.provider.bindings.clear()
        self.provider.bindings.update(bindings)
        snapshot = synchronize(self.home, self.prime, self.gateway, rows)
        self.rows = project(snapshot, rows, self.gateway, self.prime)
        return snapshot

    def roster(self):
        with self.lock:
            self.refresh()
            rows = []
            for row in self.rows:
                enabled = row.get('enabled', False)
                state = 'working' if self.runtime.participant_busy(row['id']) else 'unknown' if enabled else 'paused'
                rows.append({**row, 'state': state,
                    'activity': {'state': state, 'source': 'mesh-owned-jobs'},
                    'mesh_runtime': {'model': row.get('model', ''), 'sleeping': not enabled,
                        'controls_available': False, 'scope': 'Mesh-owned jobs; external sessions unobserved'}})
            return {'agents': rows,
                    'host': next(r for r in rows if r['id'] == self.gateway), 'platform': self.platform.kind}

    def control(self, agent, action, args):
        if agent not in self.provider.bindings:
            raise ValueError('runtime_binding_required')
        row = self.platform.rows[self.provider.bindings[agent]]
        if action in {'agent.get', 'profile.get'}:
            return {'profile': {'role': row['role'], 'models': [row['model']], 'permissions': [],
                'workstation': 'yes', 'stack': 'custom', 'voice': {'provider': 'piper', 'voice': 'current', 'pitch': 0}},
                'discovered': row, 'capabilities': ['models.list', 'host.system', 'runtime.status', 'factory.office']}
        if action == 'models.list':
            return {'models': [{'name': r['model']} for r in self.platform.rows.values()]}
        if action in {'host.system', 'host.overview', 'orchestration.status'}:
            return {'platform': self.platform.kind, 'agents': list(self.platform.rows.values()), 'gateway': self.gateway}
        if action == 'skills.list':
            return {'external_dirs': row.get('skills', []), 'managed_by': self.platform.kind}
        if action == 'runtime.status':
            return {'sleeping': not row['enabled'], 'model': row['model'], 'controls_available': False,
                    'busy': self.runtime.participant_busy(agent)}
        if action == 'communication.start':
            return self.runtime.chat(agent, args['text'])
        if action == 'communication.chat':
            completion = self.runtime.complete(agent, {'messages': [{'role': 'user', 'content': args['text']}]})
            return {'reply': completion['choices'][0]['message']['content']}
        if action == 'communication.job':
            return self.runtime.get(agent, args['job_id'])
        if action == 'factory.office':
            validate_office(args)
            with self.lock:
                self.refresh()
                if args['operation'] == 'workday.control':
                    raise ValueError('capability_unavailable')
                if args['operation'] == 'orchestrator.set':
                    snapshot = engine(self.home, namespace(self.prime, self.gateway), 'snapshot')['snapshot']
                    target = next((a for a in snapshot['agents'] if a['id'] == args['args']['id']), {})
                    if not self.platform.rows.get(target.get('runtime_id'), {}).get('enabled'):
                        raise ValueError('enabled_runtime_agent_required')
                if args['operation'] == 'run':
                    return dispatch_native_mission(self.home, self.prime, args['args']['id'], self.gateway, self.provider, self.runtime)
                result = engine(self.home, namespace(self.prime, self.gateway), args['operation'], args['args'])
                result['snapshot'].update(nativeRuntimeBound=True, nativeRuntimeReady=True,
                    runtimeReady=True, runtimeMode=self.platform.kind, nativeAdmissionReason='ready')
                return result
        raise ValueError('capability_unavailable')

    def message(self, message):
        kind, payload = message.get('type'), message.get('payload', {})
        ident = message.get('request_id')
        if kind == 'factory_control_request':
            try:
                action = payload.get('action')
                if action == 'factory.status':
                    self.roster()
                    result = {'agents': [{**r, 'id': r['runtime_id'], 'runtime': self.platform.kind,
                        'controller': r.get('is_orchestrator', False),
                        'workspace_ready': bool(r.get('enabled')), 'hardware_status': 'Selected gateway'}
                        for r in self.rows if r.get('runtime_id')],
                        'capabilities': ['host.system', 'host.overview', 'models.list', 'skills.list', 'orchestration.status'],
                        'providers': {self.platform.kind: {'available': True}},
                        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
                else:
                    result = self.control(self.gateway, action, payload.get('args', {}))
                body = {'ok': True, 'result': result}
            except Exception as exc:
                body = {'ok': False, 'error': str(exc) if isinstance(exc, ValueError) else 'host_action_failed'}
            return {'type': 'factory_control_response', 'request_id': ident, 'payload': body}
        if kind == 'control_center_request':
            try:
                result = self.control(payload.get('agent_id'), payload.get('action'), payload.get('args', {}))
                body = {'ok': True, 'result': result}
            except Exception as exc:
                logging.exception('Mesh control request failed')
                body = {'ok': False, 'error': str(exc) if isinstance(exc, ValueError) else 'host_action_failed'}
            return {'type': 'control_center_response', 'request_id': ident, 'payload': body}
        if kind == 'ide_chat_request':
            try:
                target = payload.get('target', {})
                agent = target.get('agent_id', self.gateway)
                if target.get('runtime_id') and self.provider.bindings.get(agent) != target['runtime_id']:
                    raise ValueError('runtime_binding_required')
                completion = self.runtime.complete(agent, payload['openai'])
                completion['model'] = payload['openai']['model']
                body = {'ok': True, 'completion': completion}
            except Exception as exc:
                logging.exception('IDE request failed')
                body = {'ok': False, 'error': str(exc) if isinstance(exc, ValueError) else 'runtime_execution_failed'}
            return {'type': 'ide_chat_response', 'request_id': ident, 'payload': body}
        if kind == 'message_request':
            try:
                target = payload.get('target_agent_id') or payload.get('agent_id') or self.gateway
                text = payload['text']
                if text.startswith('/agent '):
                    _, runtime, text = text.split(' ', 2)
                    target = next((aid for aid, rid in self.provider.bindings.items() if rid == runtime), None)
                    if not target:
                        raise ValueError('runtime_binding_required')
                result = self.runtime.complete(target, {'messages': [{'role': 'user', 'content': text}]})
                text, error = result['choices'][0]['message']['content'], None
            except Exception:
                logging.exception('Agent message failed')
                text, error = 'The runtime could not complete this request. Check its configuration.', 'runtime_execution_failed'
            return {'type': 'message_response', 'message': text,
                    'payload': {'request_id': ident, 'room': payload.get('room', 'direct'), 'runtime_error': error}}

    def run(self):
        origin = self.config['mesh'].rstrip('/')
        u = urlsplit(origin)
        if u.scheme != 'https' or not u.netloc or u.path or u.query or u.fragment or u.username or u.password:
            raise ValueError('mesh_https_origin_required')
        url = 'wss://' + u.netloc + '/ws/gateway/' + self.gateway + '?credential=' + quote(self.config['device_credential'])
        send_lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=8) as pool:
            while True:
                try:
                    ws = websocket.create_connection(url, timeout=25, enable_multithread=True)
                    paired = json.loads(ws.recv())
                    if paired.get('type') != 'paired':
                        raise ValueError('gateway_pairing_failed')
                    logging.info('Mesh gateway connected to build %s', paired.get('build_id', 'unknown'))
                    ws.settimeout(1)
                    def send(value, socket=ws):
                        with send_lock:
                            socket.send(json.dumps(value))
                    def handle(message, sender=send):
                        result = self.message(message)
                        if result:
                            sender(result)
                    next_roster = 0
                    next_release_check = 0
                    while True:
                        if time.monotonic() >= next_release_check:
                            next_release_check = time.monotonic() + 30
                            if self.release_changed(origin, paired.get('build_id')):
                                logging.info('Mesh release changed; reconnecting gateway')
                                break
                        if time.monotonic() >= next_roster:
                            send({'type': 'control_center_roster', 'payload': self.roster()})
                            send({'type': 'heartbeat', 'payload': {'state': 'online', 'runtime': {'hermes': 'Hermes', 'opencode': 'OpenCode', 'openwebui': 'OpenWebUI', 'openai': 'OpenAI-compatible'}[self.platform.kind],
                                'task': 'Gateway connected', 'phase': 'Native platform ready'}})
                            next_roster = time.monotonic() + 10
                        try:
                            raw = ws.recv()
                        except websocket.WebSocketTimeoutException:
                            continue
                        if not raw:
                            break
                        pool.submit(handle, json.loads(raw))
                except (OSError, ValueError, websocket.WebSocketException):
                    logging.warning('Mesh connection unavailable; retrying in 10 seconds')
                finally:
                    if 'ws' in locals():
                        ws.close()
                time.sleep(10)

    @staticmethod
    def release_changed(origin, connected_build):
        # WebSockets can outlive a Cloud Run rollout; HTTP then reaches a new process.
        if not connected_build:
            return False
        try:
            with urlopen(origin + '/healthz', timeout=5) as response:
                health = json.loads(response.read(8192))
            return bool(health.get('ok') and health.get('service') == 'progretech-mesh'
                        and health.get('build') and health['build'] != connected_build)
        except (OSError, ValueError):
            return False


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    connector = Connector(json.loads(args.config.read_text()))
    if args.check:
        print(json.dumps(connector.roster()))
    else:
        connector.run()


if __name__ == '__main__':
    main()
