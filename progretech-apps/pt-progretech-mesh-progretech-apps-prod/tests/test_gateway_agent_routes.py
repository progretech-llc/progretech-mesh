import unittest
from unittest.mock import patch
from test_gateway_agents import pem

class EnrollmentRouteTests(unittest.TestCase):
    def setUp(self):
        import main
        self.main=main
        self.registry=main.DEV_AGENT_REGISTRY.copy();self.gateways=main.GATEWAY_SOCKETS.copy()
        main.DEV_AGENT_REGISTRY.clear();main.GATEWAY_SOCKETS.clear()
        main.DEV_AGENT_REGISTRY['host']={'id':'host','name':'Host','owner_id':'owner','trust_state':'verified','public_key':pem(), 'identified_agents':[{'id':'host--mak','name':'Mak','role':'Builder'}]}
        main.GATEWAY_SOCKETS['host']=object()
        self.client=main.app.test_client()
        with self.client.session_transaction() as session:session['mesh_user']={'id':'owner','display_name':'Owner'}
        self.payload={'name':'Mak','gateway_id':'host','gateway_candidate_id':'host--mak','agent_id':'host--mak','public_key':pem(),'codeseal_evidence':{'manifest':{'mesh_identity':{'agent_id':'host--mak'}}}}
        self.verification={'valid':True,'state':'verified','provider':'codeseal','reason':'explicit test fixture'}
    def tearDown(self):
        self.main.DEV_AGENT_REGISTRY.clear();self.main.DEV_AGENT_REGISTRY.update(self.registry)
        self.main.GATEWAY_SOCKETS.clear();self.main.GATEWAY_SOCKETS.update(self.gateways)
    def test_enroll_one_then_remove_it_from_dropdown(self):
        self.assertEqual(len(self.client.get('/api/gateways/identified-agents').json['candidates']),1)
        with patch('main.verify_runtime_agent_identity',return_value=self.verification):
            response=self.client.post('/api/agents/enroll',json=self.payload,headers={'Origin':'http://localhost'})
        self.assertEqual(response.status_code,201,response.json)
        row=self.main.DEV_AGENT_REGISTRY['host--mak']
        self.assertEqual(row['public_key'],self.payload['public_key'].strip());self.assertEqual(row['owner_id'],'owner')
        self.assertTrue(row['gateway_enrollment']);self.assertEqual(self.client.get('/api/gateways/identified-agents').json['candidates'],[])
    def test_legacy_identity_and_disconnected_during_verification_fail_closed(self):
        with patch('main.verify_runtime_agent_identity',return_value={**self.verification,'provider':'development'}):
            self.assertEqual(self.client.post('/api/agents/enroll',json=self.payload,headers={'Origin':'http://localhost'}).status_code,400)
        def verify(*args):
            self.main.GATEWAY_SOCKETS.clear();return self.verification
        with patch('main.verify_runtime_agent_identity',side_effect=verify):
            self.assertEqual(self.client.post('/api/agents/enroll',json=self.payload,headers={'Origin':'http://localhost'}).status_code,409)
        self.assertNotIn('host--mak',self.main.DEV_AGENT_REGISTRY)

