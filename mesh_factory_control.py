"""Owner-only factory controls, relayed to a verified connected workstation."""
import json
import secrets
import threading
from urllib.parse import urlsplit
from flask import jsonify, render_template, request

ACTIONS = frozenset('factory.status host.overview host.system models.list audio.get audio.set voice.get voice.start voice.stop voice.providers voice.preview voice.select voice.settings vision.get vision.analyze chatter.get chatter.settings chatter.test skills.list mail.status orchestration.status harness.status grid.status vllm.status'.split())
FIELDS = {
    'mail.status': {'agent': str},
    'audio.set': {'source': str, 'sink': str},
    'voice.preview': {'provider': str, 'text': str, 'voice': str, 'pitch': (int, float)},
    'voice.select': {'provider': str},
    'voice.settings': {'provider': str, 'voice': str, 'pitch': (int, float)},
    'vision.analyze': {'prompt': str},
    'chatter.settings': {'enabled': bool, 'quiet': bool},
}

def valid_args(action, args):
    if not isinstance(args, dict) or len(json.dumps(args)) > 8192:
        return False
    fields = FIELDS.get(action, {})
    if set(args) - set(fields):
        return False
    for name, value in args.items():
        if not isinstance(value, fields[name]) or (isinstance(value, bool) and fields[name] != bool):
            return False
        if isinstance(value, str) and (len(value) > 1024 or '\x00' in value):
            return False
    required = {'audio.set': {'source', 'sink'}, 'voice.preview': {'provider', 'text'},
                'voice.select': {'provider'}, 'voice.settings': {'provider', 'voice', 'pitch'},
                'chatter.settings': {'enabled', 'quiet'}}
    if not required.get(action, set()).issubset(args):
        return False
    if 'pitch' in args and not -6 <= args['pitch'] <= 6:
        return False
    if action == 'mail.status' and args.get('agent', 'rend') not in {'rend', 'lyra', 'mak'}:
        return False
    return True

class FactoryRelay:
    def __init__(self, timeout=45, capacity=128):
        self.timeout, self.capacity = timeout, capacity
        self.pending = {}
        self.lock = threading.Lock()

    def resolve(self, agent_id, message):
        if message.get('type') != 'factory_control_response':
            return False
        request_id = message.get('request_id')
        if not isinstance(request_id, str) or len(request_id) > 128:
            return False
        key = (agent_id, request_id)
        payload = message.get('payload')
        if not isinstance(payload, dict) or not isinstance(payload.get('ok'), bool):
            return False
        with self.lock:
            pending = self.pending.get(key)
            if not pending or pending['event'].is_set():
                return False
            pending['payload'] = payload
            pending['event'].set()
        return True

    def dispatch(self, agent_id, action, args, send):
        request_id = secrets.token_urlsafe(24)
        key = (agent_id, request_id)
        pending = {'event': threading.Event(), 'payload': None}
        with self.lock:
            if len(self.pending) >= self.capacity or sum(k[0] == agent_id for k in self.pending) >= 16:
                return {'ok': False, 'error': 'factory_busy'}, 429
            self.pending[key] = pending
        try:
            ok, error = send(agent_id, {'type': 'factory_control_request', 'request_id': request_id,
                                       'payload': {'action': action, 'args': args}})
            if not ok:
                return {'ok': False, 'error': error or 'gateway_send_failed'}, 503
            if not pending['event'].wait(self.timeout):
                return {'ok': False, 'error': 'factory_timeout', 'request_id': request_id,
                        'detail': 'The workstation did not reply. The action may still finish; no retry was sent.'}, 504
            result = dict(pending['payload'])
            result['request_id'] = request_id
            return result, 200 if result['ok'] else 502
        finally:
            with self.lock:
                self.pending.pop(key, None)

factory_relay = FactoryRelay()

def register_factory_routes(app, require_session, user_id, registry, gateways, send):
    def available_hosts():
        owner = user_id()
        if not owner:
            return []
        return sorted([{'id': key, 'name': value.get('name') or key,
                        'connected': True, 'verified': True}
                       for key, value in list(registry.items())
                       if str(value.get('owner_id') or '').strip() == owner
                       and value.get('trust_state') == 'verified'
                       and key in gateways and not value.get('control_center_gateway')
                       and not value.get('office_worker') and not value.get('office_archived')],
                      key=lambda row: (row['name'].casefold(), row['id']))

    def owned(agent_id):
        record = registry.get(agent_id)
        if not record or not user_id() or str(record.get('owner_id') or '').strip() != user_id():
            return {'ok': False, 'error': 'agent_not_found'}, 404
        if record.get('control_center_gateway') or record.get('office_worker') or record.get('office_archived'):
            return {'ok': False, 'error': 'gateway_required'}, 403
        if record.get('trust_state') != 'verified':
            return {'ok': False, 'error': 'verified_gateway_required'}, 403
        if agent_id not in gateways:
            return {'ok': False, 'error': 'gateway_not_connected'}, 503
        return None

    @app.get('/mission-control')
    @require_session
    def factory_page():
        return render_template('mission_control.html', hosts=available_hosts())

    @app.get('/api/factory/gateways')
    @require_session
    def factory_gateways():
        response = jsonify(ok=True, gateways=available_hosts())
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/factory')
    @require_session
    def office_page():
        agents = [{'id': key, 'name': value.get('name', key), 'connected': key in gateways,
                   'verified': value.get('trust_state') == 'verified'} for key, value in registry.items()
                  if str(value.get('owner_id') or '').strip() == user_id() and not value.get('control_center_gateway')]
        return render_template('office.html', hosts=agents)

    @app.get('/api/agents/<agent_id>/factory')
    @require_session
    def factory_status(agent_id):
        failure = owned(agent_id)
        if failure:
            return jsonify(failure[0]), failure[1]
        result, status = factory_relay.dispatch(agent_id, 'factory.status', {}, send)
        return jsonify(result), status

    @app.post('/api/agents/<agent_id>/factory/control')
    @require_session
    def factory_control(agent_id):
        failure = owned(agent_id)
        if failure:
            return jsonify(failure[0]), failure[1]
        origin = urlsplit(request.headers.get('Origin', ''))
        expected = urlsplit(request.host_url)
        if (origin.scheme, origin.netloc) != (expected.scheme, expected.netloc) or request.headers.get('Sec-Fetch-Site') == 'cross-site':
            return jsonify(ok=False, error='same_origin_required'), 403
        if request.content_length and request.content_length > 16384:
            return jsonify(ok=False, error='payload_too_large'), 413
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) - {'action', 'args'}:
            return jsonify(ok=False, error='invalid_request'), 400
        action, args = body.get('action'), body.get('args', {})
        if not isinstance(action, str) or action not in ACTIONS:
            return jsonify(ok=False, error='unknown_action'), 400
        if not valid_args(action, args):
            return jsonify(ok=False, error='invalid_args'), 400
        result, status = factory_relay.dispatch(agent_id, action, args, send)
        return jsonify(result), status
