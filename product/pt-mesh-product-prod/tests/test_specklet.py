import copy
import json
import tempfile
import unittest
from pathlib import Path
from flask import Flask
from concurrent.futures import ThreadPoolExecutor
from control_center.provider import AgentControlProvider, register_provider_routes
from control_center.specklet import Board, validate, workspace, observe_office
from control_center.office import namespace


class SpeckletTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.home=Path(self.tmp.name)
        self.p=AgentControlProvider(self.home/'profiles',{'host':'main','host--reviewer':'reviewer'},lambda _: {},lambda *args: {})
        self.b=Board(self.p,'host--reviewer')
    def tearDown(self):self.tmp.cleanup()
    def call(self,a,args={}):return self.b.dispatch('specklet.'+a,args)
    def test_default_off_freeze_resume_and_owner_review(self):
        self.assertFalse(self.call('get')['enabled']);self.assertFalse(self.b.path.exists())
        self.b.observe('mission','Title','doing');self.assertFalse(self.b.path.exists())
        self.call('toggle',{'enabled':True});self.b.observe('mission','Title','doing')
        before=self.b.path.read_bytes();self.b.observe('mission','Title','doing');self.assertEqual(before,self.b.path.read_bytes())
        self.call('toggle',{'enabled':False});before=self.b.path.read_bytes();self.b.observe('mission','Title','done');self.assertEqual(before,self.b.path.read_bytes())
        d=self.call('get');self.assertEqual(d['workspace']['tasks'][0]['meshStatus'],'doing')
        with self.assertRaisesRegex(ValueError,'disabled'):self.b.dispatch('specklet.task',{'task':{'id':'mission','status':'done'},'revision':d['revision']},True)
        self.call('toggle',{'enabled':True});self.b.observe('mission','Title','done');self.assertEqual(self.call('get')['workspace']['tasks'][0]['status'],'done')
        self.assertEqual(self.b.path.stat().st_mode&0o777,0o600)
        workspace(json.loads(self.b.path.read_text()))
        self.assertFalse(Board(self.p,'host').dispatch('specklet.get',{})['enabled'])
    def test_specklet_round_trip_and_revision_conflict(self):
        d=self.call('task',{'revision':0,'task':{'title':'Original','status':'doing'}})
        incoming=copy.deepcopy(d['workspace']);incoming['tasks'][0].update(title='Owner scope',notes='Changed scope',status='done',position=5)
        e=self.call('import',{'revision':d['revision'],'workspace':incoming})
        self.assertEqual(e['workspace']['tasks'][0]['meshStatus'],'done');self.assertEqual(e['workspace']['tasks'][0]['position'],5)
        self.assertEqual(workspace(e['workspace'])['format'],'specklet-browser-workspace')
        with self.assertRaisesRegex(ValueError,'revision_conflict'):self.call('import',{'revision':d['revision'],'workspace':incoming})
        self.assertFalse(e['enabled'])
    def test_owner_edit_not_reverted_by_same_observation(self):
        self.call('toggle',{'enabled':True});self.b.observe('mission','Original','doing')
        d=self.call('get');self.call('task',{'revision':d['revision'],'task':{'id':'mission','title':'Changed scope','status':'done'}})
        self.b.observe('mission','Original','doing');d=self.call('get')
        self.assertEqual(d['workspace']['tasks'][0]['status'],'done')
        self.b.observe('mission','Original','blocked');d=self.call('get');self.assertEqual(d['workspace']['tasks'][0]['title'],'Changed scope');self.assertEqual(d['workspace']['tasks'][0]['meshStatus'],'blocked')
    def test_malformed_import_never_replaces_file(self):
        self.call('toggle',{'enabled':True});before=self.b.path.read_bytes()
        for change in ({'formatVersion':99},{'tasks':[{'id':'one','title':'x','projectId':'foreign','status':'done'}]},{'projects':[]}):
            incoming=self.call('get')['workspace'];incoming.update(change)
            with self.assertRaises(ValueError):self.call('import',{'revision':1,'workspace':incoming})
            self.assertEqual(before,self.b.path.read_bytes())
        for a,args in [('specklet.toggle',{'enabled':1}),('specklet.task',{'revision':0,'task':{'status':'unknown'}}),('specklet.import',{'revision':True,'workspace':{}})]:
            with self.assertRaises(ValueError):validate(a,args)
    def test_concurrent_observed_tasks_survive_restart(self):
        self.call('toggle',{'enabled':True})
        other=AgentControlProvider(self.home/'profiles',self.p.bindings,lambda _: {},lambda *a: {})
        alternate=Board(other,'host--reviewer')
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(lambda i:(self.b if i%2 else alternate).observe(str(i),'Task '+str(i),'doing'),range(30)))
        p=AgentControlProvider(self.home/'profiles',self.p.bindings,lambda _: {},lambda *a: {})
        self.assertEqual(len(Board(p,'host--reviewer').dispatch('specklet.get',{})['workspace']['tasks']),30)
        self.assertFalse(list(self.b.path.parent.glob('*.tmp')))
    def test_native_tool_auth_identity_and_disable(self):
        app=Flask(__name__);register_provider_routes(app,self.p,lambda:'fixture-token');c=app.test_client()
        body={'runtime':'reviewer','action':'get','args':{},'boardId':None};headers={'X-ProgreTech-Mesh-Local-Token':'fixture-token'}
        self.assertEqual(c.post('/api/mesh/specklet',json=body).status_code,401)
        self.call('toggle',{'enabled':True});d=c.post('/api/mesh/specklet',json=body,headers=headers).get_json()['result'];self.assertEqual([b['boardId'] for b in d['boards']],['host--reviewer'])
        body.update(action='task',boardId='host',args={'revision':0,'task':{'title':'Wrong role'}});self.assertEqual(c.post('/api/mesh/specklet',json=body,headers=headers).status_code,400)
        body.update(boardId='host--reviewer',args={'revision':1,'task':{'title':'Actual task','status':'doing'}})
        self.assertEqual(c.post('/api/mesh/specklet',json=body,headers=headers).status_code,200)
        self.call('toggle',{'enabled':False});body['args']['revision']=3
        self.assertEqual(c.post('/api/mesh/specklet',json=body,headers=headers).get_json()['error'],'specklet_disabled')
    def test_office_namespace_isolation(self):
        self.call('toggle',{'enabled':True});rows={'tasks':[{'id':'t','title':'Office task','status':'doing'}]}
        observe_office(self.p,self.home,namespace('main','host'),rows);self.assertEqual(self.call('get')['workspace']['tasks'],[])
        observe_office(self.p,self.home,namespace('reviewer','host--reviewer'),rows);self.assertEqual(self.call('get')['workspace']['tasks'][0]['meshStatus'],'doing')


class CloudSpeckletTests(unittest.TestCase):
    def test_page_and_updates_owner_origin_bound(self):
        import main
        from unittest.mock import patch
        reg=main.DEV_AGENT_REGISTRY.copy();sockets=main.GATEWAY_SOCKETS.copy()
        try:
            main.DEV_AGENT_REGISTRY['fixture']={'id':'fixture','name':'Fixture','owner_id':'owner','trust_state':'verified'};main.GATEWAY_SOCKETS['fixture']=object()
            c=main.app.test_client()
            with c.session_transaction() as s:s['mesh_user']={'id':'owner'}
            page=c.get('/agents/fixture/task-board');self.assertEqual(page.status_code,200);self.assertIn(b'Use Specklet',page.data)
            body={'action':'specklet.toggle','args':{'enabled':True}}
            with patch('mesh_agent_management.control_relay.dispatch',return_value=({'ok':True,'result':{'enabled':True}},200)):
                self.assertEqual(c.post('/api/agents/fixture/management',json=body,headers={'Origin':'http://localhost'}).status_code,200)
                self.assertEqual(c.post('/api/agents/fixture/management',json=body,headers={'Origin':'https://other.invalid'}).status_code,403)
            with c.session_transaction() as s:s['mesh_user']={'id':'different'}
            self.assertEqual(c.get('/agents/fixture/task-board').status_code,404)
        finally:
            main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY.update(reg);main.GATEWAY_SOCKETS.clear();main.GATEWAY_SOCKETS.update(sockets)
