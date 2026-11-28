import json
import tempfile
import unittest
from pathlib import Path
from control_center.office import engine
from control_center.office_identity import synchronize, project


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=self.tmp.name
    def call(self, op, args=None):return engine(self.home,'scope',op,args)
    def test_handoff_preserves_identity_memory_and_delivered_history(self):
        worker=self.call('hire',{'name':'Ada','role':'Engineer','goal':'Build'})['result']['id']
        self.call('memory.save',{'id':'orchestrator','text':'Specialist memory'})
        def task():return self.call('task.create',{'title':'Mission','description':'Evidence','assignee':'','dependsOn':[],'needsApproval':False})['result']['id']
        done=task();self.call('begin',{'id':done});self.call('finish',{'id':done,'ok':True,'result':'Delivered'})
        pending=task();self.call('message',{'to':'orchestrator','text':'Pending coordination'})
        snapshot=self.call('orchestrator.set',{'id':worker})['snapshot']
        self.assertEqual([a['id'] for a in snapshot['agents'] if a['isDirector']],[worker])
        self.assertEqual(next(t for t in snapshot['tasks'] if t['id']==pending)['assignee'],worker)
        self.assertEqual(next(t for t in snapshot['tasks'] if t['id']==done)['assignee'],'orchestrator')
        self.assertEqual(self.call('memory',{'id':'orchestrator'})['result']['text'],'Specialist memory')
        self.assertIn('Pending coordination',str(self.call('mailbox.list',{'agent':worker})['result']))
        self.assertEqual(next(a for a in snapshot['agents'] if a['id']==worker)['role'],'Engineer')
        self.assertEqual(self.call('snapshot')['snapshot']['orchestratorId'],worker)
    def test_explicit_binding_is_idempotent_and_archive_survives_discovery(self):
        self.call('runtime.sync',{'agents':[{'runtime_id':'codex','name':'Odexi','role':'Architect'}], 'bindings':{'orchestrator':'codex'}})
        a=self.call('runtime.sync',{'agents':[{'runtime_id':'coder','name':'Mak','role':'Engineer'}]})['snapshot']
        worker=next(a['id'] for a in a['agents'] if a.get('runtime_id')=='coder')
        self.call('archive',{'id':worker})
        b=self.call('runtime.sync',{'agents':[{'runtime_id':'coder','name':'Mak','role':'Engineer'}]})['snapshot']
        self.assertNotIn(worker,[a['id'] for a in b['agents']])
        self.assertIn(worker,[a['id'] for a in b['archivedAgents']])
        self.call('restore',{'id':worker})
        self.assertEqual(len(self.call('snapshot')['snapshot']['agents']),2)
    def test_projection_merges_gateway_intake_and_keeps_workers(self):
        snap={'agents':[{'id':'o','runtime_id':'main','isDirector':False},{'id':'c','runtime_id':'codex','isDirector':True},{'id':'worker-one','name':'New worker','role':'Research','isDirector':False,'state':'idle'}]}
        rows=project(snap,[{'id':'rend--main','runtime_id':'main'},{'id':'rend--codex','runtime_id':'codex'}],'rend','main')
        self.assertEqual([r['id'] for r in rows],['rend','rend--codex','rend--worker-one'])
        self.assertEqual([r['id'] for r in rows if r['is_orchestrator']],['rend--codex'])

    def test_fresh_office_adopts_host_without_synthetic_director(self):
        rows=[{'runtime_id':'main','name':'Rend','role':'SRE'}, {'runtime_id':'codex','name':'Odexi','role':'Architect'}]
        snap=synchronize(self.home,'main','new-host',rows)
        self.assertEqual(len(snap['agents']),2)
        self.assertEqual([(a['name'],a['runtime_id']) for a in snap['agents'] if a['isDirector']],[('Rend','main')])
        again=synchronize(self.home,'main','new-host',rows)
        self.assertEqual([a['id'] for a in snap['agents']],[a['id'] for a in again['agents']])

    def test_bound_role_refresh_preserves_identity_tasks_and_custom_goal(self):
        first = {'runtime_id':'codex','name':'Odexi','role':'Old role'}
        self.call('runtime.sync',{'agents':[first], 'bindings':{'orchestrator':'codex'}})
        task = self.call('task.create',{'title':'Ongoing work','description':'Keep assignment',
                         'assignee':'orchestrator','dependsOn':[],'needsApproval':False})['result']['id']
        before = self.call('snapshot')['snapshot']
        updated = dict(first, name='Renamed coordinator', role='Project manager, teacher and second-in-command')
        after = self.call('runtime.sync',{'agents':[updated]})['snapshot']
        self.assertEqual(after['orchestratorId'], before['orchestratorId'])
        self.assertEqual(after['tasks'], before['tasks'])
        self.assertEqual(after['agents'][0]['id'], before['agents'][0]['id'])
        self.assertEqual(after['agents'][0]['role'], updated['role'])
        self.assertEqual(after['agents'][0]['name'], updated['name'])
        identity = Path(self.home)/'.progretech-mesh/factory-offices/scope/hive/agents/orchestrator/identity.md'
        self.assertIn(updated['role'], identity.read_text())
        self.assertEqual(self.call('snapshot')['snapshot']['agents'][0]['role'], updated['role'])
        self.assertTrue(any(t['id']==task for t in after['tasks']))

    def test_archived_runtime_role_refresh_does_not_restore_it(self):
        row = {'runtime_id':'imagen','name':'Imagen','role':'Graphic designer'}
        first=self.call('runtime.sync',{'agents':[row]})['snapshot']
        worker=next(a['id'] for a in first['agents'] if a.get('runtime_id')=='imagen')
        self.call('archive',{'id':worker})
        self.call('runtime.sync',{'agents':[dict(row,role='Graphic designer and media generation expert')]})
        result=self.call('snapshot')['snapshot']
        self.assertNotIn(worker,[a['id'] for a in result['agents']])
        self.assertIn(worker,[a['id'] for a in result['archivedAgents']])
