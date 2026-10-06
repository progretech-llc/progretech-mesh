import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from control_center.memory_search import dispatch, validate
from control_center.provider import AgentControlProvider
from mesh_local_host import LocalHost


class AgentMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.home=Path(self.tmp.name)
        self.p=AgentControlProvider(self.home/'profiles',{'rend':'main','rend--lyra':'researcher'},lambda _: {},lambda *a: {})
        self.db=self.home/'palace.db'
        with sqlite3.connect(self.db) as db:
            db.execute('CREATE TABLE memories(memory_id TEXT,title TEXT,content TEXT,author_id TEXT,project_id TEXT,scope TEXT,status TEXT,author_type TEXT,provenance_type TEXT,provenance_ref TEXT,created_at TEXT,confidence TEXT)')
            db.execute('CREATE VIRTUAL TABLE memory_fts USING fts5(memory_id UNINDEXED,title,content)')
            for mid,author,scope,status,project in [('shared','lyra','project','active','ProgreTech'),('private','lyra','agent','active','ProgreTech'),('other','rend','project','active','ProgreTech'),('old','lyra','project','retracted','ProgreTech'),('foreign','lyra','project','active','Other')]:
                db.execute('INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(mid,'fixture <script>','fixture context',author,project,scope,status,'agent','fixture','fixture:source','2026-10-01','high'))
                db.execute('INSERT INTO memory_fts VALUES(?,?,?)',(mid,'fixture','fixture context'))
        cfg=self.home/'.local/share/progretech/mempalace-runtime/mempalace/config.example.json';cfg.parent.mkdir(parents=True);cfg.write_text(json.dumps({'database_path':str(self.db)}))
    def tearDown(self):self.tmp.cleanup()
    def call(self,action,args={},aid='rend--lyra'):return dispatch(self.p,self.home,aid,action,args)
    def test_consent_exact_author_scope_project_and_revocation(self):
        self.assertFalse(self.call('memory.status')['shared'])
        with self.assertRaisesRegex(ValueError,'sharing_required'):self.call('memory.search',{'query':'fixture','project':'ProgreTech'})
        self.call('memory.share',{'enabled':True})
        self.assertFalse(self.call('memory.status',aid='rend')['shared'])
        rows=self.call('memory.search',{'query':'fixture','project':'ProgreTech'})['records']
        self.assertEqual([r['memory_id'] for r in rows],['shared'])
        self.assertEqual((self.home/'profiles/rend--lyra.communication.json').stat().st_mode&0o777,0o600)
        self.call('memory.share',{'enabled':False})
        with self.assertRaisesRegex(ValueError,'sharing_required'):self.call('memory.search',{'query':'fixture','project':'ProgreTech'})
    def test_no_database_created_and_no_query_language_injection(self):
        self.call('memory.share',{'enabled':True})
        self.assertEqual(self.call('memory.search',{'query':'fixture OR private','project':'ProgreTech'})['records'],[])
        self.db.unlink();self.assertFalse(self.call('memory.status')['available']);self.assertFalse(self.db.exists())
    def test_untrusted_args(self):
        for action,args in [('memory.share',{'enabled':1}),('memory.search',{'query':'x','project':'Other'}),('memory.search',{'query':'x'*201,'project':'ProgreTech'}),('memory.search',{'query':'fixture','project':'ProgreTech','author':'rend'}),('memory.status',{'scope':'agent'})]:
            with self.assertRaises(ValueError):validate(action,args)
    def test_local_transport_exact_target_and_no_cloud_credentials(self):
        h=LocalHost(self.home);reg={};gateways={}
        with patch.object(h,'call',return_value={'ok':True,'agents':[{'id':'rend','name':'Rend'},{'id':'rend--lyra','name':'Reviewer','mesh_runtime':{'sleeping':False}}]}):h.refresh(reg,gateways)
        self.assertEqual(set(reg),{'rend','rend--lyra'})
        self.assertEqual(reg['rend']['state'],'unknown')
        self.assertNotIn('Awake',reg['rend']['phase'])
        self.assertEqual(reg['rend--lyra']['owner_id'],'local-edwin')
        self.assertEqual(h.send('rend',{'type':'control_center_request','payload':{'agent_id':'other'}}),(False,'agent_binding_required'))
        h.last=0
        with patch.object(h,'call',side_effect=OSError):h.refresh(reg,gateways)
        self.assertNotIn('rend',gateways);self.assertEqual(reg['rend']['transport'],'not-connected')

    def test_local_transport_forwards_bounded_mission_control_requests(self):
        from mesh_factory_control import FactoryRelay
        import mesh_factory_control
        h=LocalHost(self.home)
        relay=FactoryRelay(timeout=.01)
        prior=mesh_factory_control.factory_relay
        mesh_factory_control.factory_relay=relay
        self.addCleanup(setattr,mesh_factory_control,'factory_relay',prior)
        with patch.object(h,'call',return_value={'ok':True,'result':{'agents':[]}}) as call:
            result,status=relay.dispatch('rend','factory.status',{},h.send)
        self.assertEqual(status,200)
        self.assertTrue(result['ok'])
        call.assert_called_once_with('/api/factory/control',{'action':'factory.status','args':{}})
        self.assertEqual(relay.pending,{})

    def test_local_transport_rejects_non_host_factory_target(self):
        h=LocalHost(self.home)
        message={'type':'factory_control_request','request_id':'fixture',
                 'payload':{'action':'factory.status','args':{}}}
        self.assertEqual(h.send('rend--lyra',message),(False,'local_control_only'))

class CloudMemoryTests(unittest.TestCase):
    def test_authenticated_memory_relay_is_ephemeral_and_origin_scoped(self):
        import main
        registry=main.DEV_AGENT_REGISTRY.copy();gateways=main.GATEWAY_SOCKETS.copy()
        try:
            main.DEV_AGENT_REGISTRY.clear();main.GATEWAY_SOCKETS.clear()
            main.DEV_AGENT_REGISTRY.update({'rend':{'id':'rend','owner_id':'owner','trust_state':'verified'},'rend--lyra':{'id':'rend--lyra','owner_id':'owner','control_center_gateway':'rend','trust_state':'verified'}})
            main.GATEWAY_SOCKETS['rend']=object()
            client=main.app.test_client()
            with client.session_transaction() as session:session['mesh_user']={'id':'owner'}
            body={'action':'memory.search','args':{'query':'fixture','project':'ProgreTech'}}
            events={k:list(v) for k,v in main.EVENT_BUFFERS.items()}
            with patch('mesh_agent_management.control_relay.dispatch',return_value=({'ok':True,'result':{'records':[{'content':'fixture'}]}},200)) as relay:
                response=client.post('/api/agents/rend--lyra/management',json=body,headers={'Origin':'http://localhost'})
                self.assertEqual(response.status_code,200);self.assertIn('no-store',response.headers['Cache-Control'])
                self.assertEqual(relay.call_args.args[:3],('rend--lyra','memory.search',body['args']))
                self.assertEqual(main.EVENT_BUFFERS,events)
                self.assertEqual(client.post('/api/agents/rend--lyra/management',json=body,headers={'Origin':'https://evil.invalid'}).status_code,403)
                with client.session_transaction() as session:session['mesh_user']={'id':'different-owner'}
                self.assertEqual(client.post('/api/agents/rend--lyra/management',json=body,headers={'Origin':'http://localhost'}).status_code,404)
        finally:
            main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY.update(registry)
            main.GATEWAY_SOCKETS.clear();main.GATEWAY_SOCKETS.update(gateways)
