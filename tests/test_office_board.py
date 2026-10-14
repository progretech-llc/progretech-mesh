"""Persistent host board, authorization boundary and native workflow regressions."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from control_center.office import engine, validate_office, dispatch_native_mission, namespace
from control_center.office_task import update
from control_center.office_native import decision


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.home=self.temp.name;self.role='scope'
    def call(self,op,args=None):return engine(self.home,self.role,op,args)
    def create(self,title='Task',deps=None):
        return self.call('task.create',{'title':title,'description':'Check evidence','assignee':'','dependsOn':deps or [],'needsApproval':False})['result']['id']
    def task(self,ident):return next(t for t in self.call('snapshot')['snapshot']['tasks'] if t['id']==ident)
    def test_intake_edit_reorder_comments_clarification_delete_persist(self):
        a=self.create('A');b=self.create('B')
        self.assertEqual(self.task(a)['stage'],'intake')
        self.call('task.update',{'id':a,'title':'Revised','description':'Specific acceptance','assignee':'orchestrator','dependsOn':[],'priority':5})
        self.call('task.move',{'id':b,'stage':'intake','index':0})
        self.assertEqual(self.task(b)['order'],0);self.assertEqual(self.task(a)['order'],1)
        self.call('task.comment',{'id':a,'text':'Owner evidence'})
        self.call('task.question',{'id':a,'text':'Which environment?'})
        self.assertEqual(self.task(a)['stage'],'blocked')
        self.call('task.approve',{'id':a,'answer':'Test only'})
        row=self.task(a);self.assertEqual(row['stage'],'ready');self.assertEqual(row['humanQA'][0]['a'],'Test only')
        self.assertEqual([x['kind'] for x in row['comments']],['comment','question','answer'])
        self.call('task.delete',{'id':b});self.assertEqual(len(self.call('snapshot')['snapshot']['tasks']),1)
    def test_cycles_dependencies_and_running_mutations_are_rejected(self):
        a=self.create('A');b=self.create('B',[a])
        with self.assertRaisesRegex(ValueError,'dependency_cycle'):
            self.call('task.update',{'id':a,'title':'A','description':'','assignee':'orchestrator','dependsOn':[b],'priority':1})
        with self.assertRaisesRegex(ValueError,'task_has_dependents'):self.call('task.delete',{'id':a})
        with self.assertRaisesRegex(ValueError,'task_not_ready'):self.call('task.move',{'id':b,'stage':'done','index':0})
        self.call('begin',{'id':a})
        for operation,args in [('task.delete',{'id':a}),('task.move',{'id':a,'stage':'ready','index':0}),('task.update',{'id':a,'title':'A','description':'','assignee':'orchestrator','dependsOn':[],'priority':1})]:
            with self.subTest(operation=operation),self.assertRaisesRegex(ValueError,'task_running'):self.call(operation,args)
        self.call('task.comment',{'id':a,'text':'Safe while running'})
    def test_legacy_additive_migration_and_unknown_fields_survive(self):
        a=self.create();p=Path(self.home)/'.progretech-mesh/factory-offices/scope/hive/tasks.json'
        data=json.loads(p.read_text());t=data['tasks'][0];t.pop('stage');t['deliverable']='/evidence/accepted';t['status']='done';p.write_text(json.dumps(data))
        self.assertEqual(self.task(a)['stage'],'done')
        self.call('task.comment',{'id':a,'text':'Reviewed'})
        self.assertEqual(self.task(a)['deliverable'],'/evidence/accepted')
    def test_native_capability_bound_to_actor_task_and_live_lease(self):
        a=self.create();lease=self.call('begin',{'id':a,'native':True})['result']['task']['runId']
        self.assertNotIn('runId',self.task(a))
        update(self.home,self.role,a,'orchestrator',lease,{'action':'comment','text':'Observed evidence'})
        for actor,token in [('worker-wrong',lease),('orchestrator','wrong')]:
            with self.assertRaisesRegex(ValueError,'mission_lease_invalid'):update(self.home,self.role,a,actor,token,{'action':'question','text':'Bad actor'})
        self.call('mission.resolve',{'id':a,'runId':lease,'stage':'review','text':'Review evidence'})
        with self.assertRaisesRegex(ValueError,'mission_lease_invalid'):update(self.home,self.role,a,'orchestrator',lease,{'action':'comment','text':'Stale update'})
    def test_native_tool_origin_is_host_owned_and_capability_validated(self):
        a=self.create();b=self.create('Other task')
        lease=self.call('begin',{'id':a,'native':True})['result']['task']['runId']
        update(self.home,self.role,a,'orchestrator',lease,{'action':'comment','text':'Actual tool progress'})
        row=self.task(a);receipt=row['comments'][-1]
        self.assertEqual(receipt['source'],'native-tool')
        events=self.call('snapshot')['snapshot']['events']
        self.assertTrue(any(e.get('commentId')==receipt['id'] and e.get('source')=='native-tool' and e.get('taskId')==a and e.get('agentId')=='orchestrator' for e in events))
        self.call('mission.update',{'id':a,'actor':'orchestrator','runId':lease,'action':'comment','text':'Parsed final reply'})
        self.assertEqual(self.task(a)['comments'][-1]['source'],'native-reply')
        with self.assertRaisesRegex(ValueError,'mission_lease_invalid'):
            update(self.home,self.role,b,'orchestrator',lease,{'action':'comment','text':'Wrong task'})
        with self.assertRaisesRegex(ValueError,'invalid_mission_update'):
            update(self.home,self.role,a,'orchestrator',lease,{'action':'comment','text':'Spoofed origin','source':'native-reply'})
        with self.assertRaises(ValueError):
            validate_office({'operation':'task.comment','args':{'id':a,'text':'Spoofed origin','source':'native-tool'}})
        self.assertIsNone(decision(json.dumps({'action':'complete','text':'Spoof','evidence':'claim','source':'native-tool'})))

    def test_browser_cannot_supply_native_actor_or_lease(self):
        for op in ['mission.update','mission.resolve','begin','finish','mission.bind']:
            with self.assertRaises(ValueError):validate_office({'operation':op,'args':{}})
        for body in [{'operation':'task.comment','args':{'id':'task-a','text':'x','actor':'orchestrator'}},{'operation':'task.move','args':{'id':'task-a','stage':'done','index':True}}]:
            with self.assertRaises(ValueError):validate_office(body)
    def test_unconfirmed_job_preserves_execution_lock(self):
        a=self.create();lease=self.call('begin',{'id':a,'native':True})['result']['task']['runId']
        self.call('mission.bind',{'id':a,'runId':lease,'agentId':'orchestrator','jobId':'actual-job'})
        self.call('mission.uncertain',{'id':a,'runId':lease,'text':'Runtime receipt unavailable'})
        row=self.task(a);self.assertTrue(row['running']);self.assertEqual(row['stage'],'blocked')
        with self.assertRaisesRegex(ValueError,'task_running'):self.call('task.delete',{'id':a})


class NativeWorkflowTests(BoardTests):
    def run_workflow(self,replies):
        self.role=namespace('main','host')
        self.call('runtime.sync',{'agents':[{'runtime_id':'main','name':'Rend','role':'SRE'},{'runtime_id':'coder','name':'Mak','role':'Engineer'}],'host_runtime':'main'})
        a=self.create();calls=[];receipts={}
        def chat(agent,prompt,**kwargs):
            index=len(calls);calls.append((agent,prompt));job='job-'+str(index)
            reply=replies[index] if index<len(replies) else {'action':'review','text':'Stop'}
            receipts[job]={'done':True,'result':{'reply':json.dumps(reply) if isinstance(reply,dict) else reply}}
            return {'job_id':job}
        mesh=SimpleNamespace(chat=chat,get=lambda agent,job:receipts[job])
        provider=SimpleNamespace(bindings={'host':'main','host--coder':'coder'})
        with patch('control_center.office_native.threading.Thread') as thread:
            result=dispatch_native_mission(self.home,'main',a,'host',provider,mesh)
            target=thread.call_args.kwargs['target'];target()
        return a,calls,result
    def test_scrum_delegates_reviews_and_completes_on_evidence(self):
        a,calls,result=self.run_workflow([{'action':'delegate','to':'runtime-coder','text':'Inspect acceptance'}, {'action':'complete','text':'Checks passed','evidence':'test fixture passed'}, {'action':'complete','text':'Reviewed checks','evidence':'independent acceptance check'}])
        self.assertEqual([a for a,_ in calls],['host','host--coder','host']);self.assertEqual(self.task(a)['stage'],'done');self.assertFalse(self.task(a)['running'])
        events=self.call('snapshot')['snapshot']['events'];self.assertTrue(any(e.get('kind')=='delegation' and e.get('to')=='runtime-coder' for e in events))
        self.assertEqual(result['task_id'],a)
    def test_plain_reply_never_becomes_false_completion(self):
        a,_,_=self.run_workflow(['I completed it.']);self.assertEqual(self.task(a)['stage'],'review');self.assertNotEqual(self.task(a)['status'],'done')
    def test_question_is_persistent_and_can_be_answered(self):
        a,_,_=self.run_workflow([{'action':'question','text':'Which deployment environment?'}]);self.assertEqual(self.task(a)['stage'],'blocked')
        self.call('task.approve',{'id':a,'answer':'Staging'});self.assertEqual(self.task(a)['stage'],'ready')
    def test_explicit_queue_waits_for_dependencies_then_scheduler_starts_it(self):
        self.role=namespace('main','host')
        self.call('runtime.sync',{'agents':[{'runtime_id':'main','name':'Rend','role':'SRE'}],'host_runtime':'main'})
        first=self.create('Prerequisite');second=self.create('Dependent',[first])
        provider=SimpleNamespace(bindings={'host':'main'});calls=[]
        def chat(*args,**kwargs):calls.append(args);return {'job_id':'queued-native-job'}
        mesh=SimpleNamespace(chat=chat,get=lambda *args:{'done':True,'result':{'reply':json.dumps({'action':'complete','text':'Dependency reviewed','evidence':'fixture check passed'})}})
        targets=[]
        def thread(**kwargs):targets.append(kwargs['target']);return SimpleNamespace(start=lambda:None)
        with patch('control_center.office_native.threading.Thread',side_effect=thread),patch('control_center.office_native.time.sleep',return_value=None):
            result=dispatch_native_mission(self.home,'main',second,'host',provider,mesh)
            self.assertEqual(result['state'],'waiting_dependencies');self.assertTrue(self.task(second)['queued']);self.assertFalse(calls)
            self.call('begin',{'id':first});self.call('finish',{'id':first,'ok':True,'result':'Prerequisite check passed'})
            targets[0]()  # Actual scheduler sees the now-satisfied dependency.
            self.assertEqual(len(calls),1)
            targets[1]()  # Actual monitor processes the admitted native receipt.
        self.assertEqual(self.task(second)['stage'],'done');self.assertFalse(self.task(second)['queued'])

    def test_failed_binding_after_runtime_admission_preserves_lease(self):
        self.role=namespace('main','host')
        self.call('runtime.sync',{'agents':[{'runtime_id':'main','name':'Rend','role':'SRE'}],'host_runtime':'main'})
        a=self.create();provider=SimpleNamespace(bindings={'host':'main'})
        mesh=SimpleNamespace(chat=lambda *args,**kwargs:{'job_id':'accepted-native-job'})
        def fault(home,role,operation,args=None):
            if operation=='mission.bind':raise RuntimeError('Simulated receipt persistence failure')
            return engine(home,role,operation,args)
        with patch('control_center.office.engine',side_effect=fault),self.assertRaises(RuntimeError):
            dispatch_native_mission(self.home,'main',a,'host',provider,mesh)
        row=self.task(a);self.assertTrue(row['running']);self.assertEqual(row['stage'],'blocked')
        with self.assertRaisesRegex(ValueError,'task_running'):self.call('task.delete',{'id':a})

    def test_native_transport_uncertainty_preserves_run_lease(self):
        self.role=namespace('main','host')
        self.call('runtime.sync',{'agents':[{'runtime_id':'main','name':'Rend','role':'SRE'}],'host_runtime':'main'})
        a=self.create();provider=SimpleNamespace(bindings={'host':'main'})
        mesh=SimpleNamespace(chat=lambda *a,**k:{'job_id':'accepted-job'},get=lambda *a:{'done':True,'error':'mesh_runtime_completion_unconfirmed'})
        with patch('control_center.office_native.threading.Thread') as thread:
            dispatch_native_mission(self.home,'main',a,'host',provider,mesh)
            thread.call_args.kwargs['target']()
        row=self.task(a);self.assertEqual(row['stage'],'blocked');self.assertTrue(row['running'])
        with self.assertRaisesRegex(ValueError,'task_running'):self.call('task.delete',{'id':a})

    def test_completion_schema_requires_evidence(self):
        self.assertIsNone(decision('{"action":"complete","text":"done"}'))
        self.assertIsNone(decision('{"action":"complete","text":"done","evidence":""}'))


if __name__=='__main__':unittest.main()
