import base64
import time
import unittest
from functools import wraps
from unittest.mock import patch
from flask import Flask, jsonify, session
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from mesh_onboarding import register_onboarding_routes, canonical


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, root_path=str(__import__('pathlib').Path(__file__).resolve().parent.parent))
        self.app.secret_key = 'test-secret'
        self.registry = {}
        def auth(view):
            @wraps(view)
            def wrapped(*a, **kw):
                if not session.get('uid'): return jsonify(ok=False), 401
                return view(*a, **kw)
            return wrapped
        register_onboarding_routes(self.app, auth, lambda: session.get('uid'), self.registry,
            lambda: 'https://mesh.example', lambda *a: {'state': 'verified', 'valid': True, 'reason': 'test-signature'},
            lambda aid: jsonify(ok=True, enrollment_message='adapter instructions', enrollment_payload='PTM1:test'),
            lambda: 'now', lambda *a: 'fingerprint', automatic_enrollment=lambda aid, owner: jsonify(ok=True, enrollment_message='fixture', owner=owner))
        self.client = self.app.test_client()
        self.login()
        self.key = Ed25519PrivateKey.generate()
        self.public = self.key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()

    def login(self, uid='owner'):
        with self.client.session_transaction() as s: s['uid'] = uid

    def post(self, url, data, origin='http://localhost', **kwargs):
        return self.client.post(url, json=data, headers={'Origin': origin, **kwargs})

    def sign(self, obj):
        return base64.b64encode(self.key.sign(canonical(obj))).decode()

    def begin(self, automatic=False):
        response = self.post('/api/onboarding', {'name': 'Ada', 'personally_hosted': True, 'accept_intermediary': True, 'auto_connect': automatic})
        self.assertEqual(response.status_code, 201)
        self.sid = response.json['id']
        prompt = response.json['prompt']
        self.invitation = next(line.split(': ', 1)[1] for line in prompt.splitlines() if line.startswith('Encrypted one-use invitation'))
        self.assertNotIn('owner', self.invitation)

    def claim(self):
        body = {'invitation': self.invitation, 'public_key': self.public}
        self.claim_body = {**body, 'signature': self.sign(body), 'runtime': 'OpenClaw'}
        result = self.client.post('/api/onboarding/claim', json=self.claim_body)
        self.assertEqual(result.status_code, 200)
        self.agent_id = result.json['agent_id']
        self.token = result.json['device_token']

    def answer(self):
        self.assertEqual(self.post(f'/api/onboarding/{self.sid}/question', {'text': 'Identify yourself'}).status_code, 200)
        poll = self.client.get(f'/api/onboarding/{self.sid}/poll', headers={'Authorization': 'Bearer ' + self.token})
        identity = {'agent_id': self.agent_id, 'agent_name': 'Ada', 'public_key': self.public, 'issued_at': int(time.time())}
        body = {'text': 'I am Ada, your OpenClaw researcher. I am awake.', 'identity': identity}
        body['signature'] = self.sign({'question_id': poll.json['question']['id'], **body})
        body['identity_signature'] = self.sign(identity)
        self.answer_body = body
        return self.client.post(f'/api/onboarding/{self.sid}/answer', json=body, headers={'Authorization': 'Bearer ' + self.token})

    def test_consent_and_origin(self):
        self.assertEqual(self.post('/api/onboarding', {'name': 'Ada'}).status_code, 400)
        self.assertEqual(self.post('/api/onboarding', {}, 'https://other.example').status_code, 403)
        self.assertEqual(self.post('/api/onboarding', []).status_code, 400)

    def test_owner_and_replay(self):
        self.begin(); self.claim()
        self.assertEqual(self.client.post('/api/onboarding/claim', json=self.claim_body).status_code, 409)
        self.login('other')
        for action in ('question', 'confirm', 'cancel'):
            self.assertEqual(self.post(f'/api/onboarding/{self.sid}/{action}', {'text': 'Who?'}).status_code, 404)
        self.assertEqual(self.client.get(f'/api/onboarding/{self.sid}').status_code, 404)

    def test_no_enrollment_before_awake_answer(self):
        self.begin(); self.claim()
        self.assertEqual(self.post(f'/api/onboarding/{self.sid}/confirm', {}).status_code, 409)
        self.assertEqual(self.registry, {})

    def test_full_lifecycle_and_idempotent_confirmation(self):
        self.begin(); self.claim(); self.assertEqual(self.answer().status_code, 200)
        evidence = {'manifest': {'seal_id': 'PTCS-TEST'}}
        with patch('mesh_onboarding.request_codeseal_identity', return_value=evidence) as issuer:
            result = self.post(f'/api/onboarding/{self.sid}/confirm', {})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(self.registry[self.agent_id]['owner_id'], 'owner')
            self.assertEqual(self.registry[self.agent_id]['public_key'], self.public)
            self.assertEqual(self.post(f'/api/onboarding/{self.sid}/confirm', {}).status_code, 200)
            issuer.assert_called_once()
        poll = self.client.get(f'/api/onboarding/{self.sid}/poll', headers={'Authorization': 'Bearer ' + self.token})
        self.assertEqual(poll.json['evidence'], evidence)
        self.assertNotIn('private_key', poll.json)

    def test_fails_closed_and_can_retry(self):
        self.begin(); self.claim(); self.answer()
        with patch('mesh_onboarding.request_codeseal_identity', side_effect=ValueError('codeseal_issuer_not_configured')):
            self.assertEqual(self.post(f'/api/onboarding/{self.sid}/confirm', {}).status_code, 503)
        self.assertEqual(self.registry, {})
        self.assertEqual(self.client.get(f'/api/onboarding/{self.sid}').json['state'], 'answered')

    def test_cancel_and_invalid_proof(self):
        self.begin()
        self.assertEqual(self.client.post('/api/onboarding/claim', json={'invitation': self.invitation, 'public_key': self.public, 'signature': 'bad'}).status_code, 403)
        self.post(f'/api/onboarding/{self.sid}/cancel', {})
        body = {'invitation': self.invitation, 'public_key': self.public}
        self.assertEqual(self.client.post('/api/onboarding/claim', json={**body, 'signature': self.sign(body), 'runtime': 'OpenClaw'}).status_code, 409)

    def test_bad_agent_token_and_answer_signature(self):
        self.begin(); self.claim()
        self.assertEqual(self.client.get(f'/api/onboarding/{self.sid}/poll').status_code, 401)
        self.answer(); body = dict(self.answer_body); body['signature'] = 'bad'
        self.assertEqual(self.client.post(f'/api/onboarding/{self.sid}/answer', json=body, headers={'Authorization': 'Bearer ' + self.token}).status_code, 403)

    def test_automatic_connection_finishes_without_the_owner_browser_or_session(self):
        self.begin(automatic=True); self.claim()
        agent = self.app.test_client()
        headers = {'Authorization':'Bearer '+self.token}
        poll = agent.get(f'/api/onboarding/{self.sid}/poll', headers=headers)
        self.assertEqual(poll.json['state'], 'question')
        identity = {'agent_id':self.agent_id,'agent_name':'Ada','public_key':self.public,'issued_at':int(time.time())}
        body = {'text':'I am Ada on the OpenClaw gateway.','identity':identity}
        body['signature'] = self.sign({'question_id':poll.json['question']['id'],**body})
        body['identity_signature'] = self.sign(identity)
        evidence = {'manifest':{'seal_id':'PTCS-TEST'}}
        with patch('mesh_onboarding.request_codeseal_identity',return_value=evidence):
            response = agent.post(f'/api/onboarding/{self.sid}/answer',json=body,headers=headers)
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.registry[self.agent_id]['owner_id'],'owner')
        final = agent.get(f'/api/onboarding/{self.sid}/poll',headers=headers).json
        self.assertEqual(final['state'],'complete')
        self.assertEqual(final['enrollment']['owner'],'owner')
        self.assertEqual(agent.get(f'/api/onboarding/{self.sid}').status_code,401)

    def test_automatic_issuer_failure_preserves_the_agent_channel_for_owner_recovery(self):
        self.begin(automatic=True); self.claim()
        headers = {'Authorization':'Bearer '+self.token}
        poll = self.client.get(f'/api/onboarding/{self.sid}/poll',headers=headers).json
        identity = {'agent_id':self.agent_id,'agent_name':'Ada','public_key':self.public,'issued_at':int(time.time())}
        body = {'text':'I am Ada.','identity':identity}
        body['signature'] = self.sign({'question_id':poll['question']['id'],**body})
        body['identity_signature'] = self.sign(identity)
        with patch('mesh_onboarding.request_codeseal_identity',side_effect=ValueError('codeseal_issuer_not_configured')):
            response = self.client.post(f'/api/onboarding/{self.sid}/answer',json=body,headers=headers)
        self.assertEqual(response.status_code,200)
        status = self.client.get(f'/api/onboarding/{self.sid}').json
        self.assertTrue(status['connected'])
        self.assertEqual(status['state'],'answered')
        self.assertEqual(status['error'],'codeseal_issuer_not_configured')
        self.assertEqual(self.registry,{})

    def test_automatic_linking_rechecks_locked_or_revoked_owner_after_browser_closes(self):
        with self.client.session_transaction() as current:
            current['mesh_user']={'progretech_user_id':'subject','session_version':1}
        self.begin(automatic=True);self.claim()
        self.app.config['PROGRETECH_SECURITY_ENFORCED']=True
        agent=self.app.test_client();headers={'Authorization':'Bearer '+self.token}
        question=agent.get(f'/api/onboarding/{self.sid}/poll',headers=headers).json['question']
        identity={'agent_id':self.agent_id,'agent_name':'Ada','public_key':self.public,'issued_at':int(time.time())}
        body={'text':'I am Ada.','identity':identity}
        body['signature']=self.sign({'question_id':question['id'],**body});body['identity_signature']=self.sign(identity)
        for state in ({'status':'locked','session_version':1},{'status':'active','session_version':2}):
            with patch('mesh_account_security.account_status',return_value=state), patch('mesh_onboarding.request_codeseal_identity') as issuer:
                result=agent.post(f'/api/onboarding/{self.sid}/answer',json=body,headers=headers)
                self.assertEqual(result.status_code,200)
                issuer.assert_not_called()
                self.assertEqual(self.registry,{})
