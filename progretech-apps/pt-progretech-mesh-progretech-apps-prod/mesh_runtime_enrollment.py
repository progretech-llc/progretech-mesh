"""Add one native runtime to an existing verified gateway without replacing it."""
import base64
import hashlib
import json
from pathlib import Path
import secrets
import threading
import time
from flask import jsonify, request, send_file
from mesh_agent_management import same_origin

PLATFORMS = {'hermes', 'opencode', 'codex', 'openclaw', 'harness'}


def register_runtime_enrollment(app, require_session, user_id, registry, origin, verify_device):
    pending = {}
    lock = threading.RLock()
    helper = Path(app.root_path)/'distribution/mesh-runtime-join-v1.py'

    def host(aid, owner):
        row = registry.get(aid, {})
        return bool(row.get('owner_id') == owner and row.get('trust_state') == 'verified'
                    and not row.get('control_center_gateway') and not row.get('gateway_superseded'))

    @app.get('/api/runtime-enrollment/helper')
    def runtime_helper():
        return send_file(helper, mimetype='text/x-python', conditional=True)

    @app.get('/api/runtime-enrollment/hosts')
    @require_session
    def runtime_hosts():
        return jsonify(ok=True, hosts=[{'id': aid, 'name': r.get('name', aid)}
            for aid, r in registry.items() if host(aid, user_id())], platforms=sorted(PLATFORMS))

    @app.post('/api/runtime-enrollment')
    @require_session
    def begin_runtime():
        if not same_origin():
            return jsonify(ok=False, error='same_origin_required'), 403
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify(ok=False, error='invalid_request'), 400
        if body.get('personally_hosted') is not True or body.get('accept_intermediary') is not True:
            return jsonify(ok=False, error='onboarding_consent_required'), 400
        aid, platform, name = body.get('gateway'), body.get('platform'), body.get('name', '')
        if not isinstance(aid, str) or not host(aid, user_id()):
            return jsonify(ok=False, error='owned_verified_gateway_required'), 403
        if not isinstance(platform, str) or platform not in PLATFORMS or not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            return jsonify(ok=False, error='platform_and_name_required'), 400
        try:
            base = origin()
        except ValueError:
            return jsonify(ok=False, error='mesh_origin_unavailable'), 503
        with lock:
            for sid in list(pending):
                if pending[sid]['expires_at'] <= time.time(): del pending[sid]
            if len(pending) >= 128 or sum(r['owner'] == user_id() and r['state'] == 'waiting' for r in pending.values()) >= 3:
                return jsonify(ok=False, error='onboarding_capacity'), 429
            sid, token = secrets.token_urlsafe(24), secrets.token_urlsafe(32)
            row = {'owner': user_id(), 'gateway': aid, 'platform': platform, 'name': name.strip(),
                   'token': token, 'state': 'waiting', 'expires_at': int(time.time())+900}
            pending[sid] = row
        payload = {'mesh': base, 'gateway': aid, 'platform': platform, 'name': name.strip(), 'invitation': sid, 'token': token}
        capsule = 'PTMR1:' + base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        digest = hashlib.sha256(helper.read_bytes()).hexdigest()
        prompt = '\n'.join(['PROGRETECH MESH — ADD ONE NATIVE TOOL',
            f'Connect this exact {platform} installation/profile/session to the existing verified workstation. Preserve its other entries and current work.',
            'The owner authorizes this registration within existing native permissions. Do not create agents, change model routes, install another runtime or impersonate another session owner.',
            'Identify your exact native profile/agent ID; for Harness use the UUID of this session, not another conversation. If uncertain, stop and explain.',
            'The host must already be connected with the current Mesh connector. Use Sync & Update first if its registration module is unavailable.',
            f'Helper: {base}/api/runtime-enrollment/helper', f'Expected helper SHA-256: {digest}',
            'Download through HTTPS and verify the digest before execution. Save the following payload in a private owner-only file; do not print credentials.', capsule,
            'Run: python3 mesh-runtime-join-v1.py --payload-file <private-payload-file> --native-id <exact-native-id>',
            'For Harness, run this in the exact session being added: native follow-up control is explicitly granted to Mesh without changing creation/close/spawn ownership. The helper authenticates using the existing local device credential and adds only this native entry. It never sends histories, memory or provider keys.',
            'Wait for the existing gateway to refresh. The owner selects the Scrum Master in Factory; registration does not replace that selection.'])
        return jsonify(ok=True, id=sid, expires_at=row['expires_at'], prompt=prompt), 201

    @app.get('/api/runtime-enrollment/<sid>')
    @require_session
    def runtime_status(sid):
        with lock:
            r = pending.get(sid)
            if not r or r['owner'] != user_id():
                return jsonify(ok=False, error='onboarding_not_found'), 404
            return jsonify(ok=True, state=r['state'] if r['expires_at'] > time.time() else 'expired',
                           gateway=r['gateway'], platform=r['platform'], native_id=r.get('native_id'))

    @app.post('/api/runtime-enrollment/<sid>/cancel')
    @require_session
    def runtime_cancel(sid):
        if not same_origin(): return jsonify(ok=False, error='same_origin_required'), 403
        with lock:
            r = pending.get(sid)
            if not r or r['owner'] != user_id(): return jsonify(ok=False, error='onboarding_not_found'), 404
            if r['state'] in {'waiting','authorized'}: r['state'] = 'cancelled'
        return jsonify(ok=True)

    @app.post('/api/runtime-enrollment/<sid>/complete')
    def complete_runtime(sid):
        if request.content_length and request.content_length>16384:return jsonify(ok=False,error='payload_too_large'),413
        body=request.get_json(silent=True)
        if not isinstance(body,dict):return jsonify(ok=False,error='invalid_request'),400
        with lock:
            r=pending.get(sid)
            token=request.headers.get('Authorization','').removeprefix('Bearer ')
            if not r or r['expires_at']<=time.time() or r['state'] not in {'authorized','complete'} or not secrets.compare_digest(token,r['token']):
                return jsonify(ok=False,error='invitation_invalid_or_expired'),403
            aid,credential=body.get('agent_id'),body.get('device_credential')
            if aid!=r['gateway'] or body.get('native_id')!=r.get('native_id') or not isinstance(credential,str):
                return jsonify(ok=False,error='native_binding_required'),400
            valid,_,_=verify_device(aid,credential)
            if not valid or not host(aid,r['owner']):return jsonify(ok=False,error='device_authentication_failed'),403
            r['state']='complete'
            return jsonify(ok=True,state='complete')

    @app.post('/api/runtime-enrollment/<sid>/redeem')
    def redeem_runtime(sid):
        if request.content_length and request.content_length > 16384:
            return jsonify(ok=False, error='payload_too_large'), 413
        body = request.get_json(silent=True)
        if not isinstance(body, dict): return jsonify(ok=False, error='invalid_request'), 400
        with lock:
            r = pending.get(sid)
            token = request.headers.get('Authorization', '').removeprefix('Bearer ')
            if not r or r['expires_at'] <= time.time() or r['state'] == 'cancelled' or not secrets.compare_digest(token, r['token']):
                return jsonify(ok=False, error='invitation_invalid_or_expired'), 403
            aid, credential, native = body.get('agent_id'), body.get('device_credential'), body.get('native_id')
            if aid != r['gateway'] or not isinstance(credential, str) or not isinstance(native, str) or not 1 <= len(native) <= 128:
                return jsonify(ok=False, error='native_binding_required'), 400
            valid, _, _ = verify_device(aid, credential)
            if not valid or not host(aid, r['owner']): return jsonify(ok=False, error='device_authentication_failed'), 403
            if r['state'] in {'authorized','complete'} and native != r.get('native_id'):
                return jsonify(ok=False, error='invitation_already_bound'), 409
            r.update(state='authorized' if r['state']!='complete' else 'complete', native_id=native)
            return jsonify(ok=True, platform=r['platform'], name=r['name'], native_id=native)
