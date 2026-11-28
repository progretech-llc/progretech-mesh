import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import main
from control_center.provider import AgentControlProvider
from control_center.management import preferences


class HostManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.calls = []
        self.p = AgentControlProvider(self.temp.name, {'rend': 'main', 'rend--researcher': 'researcher'},
            lambda role: {'models': ['local/' + role], 'communication_roles': [role]},
            lambda role, action, args, profile: self.calls.append((role, action, args, profile)) or {'reply': role})
    def tearDown(self): self.temp.cleanup()
    def test_settings_are_independent_and_persisted(self):
        self.p.dispatch('rend--researcher', 'communication.save', {'role': 'researcher', 'model': 'local/researcher'})
        self.assertEqual(preferences(self.p, 'rend')['model'], 'default')
        self.assertEqual(preferences(self.p, 'rend--researcher')['model'], 'local/researcher')
        self.assertEqual(Path(self.temp.name, 'rend--researcher.communication.json').stat().st_mode & 0o777, 0o600)
    def test_cannot_impersonate_role_or_inject_model(self):
        for role, model in [('main', 'default'), ('researcher', 'external/unknown')]:
            with self.assertRaisesRegex(ValueError, 'communication_selection_unavailable'):
                self.p.dispatch('rend--researcher', 'communication.save', {'role': role, 'model': model})
    def test_chat_uses_exact_binding_and_independent_context(self):
        self.assertEqual(self.p.dispatch('rend--researcher', 'communication.chat', {'text': 'Hello'})['reply'], 'researcher')
        self.assertEqual(self.calls[0][3]['agent_id'], 'rend--researcher')
    def test_remove_survives_reload_and_blocks_future_calls(self):
        self.p.dispatch('rend--researcher', 'enrollment.remove', {})
        with self.assertRaisesRegex(ValueError, 'mesh_enrollment_removed'):
            self.p.dispatch('rend--researcher', 'communication.chat', {'text': 'Hi'})
        self.assertTrue(preferences(self.p, 'rend')['enabled'])
    def test_arguments_bounded_before_execution(self):
        for args in [{'text': 'x'*4001}, {'text': 'hello', 'command': 'sh'}, {'text': True}]:
            with self.assertRaises(ValueError): self.p.dispatch('rend', 'communication.chat', args)
        self.assertEqual(self.calls, [])


class CloudManagementTests(unittest.TestCase):
    def setUp(self):
        self.registry = main.DEV_AGENT_REGISTRY.copy(); self.gateways = main.GATEWAY_SOCKETS.copy()
        main.DEV_AGENT_REGISTRY.clear(); main.GATEWAY_SOCKETS.clear()
        main.DEV_AGENT_REGISTRY.update({'rend': {'id':'rend','owner_id':'owner','trust_state':'verified'},
          'rend--researcher': {'id':'rend--researcher','owner_id':'owner','control_center_gateway':'rend','trust_state':'verified'}})
        main.GATEWAY_SOCKETS['rend'] = object()
        self.client = main.app.test_client()
        with self.client.session_transaction() as s: s['mesh_user'] = {'id':'owner','display_name':'Owner'}
        self.headers = {'Origin':'http://localhost'}
    def tearDown(self):
        main.DEV_AGENT_REGISTRY.clear(); main.DEV_AGENT_REGISTRY.update(self.registry)
        main.GATEWAY_SOCKETS.clear(); main.GATEWAY_SOCKETS.update(self.gateways)
    def test_role_message_targets_parent_gateway(self):
        with patch('mesh_agent_management.control_relay.dispatch', return_value=({'ok':True,'result':{'reply':'Lyra'}},200)) as relay:
            r=self.client.post('/api/agents/rend--researcher/message',json={'text':'Hello'},headers=self.headers)
            self.assertEqual(r.status_code,200); self.assertEqual(r.json['reply'],'Lyra')
            self.assertEqual(relay.call_args.args[0], 'rend--researcher');self.assertEqual(relay.call_args.args[-1], 'rend')
    def test_origin_owner_and_credentials_are_restricted(self):
        self.assertEqual(self.client.post('/api/agents/rend--researcher/management',json={'action':'communication.get'}).status_code,403)
        with self.client.session_transaction() as s: s['mesh_user']={'id':'other','display_name':'Other'}
        self.assertEqual(self.client.post('/api/agents/rend--researcher/management',json={'action':'communication.get'},headers=self.headers).status_code,404)
        self.assertEqual(self.client.post('/api/agents/rend--researcher/pair-token',json={},headers=self.headers).status_code,409)
    def test_remove_only_after_host_acknowledges(self):
        with patch('mesh_agent_management.control_relay.dispatch', return_value=({'ok':False,'error':'host_busy'},502)):
            self.assertEqual(self.client.post('/api/agents/rend--researcher/management',json={'action':'enrollment.remove'},headers=self.headers).status_code,502)
            self.assertIn('rend--researcher',main.DEV_AGENT_REGISTRY)
        with patch('mesh_agent_management.control_relay.dispatch', return_value=({'ok':True,'result':{}},200)):
            self.assertEqual(self.client.post('/api/agents/rend--researcher/management',json={'action':'enrollment.remove'},headers=self.headers).status_code,200)
            self.assertNotIn('rend--researcher',main.DEV_AGENT_REGISTRY);self.assertIn('rend',main.DEV_AGENT_REGISTRY)
    def test_offline_and_malformed_requests_do_not_dispatch(self):
        main.GATEWAY_SOCKETS.clear()
        with patch('mesh_agent_management.control_relay.dispatch') as relay:
            self.assertEqual(self.client.post('/api/agents/rend--researcher/management',json={'action':'communication.get'},headers=self.headers).status_code,503)
            relay.assert_not_called()

if __name__=='__main__':unittest.main()

class FactoryJobTests(unittest.TestCase):
    def test_requires_explicit_host_configuration(self):
        from control_center.factory_jobs import dispatch_factory
        with tempfile.TemporaryDirectory() as home:
            state=dispatch_factory(home,'researcher','factory.providers',{})
            self.assertTrue(all(not p['configured'] for p in state['providers']))
            with self.assertRaisesRegex(ValueError,'not_configured'):
                dispatch_factory(home,'researcher','factory.run',{'provider':'crewai','task':'Plan'})
    def test_factory_job_status_is_role_scoped(self):
        from control_center.factory_jobs import dispatch_factory
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)/'.progretech-mesh/factory-jobs/researcher';root.mkdir(parents=True)
            job='a'*32;(root/(job+'.json')).write_text(json.dumps({'state':'completed'}))
            self.assertEqual(dispatch_factory(home,'researcher','factory.job',{'job_id':job})['state'],'completed')
            with self.assertRaisesRegex(ValueError,'not_found'):
                dispatch_factory(home,'coder','factory.job',{'job_id':job})

class BoundBridgeConversationTests(unittest.TestCase):
    def test_model_override_and_session_target_exact_local_role(self):
        import threading
        from types import SimpleNamespace
        from flask import Flask
        from control_center.rend_bridge import install
        with tempfile.TemporaryDirectory() as home:
            root=Path(home);(root/'.progretech-mesh').mkdir();(root/'.openclaw').mkdir()
            (root/'.progretech-mesh/control-center-bindings.json').write_text(json.dumps({'rend--researcher':'researcher'}))
            cfg={'agents':{'entries':{'researcher':{'model':'local/heavy'}},'defaults':{'models':{'local/heavy':{},'local/light':{}}}},'gateway':{'auth':{'mode':'token','token':'test-only-token'},'port':18789,'http':{'endpoints':{'chatCompletions':{'enabled':True}}}}}
            (root/'.openclaw/openclaw.json').write_text(json.dumps(cfg))
            provider=install(SimpleNamespace(app=Flask(__name__),token=lambda:'fixture',MUTATION_LOCK=threading.Lock(),dispatch=lambda *a:{}),home)
            models=provider.dispatch('rend--researcher','communication.get',{})['models']
            self.assertIn('local/light',models)
            provider.dispatch('rend--researcher','communication.save',{'role':'researcher','model':'local/light'})
            response=SimpleNamespace(read=lambda size:json.dumps({'choices':[{'message':{'content':'reply'}}]}).encode())
            class Context:
                def __enter__(self):return response
                def __exit__(self,*args):pass
            with patch('control_center.rend_bridge.urlopen',return_value=Context()) as transport:
                result=provider.dispatch('rend--researcher','communication.chat',{'text':'Hello'})
                request=transport.call_args.args[0]
                self.assertEqual(request.get_header('X-openclaw-agent-id'),'researcher')
                self.assertEqual(request.get_header('X-openclaw-model'),'local/light')
                self.assertEqual(request.get_header('X-openclaw-session-key'),'agent:researcher:mesh-chat:rend--researcher')
                self.assertEqual(json.loads(request.data)['model'],'openclaw/researcher')
                self.assertEqual(result['reply'],'reply')
                self.assertEqual(transport.call_args.kwargs['timeout'],300)
            with patch('control_center.rend_bridge.urlopen',side_effect=TimeoutError('private diagnostic')):
                with self.assertRaisesRegex(ValueError,'^mesh_runtime_completion_unconfirmed$'):
                    provider.dispatch('rend--researcher','communication.chat',{'text':'Bounded timeout fixture'})
            cfg['gateway']['auth']['token']={'source':'store','provider':'default','id':'fixture-reference'}
            (root/'.openclaw/openclaw.json').write_text(json.dumps(cfg))
            with patch('control_center.mesh_runtime.gateway_agent_reply',return_value='secretref reply') as transport:
                result=provider.dispatch('rend--researcher','communication.chat',{'text':'Hello again'})
                self.assertEqual(result['reply'],'secretref reply')
                self.assertEqual(transport.call_args.args[1:5],('researcher','agent:researcher:mesh-chat:rend--researcher','Hello again',300))
                self.assertEqual(transport.call_args.args[-1],'local/light')
            self.assertEqual(json.loads((root/'.openclaw/openclaw.json').read_text()),cfg)
