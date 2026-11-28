import unittest
from functools import wraps
from flask import Flask, jsonify, session
from unittest.mock import patch
from mesh_office import register_office_routes


class OfficeRouteTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__); app.secret_key = 'test'
        self.registry = {'host': {'owner_id': 'owner', 'trust_state': 'verified'}}
        self.gateways = {'host': object()}
        def auth(view):
            @wraps(view)
            def wrapped(*a, **kw):
                if not session.get('uid'): return jsonify(ok=False), 401
                return view(*a, **kw)
            return wrapped
        register_office_routes(app, auth, lambda: session.get('uid'), self.registry, self.gateways, lambda *a: (True, None))
        self.client = app.test_client()

    def login(self, uid='owner'):
        with self.client.session_transaction() as s: s['uid'] = uid

    def call(self, body=None, origin='http://localhost'):
        return self.client.post('/api/agents/host/office', json=body or {'operation': 'snapshot', 'args': {}}, headers={'Origin': origin})

    def test_owner_auth_and_origin(self):
        self.assertEqual(self.call().status_code, 401)
        self.login('other'); self.assertEqual(self.call().status_code, 404)
        self.login(); self.assertEqual(self.call(origin='https://elsewhere.example').status_code, 403)

    def test_requires_live_verified_host(self):
        self.login(); self.registry['host']['trust_state'] = 'unsigned'
        self.assertEqual(self.call().status_code, 403)
        self.registry['host']['trust_state'] = 'verified'; self.gateways.clear()
        self.assertEqual(self.call().status_code, 503)

    def test_relay_is_bounded(self):
        self.login()
        with patch('mesh_office.control_relay.dispatch', return_value=({'ok': True, 'result': {'snapshot': {}}}, 200)) as relay:
            self.assertEqual(self.call().status_code, 200)
            self.assertEqual(relay.call_args.args[1], 'factory.office')
            self.assertEqual(self.call({'operation': 'shell', 'args': {}}).status_code, 400)
            relay.assert_called_once()

    def test_linked_role_uses_same_host_office_and_cannot_cross_owner(self):
        self.login()
        self.registry['host--codex']={'owner_id':'owner','trust_state':'verified','control_center_gateway':'host'}
        with patch('mesh_office.control_relay.dispatch',return_value=({'ok':True},200)) as relay:
            r=self.client.post('/api/agents/host--codex/office',json={'operation':'orchestrator.set','args':{'id':'runtime-codex'}},headers={'Origin':'http://localhost'})
            self.assertEqual(r.status_code,200)
            self.assertEqual(relay.call_args.args[0],'host')
        self.registry['host']['owner_id']='other'
        r=self.client.post('/api/agents/host--codex/office',json={'operation':'snapshot','args':{}},headers={'Origin':'http://localhost'})
        self.assertEqual(r.status_code,403)
