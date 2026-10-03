import unittest
from unittest.mock import patch
import main

class RoleAPITests(unittest.TestCase):
    def setUp(self):
        self.old=main.DEV_AGENT_REGISTRY.copy()
        main.DEV_AGENT_REGISTRY.clear()
        main.DEV_AGENT_REGISTRY['rend']={'owner_id':'owner','trust_state':'verified','transport':'connected'}
        self.client=main.app.test_client()
        self.token=main.issue_ide_token('owner','rend')['token']
        self.headers={'Authorization':'Bearer '+self.token}
    def tearDown(self):
        main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY.update(self.old)
    def test_models_aliases_and_legacy(self):
        response=self.client.get('/v1/models',headers=self.headers)
        self.assertEqual(response.status_code,200)
        models={x['id'] for x in response.json['data']}
        self.assertTrue({'rend','lyra','mak','progre','imagen','codex','odexi','rend-code','rend-research'}<=models)
    def test_auth_and_owner_binding(self):
        self.assertEqual(self.client.get('/v1/models').status_code,401)
        main.DEV_AGENT_REGISTRY['rend']['owner_id']='someone-else'
        self.assertEqual(self.client.get('/v1/models',headers=self.headers).status_code,401)
    def test_unverified(self):
        main.DEV_AGENT_REGISTRY['rend']['trust_state']='unsigned'
        self.assertEqual(self.client.get('/v1/models',headers=self.headers).status_code,401)
    def test_alias_dispatch_preserves_messages_and_tools(self):
        completion={'id':'x','choices':[{'message':{'role':'assistant','content':'ok'},'finish_reason':'stop'}]}
        with patch.object(main,'dispatch_ide_chat',return_value=(True,'ok',{'payload':{'ok':True,'completion':completion}})) as dispatch:
            for model in ['rend','lyra','mak','progre','imagen','codex','odexi']:
                body={'model':model,'messages':[{'role':'system','content':'Instructions'},{'role':'user','content':'Hi'}], 'tools':[{'type':'function','function':{'name':'lookup'}}]}
                response=self.client.post('/v1/chat/completions',headers=self.headers,json=body)
                self.assertEqual(response.status_code,200)
                self.assertEqual(dispatch.call_args.args[0],'rend')
                self.assertEqual(dispatch.call_args.args[1],{**body,'stream':False})
    def test_unknown_model_and_invalid_body_rejected(self):
        for body in [[],{'model':'arbitrary-model','messages':[{}]}]:
            self.assertEqual(self.client.post('/v1/chat/completions',headers=self.headers,json=body).status_code,400)
    def test_stream_preserves_tool_calls(self):
        completion={'id':'x','choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'a','type':'function','function':{'name':'lookup','arguments':'{}'}}]},'finish_reason':'tool_calls'}]}
        with patch.object(main,'dispatch_ide_chat',return_value=(True,'ok',{'payload':{'ok':True,'completion':completion}})):
            response=self.client.post('/v1/chat/completions',headers=self.headers,json={'model':'mak','messages':[{'role':'user','content':'Hi'}],'stream':True})
            self.assertEqual(response.status_code,200)
            self.assertIn(b'"tool_calls"',response.data)
            self.assertIn(b'"index":0',response.data)
            self.assertIn(b'[DONE]',response.data)
    def test_other_session_cannot_mint_owner_token(self):
        with self.client.session_transaction() as session:session['mesh_user']={'id':'someone-else','display_name':'Other'}
        self.assertEqual(self.client.post('/api/agents/rend/ide/token').status_code,404)
    def test_owner_mints_token(self):
        with self.client.session_transaction() as session:session['mesh_user']={'id':'owner','display_name':'Owner'}
        self.assertEqual(self.client.post('/api/agents/rend/ide/token').status_code,201)

if __name__=='__main__':unittest.main()
