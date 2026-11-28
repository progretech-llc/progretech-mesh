import copy
import tempfile
import unittest
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, session

import mesh_control_center as cloud
from control_center.provider import AgentControlProvider, register_provider_routes


def profile(**changes):
    return {'role': 'Research', 'models': ['ollama/example'], 'workstation': 'yes', 'stack': 'custom',
            'voice': {'provider': 'kokoro', 'voice': 'af_heart', 'pitch': 1},
            'permissions': ['profile', 'inventory', 'speaker'], **changes}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.calls = []
        self.reads = []
        def discover(runtime):
            self.reads.append(runtime)
            return {'models': [f'local/{runtime}']}
        def execute(runtime, action, args, saved):
            self.calls.append((runtime, action, args, copy.deepcopy(saved)))
            return {'played': True}
        self.provider = AgentControlProvider(self.temp.name, {'lyra': 'researcher', 'rend': 'main'},
            discover, execute, ['voice.preview', 'voice.start', 'models.list'])
    def tearDown(self):
        self.temp.cleanup()
    def test_profiles_persist_and_do_not_change_other_agents(self):
        self.provider.dispatch('lyra', 'profile.save', profile())
        same_disk = AgentControlProvider(self.temp.name, self.provider.bindings, lambda _: {}, lambda *a: {})
        self.assertEqual(same_disk.dispatch('lyra', 'profile.get', {})['profile']['voice']['voice'], 'af_heart')
        self.assertEqual(self.provider.dispatch('rend', 'profile.get', {})['profile']['permissions'], [])
        self.assertEqual(self.provider.dispatch('rend', 'profile.get', {})['profile']['voice']['voice'], 'am_onyx')
        self.assertEqual(Path(self.temp.name, 'lyra.json').stat().st_mode & 0o777, 0o600)
    def test_inventory_requires_consent_and_correct_runtime(self):
        self.provider.dispatch('lyra', 'profile.get', {})
        self.assertEqual(self.reads, [])
        self.provider.dispatch('lyra', 'profile.save', profile())
        data = self.provider.dispatch('lyra', 'profile.get', {})
        self.assertEqual(data['discovered']['models'], ['local/researcher'])
        self.assertEqual(self.reads, ['researcher'])
    def test_saved_voice_is_selected_agent_only(self):
        self.provider.dispatch('lyra', 'profile.save', profile())
        self.provider.dispatch('lyra', 'voice.preview', {'text': 'Hello'})
        self.assertEqual(self.calls[0][0], 'researcher')
        self.assertEqual(self.calls[0][3]['voice']['voice'], 'af_heart')
        with self.assertRaisesRegex(ValueError, 'permission_required'):
            self.provider.dispatch('rend', 'voice.preview', {'text': 'Hello'})
    def test_host_controls_require_both_grants_and_workstation(self):
        for changes, error in [({}, 'permission_required'),
            ({'permissions': ['profile','microphone']}, 'workstation_permission_required'),
            ({'permissions': ['profile','microphone','workstation'], 'workstation': 'no'}, 'workstation_permission_required')]:
            self.provider.dispatch('lyra','profile.save',profile(**changes))
            with self.assertRaisesRegex(ValueError,error):
                self.provider.dispatch('lyra','voice.start',{})
        self.assertEqual(self.calls, [])
    def test_revocation_blocks_future_preview(self):
        p = profile()
        self.provider.dispatch('lyra','profile.save',p)
        self.provider.dispatch('lyra','profile.save',{**p,'permissions':[]})
        with self.assertRaisesRegex(ValueError,'permission_required'):
            self.provider.dispatch('lyra','voice.preview',{'text':'Hello'})
    def test_cannot_store_new_details_without_consent(self):
        with self.assertRaisesRegex(ValueError,'profile_permission_required'):
            self.provider.dispatch('lyra','profile.save',profile(permissions=[]))
        self.assertFalse(Path(self.temp.name,'lyra.json').exists())
    def test_unbound_and_path_traversal_are_rejected(self):
        for agent in ['mak', '../lyra', '', 'rend/../../lyra']:
            with self.assertRaisesRegex(ValueError,'agent_binding_required'):
                self.provider.dispatch(agent,'profile.get',{})
    def test_invalid_profile_is_never_saved(self):
        for pitch in [True, float('nan'), float('inf'), 7]:
            p = profile(); p['voice']['pitch'] = pitch
            with self.assertRaises(ValueError):self.provider.dispatch('lyra','profile.save',p)
        with self.assertRaises(ValueError):self.provider.dispatch('lyra','profile.save',profile(permissions=['shell']))
        self.assertFalse(Path(self.temp.name,'lyra.json').exists())
    def test_provider_auth_and_target_binding(self):
        app = Flask(__name__)
        register_provider_routes(app, self.provider, lambda:'test-token')
        client = app.test_client()
        body = {'agent_id':'lyra','action':'profile.get','args':{}}
        self.assertEqual(client.post('/api/mesh/control-center',json=body).status_code,401)
        headers = {'X-ProgreTech-Mesh-Local-Token':'test-token'}
        self.assertEqual(client.post('/api/mesh/control-center',json=body,headers=headers).json['result']['agent_id'],'lyra')
        body['agent_id'] = 'mak'
        self.assertEqual(client.post('/api/mesh/control-center',json=body,headers=headers).status_code,400)
    def test_outside_stack_details_do_not_claim_voice_readiness(self):
        p=profile();p['voice']={'provider':'my-tts','voice':'lyra-custom','pitch':0}
        self.provider.dispatch('lyra','profile.save',p)
        data=self.provider.dispatch('lyra','profile.get',{})
        self.assertEqual(data['profile']['voice']['voice'],'lyra-custom')
        self.assertNotIn('voice.preview',data['capabilities'])
        with self.assertRaisesRegex(ValueError,'voice_provider_unavailable'):
            self.provider.dispatch('lyra','voice.preview',{'text':'Hello'})


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder='../templates', static_folder='../static')
        self.app.secret_key = 'test'
        self.registry = {'lyra':{'id':'lyra','name':'Lyra','owner_id':'owner','trust_state':'verified'}}
        self.gateways = {'lyra':object()}
        self.sent = []
        self.old = cloud.control_relay
        cloud.control_relay = cloud.ControlRelay(timeout=.005)
        def auth(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                if not session.get('uid'):return jsonify(ok=False),401
                return view(*args,**kwargs)
            return wrapped
        def send(agent, msg):
            self.sent.append((agent,msg))
            cloud.control_relay.resolve(agent,{'type':'control_center_response','request_id':msg['request_id'],
                'payload':{'ok':True,'result':{'agent_id':agent}}})
            return True,None
        cloud.register_control_center_routes(self.app,auth,lambda:session.get('uid'),self.registry,self.gateways,send)
        self.client = self.app.test_client()
    def tearDown(self):cloud.control_relay = self.old
    def login(self, uid='owner'):
        with self.client.session_transaction() as s:s['uid']=uid
    def post(self, action='profile.get', args=None, origin='http://localhost'):
        return self.client.post('/api/agents/lyra/control-center',json={'action':action,'args':args or {}},headers={'Origin':origin})
    def test_auth_and_cross_owner(self):
        self.assertEqual(self.post().status_code,401)
        self.login('someone-else')
        self.assertEqual(self.post().status_code,404)
        self.assertEqual(self.client.get('/agents/lyra/control-center').status_code,404)
        self.assertFalse(self.sent)
    def test_unbound_unverified_offline(self):
        self.login()
        for field,value,expected in [('owner_id','',404),('trust_state','unsigned',403)]:
            old = self.registry['lyra'][field];self.registry['lyra'][field]=value
            self.assertEqual(self.post().status_code,expected)
            self.registry['lyra'][field]=old
        self.gateways.clear();self.assertEqual(self.post().status_code,503)
        self.assertFalse(self.sent)
    def test_csrf_and_bad_actions(self):
        self.login()
        self.assertEqual(self.post(origin='https://evil.example').status_code,403)
        self.assertEqual(self.post(origin='').status_code,403)
        self.assertEqual(self.post('voice.settings').status_code,400)
        self.assertEqual(self.post(args={'agent_id':'rend'}).status_code,400)
        self.assertFalse(self.sent)
    def test_availability_controls_preserve_auth_origin_and_agent_scope(self):
        self.assertEqual(self.post('runtime.wake').status_code,401)
        self.login()
        for action in ('runtime.status','runtime.wake','runtime.sleep'):
            self.assertEqual(self.post(action).status_code,200)
            self.assertEqual(self.sent[-1][1]['payload']['agent_id'],'lyra')
            self.assertEqual(self.post(action,origin='https://evil.example').status_code,403)
            self.assertEqual(self.post(action,args={'agent_id':'rend'}).status_code,400)
        self.assertEqual(self.post('communication.job',{'job_id':'a'*32}).status_code,200)
        self.assertEqual(self.post('communication.job',{'job_id':'bad'}).status_code,400)
        self.login('other')
        self.assertEqual(self.post('runtime.wake').status_code,404)

    def test_availability_roster_does_not_invent_awake_or_expose_private_fields(self):
        self.assertEqual(cloud.availability_status({}),{})
        result=cloud.availability_status({'mesh_runtime':{'sleeping':None,'controls_available':False,'model':'configured','private':'hidden'}})
        self.assertIsNone(result['sleeping'])
        self.assertEqual(result['model'],'configured')
        self.assertNotIn('private',result)

    def test_selected_agent_roundtrip(self):
        self.login();self.assertEqual(self.post().json['result']['agent_id'],'lyra')
        self.assertEqual(self.sent[0][0],'lyra');self.assertEqual(cloud.control_relay.pending,{})
    def test_offline_page_has_early_requirements_and_permissions(self):
        self.login();self.gateways.clear()
        response = self.client.get('/agents/lyra/control-center')
        self.assertEqual(response.status_code,200)
        for text in [b'Minimum Requirements',b'Permissions &amp; data',b'Use Progretech',b'Gateway offline']:
            self.assertIn(text,response.data)
        self.assertFalse(self.sent)
    def test_wrong_agent_response_cannot_resolve(self):
        relay = cloud.ControlRelay(timeout=.001)
        def send(agent,msg):
            self.assertFalse(relay.resolve('rend',{'type':'control_center_response','request_id':msg['request_id'],'payload':{'ok':True}}))
            return True,None
        self.assertEqual(relay.dispatch('lyra','profile.get',{},send)[1],504)
        self.assertEqual(relay.pending,{})
    def test_linked_role_uses_parent_gateway_and_its_own_profile(self):
        self.login()
        cloud.register_gateway_agents('lyra',{'agents':[{'id':'lyra--worker','name':'Worker','role':'Research'}]},self.registry)
        self.registry['lyra--worker']={'id':'lyra--worker','name':'Worker','owner_id':'owner','trust_state':'verified','control_center_gateway':'lyra','gateway_enrollment':True}
        response=self.client.post('/api/agents/lyra--worker/control-center',json={'action':'profile.get','args':{}},headers={'Origin':'http://localhost'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.sent[0][0],'lyra')
        self.assertEqual(self.sent[0][1]['payload']['agent_id'],'lyra--worker')
        self.registry['lyra']['trust_state']='revoked'
        self.assertEqual(self.client.post('/api/agents/lyra--worker/control-center',json={'action':'profile.get'},headers={'Origin':'http://localhost'}).status_code,403)
    def test_roster_cannot_adopt_other_owners_or_outside_namespace(self):
        self.registry['lyra--taken']={'owner_id':'other'}
        for aid in ['lyra--taken','rend--worker','../../worker']:
            self.assertFalse(cloud.register_gateway_agents('lyra',{'agents':[{'id':aid,'name':'Worker'}]},self.registry))
        self.assertEqual(self.registry['lyra--taken']['owner_id'],'other')
    def test_roster_links_runtime_without_independent_enrollment_and_preserves_signed_identity(self):
        self.login()
        payload={'agents':[{'id':'lyra--worker','name':'Worker','mesh_runtime':{'sleeping':True,'controls_available':True,'model':'ollama/fixture'}}]}
        cloud.register_gateway_agents('lyra',payload,self.registry)
        self.assertTrue(self.registry['lyra--worker']['gateway_linked'])
        self.assertFalse(self.registry['lyra--worker'].get('gateway_enrollment',False))
        self.assertEqual(self.registry['lyra--worker']['runtime_id'],'worker')
        candidates=self.client.get('/api/gateways/identified-agents').json['candidates']
        self.assertEqual(candidates[0]['id'],'lyra--worker')
        self.registry['lyra--worker']={'id':'lyra--worker','owner_id':'owner','control_center_gateway':'lyra','gateway_enrollment':True,'fingerprint':'own-key','public_key':'own-pem','codeseal_evidence':{'seal':'own'}}
        cloud.register_gateway_agents('lyra',payload,self.registry)
        self.assertEqual(self.registry['lyra--worker']['fingerprint'],'own-key')
        self.assertTrue(self.registry['lyra--worker']['mesh_runtime']['sleeping'])
        self.assertEqual(self.registry['lyra--worker']['model'],'ollama/fixture')
        self.assertEqual(self.client.get('/api/gateways/identified-agents').json['candidates'],[])
        cloud.register_gateway_agents('lyra',{'agents':[]},self.registry)
        self.assertIn('lyra--worker',self.registry)

    def test_roster_removes_missing_host_link_but_retains_signed_role(self):
        cloud.register_gateway_agents('lyra',{'agents':[{'id':'lyra--worker','name':'Worker'}]},self.registry)
        self.assertIn('lyra--worker',self.registry)
        cloud.register_gateway_agents('lyra',{'agents':[]},self.registry)
        self.assertNotIn('lyra--worker',self.registry)
    def test_host_linked_role_uses_verified_gateway_and_loses_access_when_removed(self):
        self.login()
        cloud.register_gateway_agents('lyra',{'agents':[{'id':'lyra--worker','name':'Worker'}]},self.registry)
        response=self.client.post('/api/agents/lyra--worker/control-center',json={'action':'profile.get','args':{}},headers={'Origin':'http://localhost'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.sent[-1][0],'lyra')
        self.assertEqual(self.sent[-1][1]['payload']['agent_id'],'lyra--worker')
        cloud.register_gateway_agents('lyra',{'agents':[]},self.registry)
        self.assertEqual(self.client.post('/api/agents/lyra--worker/control-center',json={'action':'profile.get','args':{}},headers={'Origin':'http://localhost'}).status_code,404)

    def test_roster_relays_only_memory_receipt_metadata_for_host_and_signed_role(self):
        self.registry['lyra--worker']={'id':'lyra--worker','owner_id':'owner',
            'control_center_gateway':'lyra','gateway_enrollment':True}
        receipt={'latest_status':'recorded','memory_id':'87ee2d66-92ef-492d-878f-dd374ba1e6a4',
            'recall_verified':True,'activity_kind':'runtime_activity','project':'ProgreTech',
            'private_body':'excluded','last_verified':{'activity_recall_verified':True,
                'activity_memory_id':'87ee2d66-92ef-492d-878f-dd374ba1e6a4','raw_output':'excluded'}}
        payload={'agents':[{'id':aid,'name':'Lyra','mesh_runtime':{'memory':receipt}}
            for aid in ('lyra','lyra--worker')]}
        self.assertTrue(cloud.register_gateway_agents('lyra',payload,self.registry))
        for aid in ('lyra','lyra--worker'):
            observed=self.registry[aid]['mesh_runtime']['memory']
            self.assertTrue(observed['recall_verified'])
            self.assertEqual(observed['memory_id'],receipt['memory_id'])
            self.assertNotIn('private_body',observed)
            self.assertNotIn('raw_output',observed['last_verified'])

    def test_gateway_candidates_are_owner_scoped_and_require_connection(self):
        self.login();self.registry['lyra']['owner_id']='other'
        self.registry['lyra']['identified_agents']=[{'id':'lyra--worker','name':'Worker'}]
        self.assertEqual(self.client.get('/api/gateways/identified-agents').json['candidates'],[])
        self.registry['lyra']['owner_id']='owner';self.gateways.clear()
        self.assertEqual(self.client.get('/api/gateways/identified-agents').json['candidates'],[])

    def test_retiring_binding_removes_only_host_roles(self):
        cloud.register_gateway_agents('lyra',{'agents':[{'id':'lyra--worker','name':'Worker'}]},self.registry)
        cloud.register_gateway_agents('lyra',{'agents':[]},self.registry)
        self.assertNotIn('lyra--worker',self.registry)
        self.assertIn('lyra',self.registry)
    def test_role_activity_is_distinct_from_connected_transport(self):
        self.registry['lyra--worker']={'id':'lyra--worker','control_center_gateway':'lyra','gateway_enrollment':True,'fingerprint':'worker-signature','owner_id':'owner'}
        cloud.register_gateway_agents('lyra',{'agents':[{'id':'lyra--worker','name':'Worker','activity':{'state':'active','source':'openclaw-native-event','task_id':'workday-test'}}]},self.registry)
        self.assertEqual(self.registry['lyra--worker']['state'],'working')
        self.assertEqual(self.registry['lyra--worker']['transport'],'connected')
        self.assertEqual(self.registry['lyra--worker']['fingerprint'],'worker-signature')
        cloud.register_gateway_agents('lyra',{'agents':[{'id':'lyra--worker','name':'Worker','activity':{'state':'unknown'}}]},self.registry)
        self.assertEqual(self.registry['lyra--worker']['state'],'unknown')
    def test_gateway_activity_does_not_overwrite_identity(self):
        cloud.register_gateway_agents('lyra',{'agents':[{'id':'lyra','activity':{'state':'idle','source':'workday'}},{'id':'lyra--worker','name':'Worker'}]},self.registry)
        self.assertEqual(self.registry['lyra']['state'],'idle')
        self.assertEqual(self.registry['lyra']['owner_id'],'owner')


if __name__ == '__main__':unittest.main()
