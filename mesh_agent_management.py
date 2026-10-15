"""Owner-scoped management and conversations through the verified host."""
import json
import os
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from flask import jsonify, request
from mesh_control_center import control_relay


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_codeseal_identity(identity, signature, api_token=None):
    token = api_token or os.environ.get('CODESEAL_MESH_ISSUER_TOKEN', '')
    if not isinstance(token, str) or not token.startswith('ptcs_live_'):
        raise ValueError('codeseal_issuer_not_configured')
    base = os.environ.get('CODESEAL_API_URL', 'https://codeseal.progretech.com/api/v1').rstrip('/')
    target = urlsplit(base)
    local = os.environ.get('APP_ENV') != 'production' and target.hostname in {'127.0.0.1', 'localhost', '::1'}
    if target.scheme != 'https' and not (target.scheme == 'http' and local):
        raise ValueError('codeseal_url_invalid')
    payload = json.dumps({'identity': identity, 'signature': signature}).encode()
    req = Request(base + '/mesh/identities', data=payload, headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    with build_opener(NoRedirect).open(req, timeout=20) as response:
        return json.loads(response.read(65536))


def same_origin():
    a, b = urlsplit(request.headers.get('Origin', '')), urlsplit(request.host_url)
    return (a.scheme, a.netloc) == (b.scheme, b.netloc) and request.headers.get('Sec-Fetch-Site') != 'cross-site'


def linked_message(record, owner, registry, gateways, send):
    if not same_origin():
        return jsonify(ok=False, error='same_origin_required'), 403
    host_id = record.get('control_center_gateway') or record['id']
    host = registry.get(host_id, {})
    if record.get('owner_id') != owner or host.get('owner_id') != owner or host.get('trust_state') != 'verified':
        return jsonify(ok=False, error='agent_not_found'), 404
    if host_id not in gateways:
        return jsonify(ok=False, error='gateway_not_connected'), 503
    if record.get('gateway_enrollment') and not any(a.get('id') == record['id'] for a in host.get('identified_agents', [])):
        return jsonify(ok=False, error='gateway_candidate_unavailable'), 409
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or set(body) != {'text'} or not isinstance(body['text'], str) or not 1 <= len(body['text'].strip()) <= 4000:
        return jsonify(ok=False, error='invalid_message'), 400
    result, status = control_relay.dispatch(record['id'], 'communication.chat', {'text': body['text'].strip()}, send, host_id)
    if result.get('ok'):
        return jsonify(ok=True, reply=result.get('result', {}).get('reply', ''), agent_id=record['id'])
    return jsonify(result), status


def register_management_routes(app, require_session, user_id, registry, gateways, send):
    @app.post('/api/agents/<agent_id>/management')
    @require_session
    def manage_agent(agent_id):
        if request.content_length and request.content_length > 550000:
            return jsonify(ok=False, error='payload_too_large'), 413
        if not same_origin():
            return jsonify(ok=False, error='same_origin_required'), 403
        record = registry.get(agent_id)
        if not record or record.get('owner_id') != user_id():
            return jsonify(ok=False, error='agent_not_found'), 404
        host_id = record.get('control_center_gateway') or agent_id
        host = registry.get(host_id, {})
        if host.get('owner_id') != user_id() or host.get('trust_state') != 'verified':
            return jsonify(ok=False, error='verified_host_required'), 403
        if host_id not in gateways:
            return jsonify(ok=False, error='gateway_not_connected'), 503
        if record.get('gateway_enrollment') and not any(a.get('id') == agent_id for a in host.get('identified_agents', [])):
            return jsonify(ok=False, error='gateway_candidate_unavailable'), 409
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) - {'action', 'args'}:
            return jsonify(ok=False, error='invalid_request'), 400
        action = body.get('action')
        if action not in {'context.read', 'specklet.get', 'specklet.toggle', 'specklet.import', 'specklet.task', 'memory.status', 'memory.share', 'memory.search', 'chatter.encounter','chatter.configure', 'chatter.history', 'chatter.pair', 'chatter.topic', 'handoff.create', 'handoff.list', 'handoff.control', 'files.begin', 'files.chunk', 'files.finish', 'files.cancel', 'files.list', 'files.read', 'files.reference', 'communication.get', 'communication.save', 'communication.chat', 'communication.start', 'communication.job', 'communication.new', 'runtime.status', 'runtime.wake', 'runtime.sleep', 'runtime.context', 'runtime.recover', 'runtime.snapshot', 'enrollment.remove', 'factory.providers', 'factory.run', 'factory.job'}:
            return jsonify(ok=False, error='unknown_action'), 400
        from control_center.management import validate_management
        try:
            validate_management(action, body.get('args', {}))
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        result, status = control_relay.dispatch(agent_id, action, body.get('args', {}), send, host_id)
        if action == 'enrollment.remove' and result.get('ok'):
            for aid in list(registry):
                if aid == agent_id or registry[aid].get('control_center_gateway') == agent_id:
                    registry.pop(aid, None)
            if agent_id == host_id:
                socket = gateways.pop(host_id, None)
                if socket:
                    try: socket.close()
                    except (RuntimeError, OSError): pass
        response=jsonify(result)
        if action.startswith(('memory.','specklet.')):
            response.headers['Cache-Control']='no-store, private'
            response.headers['Pragma']='no-cache'
        return response, status

    @app.post('/api/enrollment/codeseal')
    @require_session
    def issue_codeseal():
        if not same_origin():
            return jsonify(ok=False, error='same_origin_required'), 403
        if request.content_length and request.content_length > 16384:
            return jsonify(ok=False, error='payload_too_large'), 413
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) - {'identity', 'signature', 'api_token'} or not {'identity', 'signature'} <= set(body):
            return jsonify(ok=False, error='invalid_issuance_request'), 400
        token = body.get('api_token', '')
        if not isinstance(token, str) or (token and not token.startswith('ptcs_live_')):
            return jsonify(ok=False, error='invalid_codeseal_api_token'), 400
        try:
            evidence = request_codeseal_identity(body['identity'], body['signature'], token or None)
            return jsonify(ok=True, evidence=evidence)
        except ValueError as exc:
            if str(exc) in {'codeseal_issuer_not_configured', 'codeseal_url_invalid'}:
                return jsonify(ok=False, error=str(exc)), 503
            return jsonify(ok=False, error='invalid_issuance_request'), 400
        except Exception:
            return jsonify(ok=False, error='codeseal_issuance_unavailable', detail='CodeSeal issuance is temporarily unavailable. Try again.'), 502
