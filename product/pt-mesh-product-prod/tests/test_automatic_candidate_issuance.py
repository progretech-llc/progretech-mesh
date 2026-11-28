import unittest
from unittest.mock import patch
from flask import Flask
from mesh_agent_management import register_management_routes

class AutomaticCandidateIssuance(unittest.TestCase):
    def setUp(self):
        app=Flask(__name__);app.secret_key='fixture'
        register_management_routes(app,lambda view:view,lambda:'owner',{}, {}, lambda *a:None)
        self.client=app.test_client();self.headers={'Origin':'http://localhost'}
    def test_empty_or_omitted_token_uses_server_issuer(self):
        for extra in ({},{'api_token':''}):
            with patch('mesh_agent_management.request_codeseal_identity',return_value={'manifest':{}}) as issue:
                r=self.client.post('/api/enrollment/codeseal',json={'identity':{},'signature':'proof',**extra},headers=self.headers)
                self.assertEqual(r.status_code,200);self.assertIsNone(issue.call_args.args[2])
    def test_optional_personal_token_and_no_client_url(self):
        with patch('mesh_agent_management.request_codeseal_identity',return_value={}) as issue:
            r=self.client.post('/api/enrollment/codeseal',json={'identity':{},'signature':'proof','api_token':'ptcs_live_fixture'},headers=self.headers)
            self.assertEqual(r.status_code,200);self.assertEqual(issue.call_args.args[2],'ptcs_live_fixture')
            r=self.client.post('/api/enrollment/codeseal',json={'identity':{},'signature':'proof','url':'https://attacker.invalid'},headers=self.headers)
            self.assertEqual(r.status_code,400)
    def test_missing_issuer_and_cross_origin_fail_closed(self):
        with patch('mesh_agent_management.request_codeseal_identity',side_effect=ValueError('codeseal_issuer_not_configured')):
            r=self.client.post('/api/enrollment/codeseal',json={'identity':{},'signature':'proof'},headers=self.headers)
            self.assertEqual(r.status_code,503)
            self.assertEqual(self.client.post('/api/enrollment/codeseal',json={}).status_code,403)
