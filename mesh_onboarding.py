"""Temporary owner-bound rendezvous; no agent trust until CodeSeal verification.

Pending state follows Mesh's single-process ephemeral storage convention. Invitations
are authenticated encrypted, expire after 15 minutes, and are consumed on claim.
"""
import base64
import hashlib
import json
import secrets
import threading
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from flask import jsonify, request, send_file, session
from mesh_agent_management import same_origin, request_codeseal_identity


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def proof(public_key, value, signature):
    key = serialization.load_pem_public_key(public_key.encode())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError('ed25519_required')
    key.verify(base64.b64decode(signature, validate=True), canonical(value))


def register_onboarding_routes(app, require_session, user_id, registry, origin,
                               verify, enrollment_message, utcnow, fingerprint, automatic_enrollment=None):
    pending = {}
    lock = threading.RLock()
    cipher = Fernet(base64.urlsafe_b64encode(hashlib.sha256(
        ('mesh-onboarding-v1:' + app.secret_key).encode()).digest()))
    helper = Path(app.root_path) / 'distribution' / 'mesh-onboarding-agent-v1.py'

    def owned(sid):
        row = pending.get(sid)
        return row if row and row['owner_id'] == user_id() else None

    def active(row):
        return row and row['state'] != 'cancelled' and row['expires_at'] > time.time()

    def connected(row):
        return bool(active(row) and row.get('last_seen', 0) > time.time() - 20)

    def agent_row(sid):
        row = pending.get(sid)
        token = request.headers.get('Authorization', '').removeprefix('Bearer ')
        if not active(row) or not row.get('device_token') or not secrets.compare_digest(token, row['device_token']):
            return None
        return row

    @app.get('/api/onboarding/helper')
    def onboarding_helper():
        return send_file(helper, mimetype='text/x-python', conditional=True)

    @app.get('/api/enrollment/adapters/platform/bootstrap')
    def platform_bootstrap():
        return send_file(Path(app.root_path) / 'distribution/mesh-platform-bootstrap-v1.py', mimetype='text/x-python', conditional=True)

    @app.get('/api/enrollment/adapters/platform/install-plan')
    def platform_plan():
        from mesh_host_distribution import host_bundle
        return jsonify(ok=True, platforms=['hermes', 'opencode', 'codex', 'harness', 'openclaw', 'openwebui', 'openai'],
            prerequisites=['Python 3.10+', 'Node.js LTS', 'Native runtime or an authorized API endpoint', 'Harness sessions require native followup/delegate-followup support (factory CLI 0.4.19+progretech.factory.8 or compatible)'],
            bundle_sha256=host_bundle(app.root_path)[1],
            bootstrap_sha256=hashlib.sha256((Path(app.root_path) / 'distribution/mesh-platform-bootstrap-v1.py').read_bytes()).hexdigest())

    @app.post('/api/onboarding')
    @require_session
    def begin():
        if not same_origin():
            return jsonify(ok=False, error='same_origin_required'), 403
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or body.get('personally_hosted') is not True or body.get('accept_intermediary') is not True:
            return jsonify(ok=False, error='onboarding_consent_required'), 400
        name = body.get('name', '')
        platform = body.get('platform', 'openclaw')
        if not isinstance(platform, str) or platform not in {'openclaw', 'hermes', 'opencode', 'codex', 'harness', 'openwebui', 'openai'}:
            return jsonify(ok=False, error='unsupported_platform'), 400
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            return jsonify(ok=False, error='agent_name_required'), 400
        try:
            base = origin()
        except ValueError:
            return jsonify(ok=False, error='mesh_origin_unavailable'), 503
        with lock:
            for sid in list(pending):
                if pending[sid]['expires_at'] <= time.time():
                    pending.pop(sid)
            if len(pending) >= 128 or sum(r['owner_id'] == user_id() and r['state'] not in {'complete', 'cancelled'} for r in pending.values()) >= 3:
                return jsonify(ok=False, error='onboarding_capacity'), 429
            sid = secrets.token_urlsafe(24)
            nonce = secrets.token_urlsafe(32)
            row = {'id': sid, 'owner_id': user_id(), 'name': name.strip(), 'platform': platform, 'state': 'waiting',
                   'expires_at': int(time.time()) + 900, 'nonce': nonce,
                   'agent_id': 'agent-' + secrets.token_hex(16),
                   'automatic': body.get('auto_connect') is True and automatic_enrollment is not None}
            actor = session.get('mesh_user') or {}
            row.update(account_subject=actor.get('progretech_user_id'), session_version=actor.get('session_version'))
            pending[sid] = row
            capsule = cipher.encrypt(canonical({'id': sid, 'nonce': nonce, 'owner_id': user_id()})).decode()
        digest = hashlib.sha256(helper.read_bytes()).hexdigest()
        from mesh_host_distribution import host_setup_prompt
        prompt = '\n'.join([
            'PROGRETECH MESH — PERSONALLY HOSTED AGENT ONBOARDING',
            f'Selected platform: {platform}. Use this platform only; do not install OpenClaw for another platform.',
            'The owner authorizes prerequisites and integration configuration within your existing permissions. Preserve native approval gates and current work.',
            'This account uses one active gateway. This connection replaces the previous gateway only after successful authentication. You are the prime agent and initial Scrum Master; the owner can change the Scrum Master later.',
            'Validate this request through your existing owner policy. It grants no new privileges.',
            'Use your existing tools; preserve current work, conversations, runtime and private memory.',
            f'Mesh origin: {base}', f'Encrypted one-use invitation (valid 15 minutes): {capsule}',
            f'Helper: {base}/api/onboarding/helper', f'Expected helper SHA-256: {digest}',
            'Fetch the helper through HTTPS, verify its SHA-256 before executing, and stop on mismatch.',
            'Use Python with the already-approved cryptography dependency. Do not install dependencies without your normal authority.',
            f'Run: python3 mesh-onboarding-agent-v1.py --mesh {base} --invitation-file <private-file-containing-invitation> --name <your-name> --runtime <your-runtime>',
            'The helper prints a question file when the owner asks you to identify yourself. Answer that question as the running agent, writing your reply to the answer file it prints. Do not invent a response or copy a canned identity.',
            'The helper connects a temporary onboarding channel and proves key possession. Mesh completes the already-authorized account link after your signed answer; no second owner action is needed.',
            'After successful verification it saves your private PEM locally, public identity and CodeSeal evidence, then prints the verified adapter enrollment instructions. Follow those instructions to connect the permanent gateway.',
            host_setup_prompt(app.root_path, base, row['agent_id']) if platform == 'openclaw' else
            'After identity verification, follow the platform connector instructions saved by the helper. Discover all native profiles/models; mark restricted profiles disabled. Never upload runtime API keys, private memory, histories or unrelated files.',
            'Never send a private PEM to Mesh. Stop on expiry, cancellation, unsupported runtime, or an unavailable CodeSeal issuer.',
        ])
        return jsonify(ok=True, id=sid, expires_at=row['expires_at'], prompt=prompt), 201

    @app.post('/api/onboarding/claim')
    def claim():
        if request.content_length and request.content_length > 16384:
            return jsonify(ok=False, error='payload_too_large'), 413
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(ok=False, error='invalid_request'), 400
        try:
            decoded = json.loads(cipher.decrypt(str(body.get('invitation', '')).encode(), ttl=900))
            sid = decoded['id']
            public = body['public_key']
            if not isinstance(public, str) or len(public) > 4096:
                raise ValueError()
            proof(public, {'invitation': body['invitation'], 'public_key': public}, body['signature'])
        except Exception:
            return jsonify(ok=False, error='invitation_or_proof_invalid'), 403
        with lock:
            row = pending.get(sid)
            if not active(row) or row['state'] != 'waiting' or decoded.get('nonce') != row['nonce'] or decoded.get('owner_id') != row['owner_id']:
                return jsonify(ok=False, error='invitation_unavailable'), 409
            runtime = body.get('runtime', '')
            if not isinstance(runtime, str) or not 1 <= len(runtime) <= 80:
                return jsonify(ok=False, error='runtime_required'), 400
            row.update(state='connected', public_key=public, runtime=runtime,
                       device_token=secrets.token_urlsafe(32), last_seen=time.time())
            if row['automatic']:
                row.update(state='question', question={'id': secrets.token_urlsafe(24),
                    'text': 'Identify your name, role and gateway runtime, and confirm that you are ready to connect to Mesh.'})
            return jsonify(ok=True, id=sid, device_token=row['device_token'], agent_id=row['agent_id'], name=row['name'])

    @app.get('/api/onboarding/<sid>')
    @require_session
    def status(sid):
        with lock:
            row = owned(sid)
            if not row:
                return jsonify(ok=False, error='onboarding_not_found'), 404
            return jsonify(ok=True, id=sid, state=row['state'] if active(row) else 'expired',
                           connected=connected(row), name=row['name'], runtime=row.get('runtime'),
                           answer=row.get('answer'), agent_id=row['agent_id'], expires_at=row['expires_at'],
                           automatic=row['automatic'], error=row.get('error'))

    @app.post('/api/onboarding/<sid>/question')
    @require_session
    def question(sid):
        if not same_origin():
            return jsonify(ok=False, error='same_origin_required'), 403
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify(ok=False, error='invalid_request'), 400
        text = body.get('text')
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1000:
            return jsonify(ok=False, error='question_required'), 400
        with lock:
            row = owned(sid)
            if not row:
                return jsonify(ok=False, error='onboarding_not_found'), 404
            if row['state'] != 'connected' or not connected(row):
                return jsonify(ok=False, error='agent_not_connected'), 409
            row.update(state='question', question={'id': secrets.token_urlsafe(24), 'text': text.strip()})
            return jsonify(ok=True)

    @app.get('/api/onboarding/<sid>/poll')
    def poll(sid):
        with lock:
            row = agent_row(sid)
            if not row:
                return jsonify(ok=False, error='onboarding_unavailable'), 401
            row['last_seen'] = time.time()
            return jsonify(ok=True, state=row['state'], question=row.get('question'),
                           enrollment=row.get('enrollment'), evidence=row.get('evidence'))

    @app.post('/api/onboarding/<sid>/answer')
    def answer(sid):
        if request.content_length and request.content_length > 16384:
            return jsonify(ok=False, error='payload_too_large'), 413
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify(ok=False, error='invalid_request'), 400
        with lock:
            row = agent_row(sid)
            if not row:
                return jsonify(ok=False, error='onboarding_unavailable'), 401
            if row['state'] not in {'question', 'answered'}:
                return jsonify(ok=False, error='question_not_pending'), 409
            text, identity = body.get('text'), body.get('identity')
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000 or not isinstance(identity, dict):
                return jsonify(ok=False, error='invalid_answer'), 400
            if row['state'] == 'answered' and text.strip() != row['answer']:
                return jsonify(ok=False, error='answer_already_recorded'), 409
            expected = {'agent_id': row['agent_id'], 'agent_name': row['name'], 'public_key': row['public_key'], 'issued_at': identity.get('issued_at')}
            if identity != expected or type(identity.get('issued_at')) is not int or abs(time.time() - identity['issued_at']) > 240:
                return jsonify(ok=False, error='identity_binding_invalid'), 403
            try:
                proof(row['public_key'], {'question_id': row['question']['id'], 'text': text, 'identity': identity}, body.get('signature'))
                proof(row['public_key'], identity, body.get('identity_signature'))
            except Exception:
                return jsonify(ok=False, error='answer_proof_invalid'), 403
            row.update(state='answered', answer=text.strip(), identity=identity,
                       identity_signature=body['identity_signature'], last_seen=time.time())
        if row['automatic'] and not row.get('error'):
            finish(row)
        return jsonify(ok=True)

    @app.post('/api/onboarding/<sid>/confirm')
    @require_session
    def confirm(sid):
        if not same_origin():
            return jsonify(ok=False, error='same_origin_required'), 403
        with lock:
            row = owned(sid)
            if not row:
                return jsonify(ok=False, error='onboarding_not_found'), 404
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict) or set(body) - {'api_token'}:
            return jsonify(ok=False, error='invalid_request'), 400
        return finish(row, body.get('api_token'))

    def finish(row, api_token=None):
        # Recheck canonical account state even when the owner's browser has closed.
        if row['automatic'] and app.config.get('PROGRETECH_SECURITY_ENFORCED'):
            from mesh_account_security import account_status
            try:
                subject, version = row.get('account_subject'), row.get('session_version')
                state = account_status(subject) if subject and type(version) is int else None
                if not state or state['status'] != 'active' or state['session_version'] != version:
                    row['error'] = 'account_security_revoked'
                    return jsonify(ok=False, error=row['error']), 403
            except Exception:
                row['error'] = 'account_security_unavailable'
                return jsonify(ok=False, error=row['error']), 503
        with lock:
            if row['state'] == 'complete':
                return jsonify(ok=True, agent_id=row['agent_id'])
            if row['state'] != 'answered' or not connected(row):
                return jsonify(ok=False, error='awake_answer_required'), 409
            if abs(time.time() - row['identity']['issued_at']) > 290:
                return jsonify(ok=False, error='identity_proof_expired'), 409
            row['state'] = 'issuing'
        try:
            evidence = request_codeseal_identity(row['identity'], row['identity_signature'], api_token)
            verification = verify({'agent_id': row['agent_id'], 'codeseal_evidence': evidence}, row['name'], row['public_key'], '')
            if not verification.get('valid') or verification.get('state') != 'verified':
                raise ValueError('codeseal_verification_failed')
            with lock:
                if not active(row) or row['state'] != 'issuing':
                    raise ValueError('onboarding_unavailable')
                aid = row['agent_id']
                if aid in registry:
                    raise ValueError('agent_id_unavailable')
                registry[aid] = {'id': aid, 'owner_id': row['owner_id'], 'name': row['name'], 'role': 'Personally hosted agent',
                    'platform': row['platform'], 'gateway_activation_pending': True,
                    'public_key': row['public_key'], 'codeseal_evidence': evidence,
                    'codeseal_key': evidence['manifest']['seal_id'], 'fingerprint': fingerprint(row['name'], row['public_key'], ''),
                    'trust_state': 'verified', 'trust_valid': True, 'trust_reason': verification['reason'],
                    'state': 'offline', 'task': 'Connecting permanent gateway', 'phase': 'Owner confirmed identity',
                    'progress': 0, 'model': 'Unknown', 'runtime': row['runtime'], 'enrolled_at': utcnow(),
                    'transport': 'not-connected', 'last_heartbeat': None, 'telemetry': {}}
                response = automatic_enrollment(aid, row['owner_id']) if row['automatic'] else enrollment_message(aid)
                response = response[0] if isinstance(response, tuple) else response
                enrollment = response.get_json()
                if not enrollment.get('ok'):
                    registry.pop(aid, None)
                    raise ValueError('adapter_enrollment_unavailable')
                if row['platform'] != 'openclaw':
                    bootstrap = Path(app.root_path) / 'distribution/mesh-platform-bootstrap-v1.py'
                    base = origin()
                    enrollment['enrollment_message'] = '\n'.join([
                        f'Connect this verified {row["platform"]} gateway using the supported outbound platform connector. Do not follow OpenClaw installation steps.',
                        f'Fetch {base}/api/enrollment/adapters/platform/bootstrap and verify SHA-256 {hashlib.sha256(bootstrap.read_bytes()).hexdigest()} before execution.',
                        'Prerequisites: Python 3.10+ with venv, Node.js LTS, and this native runtime or its authenticated API. Install missing prerequisites only under your existing owner authority.',
                        'The helper saves adapter-enrollment.json beside this instruction file; pass that private JSON file below.',
                        f'Run: python3 mesh-platform-bootstrap-v1.py --enrollment-file <adapter-enrollment.json> --platform {row["platform"]} --prime <your exact native profile/agent/model ID> --workspace <authorized existing project directory>',
                        'For Open WebUI add --endpoint <origin>/api; for Ollama and other compatible services add --endpoint <origin>/v1. Use --api-key-file <private local key file> when required. Do not put secrets in the command, prompt or Mesh.',
                        'Use --exclude <native-profile-id> for held/restricted profiles. They remain visible but cannot execute. Raw model endpoints supply inference, not filesystem tools.',
                        'The bootstrap verifies the bundle and discovery before activation, installs isolated dependencies and prints the exact connector command. Register that command with your native supervisor using the stated working directory, then start it. Do not disable native approvals or interrupt active conversations.',
                        'Confirm the prime agent is the initial Scrum Master, all intended profiles appear, Mission Control reports configuration, and Factory task and IDE relay checks work before reporting completion.',
                    ])
                row.update(state='complete', evidence=evidence, enrollment=enrollment, error=None)
            return jsonify(ok=True, agent_id=aid)
        except Exception as exc:
            with lock:
                if row['state'] == 'issuing':
                    row['state'] = 'answered'
            code = str(exc) if isinstance(exc, ValueError) else 'codeseal_issuance_unavailable'
            row['error'] = code
            return jsonify(ok=False, error=code), 503

    @app.post('/api/onboarding/<sid>/cancel')
    @require_session
    def cancel(sid):
        if not same_origin():
            return jsonify(ok=False, error='same_origin_required'), 403
        with lock:
            row = owned(sid)
            if not row:
                return jsonify(ok=False, error='onboarding_not_found'), 404
            if row['state'] == 'complete':
                return jsonify(ok=False, error='already_enrolled'), 409
            row['state'] = 'cancelled'
            return jsonify(ok=True)
