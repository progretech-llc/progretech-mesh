import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from control_center.handoffs import Handoffs

class FakeMesh:
    def __init__(self):self.calls=[];self.jobs={};self.asleep=False;self.native_idle=True;self.inference=threading.Lock();self.lock=threading.RLock()
    def status(self,a):return {'sleeping':self.asleep}
    def sleeping(self,a):return self.asleep
    def idle(self):return self.native_idle
    def chat(self,a,text,**kwargs):
        j={'job_id':str(len(self.calls)),'done':False,'agent_id':a};self.calls.append((a,text));self.jobs[(a,j['job_id'])]=j;return j
    def get(self,a,i):return self.jobs[(a,i)]

class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.home=Path(self.tmp.name)
        self.mesh=FakeMesh();self.provider=SimpleNamespace(bindings={'host':'main','host--imagen':'imagen','host--researcher':'researcher','host--progre':'progre'})
        self.addCleanup(patch.stopall)
        patch('control_center.chatter_admission.resources',return_value=(True,'Capacity confirmed')).start()
        patch('control_center.office.engine',return_value={'snapshot':{'paused':False}}).start()
        self.h=Handoffs(self.provider,self.home,self.mesh);self.notices=[];self.h.notify=lambda t:self.notices.append(t) or True
    def publish(self):
        p=self.home/'Rend/artifacts/imagen/icon.svg';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('<svg/>');return p
    def create(self):return self.h.dispatch('host--researcher','handoff.create',{'source':'imagen','text':'Review the generated icon.'})
    def test_dependency_waits_for_new_artifact_then_runs_once_and_notifies_director(self):
        self.publish();self.h.tick();r=self.create();self.h.tick();self.assertEqual(self.mesh.calls,[])
        time.sleep(.01);p=self.publish();self.h.tick();self.assertEqual(len(self.mesh.calls),1);self.assertEqual(self.mesh.calls[0][0],'host--researcher');self.assertIn(str(p),self.mesh.calls[0][1])
        self.h.tick();self.assertEqual(len(self.mesh.calls),1)
        self.mesh.jobs[('host--researcher','0')].update(done=True,result={'reply':'Reviewed icon; contrast needs work.'})
        self.h.tick();row=self.h.data['rules'][0];self.assertEqual(row['state'],'delivered');self.assertTrue(row['director_notified']);self.assertTrue(any('contrast' in t for t in self.notices))
    def test_owner_pause_cancel_and_target_bound_controls(self):
        r=self.create();self.h.dispatch('host--researcher','handoff.control',{'id':r['id'],'state':'paused'});self.publish();self.h.tick();self.assertEqual(self.mesh.calls,[])
        with self.assertRaises(ValueError):self.h.dispatch('host--imagen','handoff.control',{'id':r['id'],'state':'waiting'})
        self.h.dispatch('host--researcher','handoff.control',{'id':r['id'],'state':'cancelled'});self.h.tick();self.assertEqual(self.mesh.calls,[])
    def test_sleep_and_restart_do_not_replay_started_work(self):
        self.create();self.publish();self.mesh.asleep=True;self.h.tick();self.assertFalse(self.mesh.calls)
        self.mesh.asleep=False;self.h.tick();self.assertEqual(len(self.mesh.calls),1)
        h=Handoffs(self.provider,self.home,self.mesh);self.assertEqual(h.data['rules'][0]['state'],'unconfirmed');h.notify=lambda _:True;h.tick();self.assertEqual(len(self.mesh.calls),1)
    def test_chatter_opt_in_idle_pair_and_two_actual_replies(self):
        self.h.chatter_tick();self.assertFalse(self.mesh.calls)
        self.h.dispatch('host','chatter.configure',{'enabled':True});self.mesh.native_idle=False;self.h.chatter_tick();self.assertFalse(self.mesh.calls)
        self.mesh.native_idle=True
        with patch('control_center.office.engine',return_value={'snapshot':{'paused':False}}):self.h.chatter_tick()
        chat=self.h.data['chatter']['conversations'][0];self.assertEqual(chat['state'],'approaching');self.assertFalse(self.mesh.calls);chat['approach_until']=0;self.h.chatter_tick();self.assertEqual(len(self.mesh.calls),1)
        self.mesh.jobs[(chat['a'],'0')].update(done=True,result={'reply':'Use evidence-linked review.'})
        self.h.chatter_tick();self.assertEqual(len(self.mesh.calls),2)
        self.mesh.jobs[(chat['b'],'1')].update(done=True,result={'reply':'Agreed; verify recall before claiming learning.'})
        self.h.chatter_tick();self.assertEqual(chat['state'],'complete');self.assertEqual(len(chat['messages']),2)
        self.h.chatter_tick();self.assertEqual(len(self.mesh.calls),2)
    def test_disabling_chatter_stops_before_second_turn(self):
        self.h.dispatch('host','chatter.configure',{'enabled':True})
        with patch('control_center.office.engine',return_value={'snapshot':{'paused':False}}):self.h.chatter_tick()
        chat=self.h.data['chatter']['conversations'][0];chat['approach_until']=0;self.h.chatter_tick();self.h.dispatch('host','chatter.configure',{'enabled':False});self.mesh.jobs[(chat['a'],'0')].update(done=True,result={'reply':'Suggestion'})
        self.h.chatter_tick();self.assertEqual(chat['state'],'stopped');self.assertEqual(len(self.mesh.calls),1)
    def test_serial_conversations_repeat_inside_and_after_windows(self):
        self.h.dispatch('host','chatter.configure',{'enabled':True})
        self.h.chatter_tick();c=self.h.data['chatter']['conversations'][0];c['approach_until']=0
        self.h.chatter_tick();self.h.chatter_tick();self.assertEqual(len(self.mesh.calls),1)
        self.mesh.jobs[(c['a'],'0')].update(done=True,result={'reply':'First'})
        self.h.chatter_tick();self.assertEqual(len(self.mesh.calls),2)
        self.mesh.jobs[(c['b'],'1')].update(done=True,result={'reply':'Second'})
        self.h.chatter_tick();ch=self.h.data['chatter'];ch['next_at']=0
        self.h.chatter_tick();self.assertEqual(len(ch['conversations']),2)
        old=ch['window_ends'];ch['window_ends']=0;self.h.chatter_tick();self.assertGreater(ch['window_ends'],old-1)
    def test_configurable_session_duration_persists_repeats_and_requires_enabled(self):
        self.assertEqual(self.h.data['chatter']['session_minutes'],15)
        with patch('control_center.handoffs.time.time',return_value=100):
            self.h.dispatch('host','chatter.configure',{'enabled':True,'session_minutes':7})
        ch=self.h.data['chatter'];self.assertEqual(ch['window_ends'],520)
        self.mesh.native_idle=False
        with patch('control_center.handoffs.time.time',return_value=521):self.h.chatter_tick()
        self.assertEqual(ch['window_ends'],941);self.assertFalse(self.mesh.calls)
        restored=Handoffs(self.provider,self.home,self.mesh)
        self.assertEqual(restored.data['chatter']['session_minutes'],7)
        self.h.dispatch('host','chatter.configure',{'enabled':False})
        for value in [0,121,True,1.5,'7']:
            with self.assertRaises(ValueError):self.h.dispatch('host','chatter.configure',{'enabled':True,'session_minutes':value})
        with self.assertRaises(ValueError):self.h.dispatch('host','chatter.configure',{'enabled':False,'session_minutes':20})
        self.h.dispatch('host','chatter.configure',{'enabled':True})
        self.assertEqual(ch['session_minutes'],7)

    def test_pair_topic_and_resource_wait_preserve_request(self):
        self.h.dispatch('host','chatter.configure',{'enabled':True})
        c=self.h.dispatch('host','chatter.pair',{'a':'host--imagen','b':'host--researcher','topic':''})
        self.h.dispatch('host','chatter.topic',{'id':c['id'],'topic':'Icon accessibility'})
        self.h.chatter_tick();c=self.h.data['chatter']['conversations'][0];c['approach_until']=0
        with patch('control_center.chatter_admission.resources',return_value=(False,'Waiting for RAM headroom')):self.h.chatter_tick()
        self.assertFalse(self.mesh.calls);self.assertEqual(c['state'],'approaching');self.assertIn('RAM',c['note'])
        self.h.chatter_tick();self.assertIn('Icon accessibility',self.mesh.calls[0][1])
        with self.assertRaisesRegex(ValueError,'invalid_chatter_pair'):self.h.dispatch('host','chatter.pair',{'a':'other--imagen','b':'host--researcher','topic':''})
    def test_owner_requests_preempt_chatter(self):
        self.h.dispatch('host','chatter.configure',{'enabled':True})
        self.mesh.jobs['owner']={'agent_id':'host','done':False}
        self.h.chatter_tick();self.assertFalse(self.h.data['chatter']['conversations']);self.assertIn('priority',self.h.data['chatter']['admission'])

    def test_mission_priority_persists_and_rejects_running_mutation(self):
        patch.stopall()
        from control_center.office import engine,validate_office
        body={'operation':'task.priority','args':{'id':'task-'+'a'*12,'priority':99}};validate_office(body)
        created=engine(self.home,'main','task.create',{'title':'Review','description':'Owner task','assignee':'orchestrator','dependsOn':[],'needsApproval':False})
        tid=created['result']['id'];result=engine(self.home,'main','task.priority',{'id':tid,'priority':20});self.assertEqual(result['snapshot']['tasks'][0]['priority'],20)
        engine(self.home,'main','begin',{'id':tid})
        with self.assertRaisesRegex(ValueError,'task_not_ready'):engine(self.home,'main','task.priority',{'id':tid,'priority':21})

    def test_concurrency_defaults_and_typed_bounded_settings(self):
        self.assertEqual(self.h.data['chatter']['max_conversations'],1)
        self.assertFalse(self.h.data['chatter']['experimental_group_chat'])
        for value in [0,5,True,'2',1.5]:
            with self.assertRaisesRegex(ValueError,'invalid_chatter_concurrency'):
                self.h.dispatch('host','chatter.configure',{'enabled':True,'max_conversations':value})
        with self.assertRaisesRegex(ValueError,'invalid_group_chat'):
            self.h.dispatch('host','chatter.configure',{'enabled':True,'experimental_group_chat':1})
        self.h.dispatch('host','chatter.configure',{'enabled':True,'max_conversations':3,'experimental_group_chat':True})
        restored=Handoffs(self.provider,self.home,self.mesh)
        self.assertEqual(restored.data['chatter']['max_conversations'],3)
        self.assertTrue(restored.data['chatter']['experimental_group_chat'])

    def test_concurrent_pairs_never_share_participants(self):
        self.provider.bindings.update({'host--codex':'codex','host--progre':'progre','host--coder':'coder'})
        self.h.dispatch('host','chatter.configure',{'enabled':True,'max_conversations':3})
        self.h.chatter_tick()
        rows=self.h.data['chatter']['conversations']
        self.assertEqual(len(rows),2)
        people=[a for c in rows for a in self.h.participants(c)]
        self.assertEqual(len(people),len(set(people)))
        self.h.chatter_tick();self.assertEqual(len(rows),2)
        self.h.dispatch('host','chatter.configure',{'enabled':False})
        self.assertTrue(all(c['state']=='stopped' for c in rows))

    def test_current_codex_and_moxy_roles_are_chatter_participants(self):
        self.provider.bindings.update({'host--codex':'codex','host--moxy':'moxy'})
        row=self.h.conversation('host--codex','host--moxy')
        self.assertEqual((row['a_role'],row['b_role']),('codex','moxy'))

    def test_group_three_ordered_turns_and_proposal_notification(self):
        self.provider.bindings['host--codex']='codex'
        self.h.dispatch('host','chatter.configure',{'enabled':True,'experimental_group_chat':True})
        self.h.chatter_tick();row=self.h.data['chatter']['conversations'][0]
        row['approach_until']=0
        people=self.h.participants(row);self.assertEqual(len(people),3)
        self.h.chatter_tick()
        for i,person in enumerate(people):
            self.assertEqual(self.mesh.calls[i][0],person)
            self.mesh.jobs[(person,str(i))].update(done=True,result={'reply':'Proposal turn '+str(i)})
            self.h.chatter_tick()
        self.assertEqual(row['state'],'complete');self.assertEqual(len(row['messages']),3)
        self.assertTrue(row['director_notified'])
        proposal=Path(row['proposal_path']);self.assertTrue(proposal.is_file())
        self.assertIn('Proposal turn 2',proposal.read_text())
        self.assertIn('have not been executed',proposal.read_text())
        self.assertIn('Proposal turn 0',self.mesh.calls[2][1]);self.assertIn('Proposal turn 1',self.mesh.calls[2][1])
        self.assertTrue(any('Lyra and Director' in n for n in self.notices))

    def test_group_queue_requires_opt_in_distinct_bound_participants(self):
        self.provider.bindings['host--codex']='codex'
        args={'a':'host--imagen','b':'host--researcher','c':'host--codex','topic':'PWA preview proposal'}
        self.h.dispatch('host','chatter.configure',{'enabled':True})
        with self.assertRaisesRegex(ValueError,'group_chat_disabled'):self.h.dispatch('host','chatter.group',args)
        self.h.dispatch('host','chatter.configure',{'enabled':True,'experimental_group_chat':True})
        row=self.h.dispatch('host','chatter.group',args)
        self.assertEqual(row['state'],'queued');self.assertEqual(row['c'],args['c'])
        self.assertEqual(self.h.dispatch('host','chatter.group',args)['id'],row['id'])
        with self.assertRaisesRegex(ValueError,'invalid_chatter_pair'):self.h.dispatch('host','chatter.group',{**args,'c':args['a']})
        with self.assertRaisesRegex(ValueError,'invalid_chatter_pair'):self.h.dispatch('host','chatter.group',{**args,'c':'other--codex'})

    def test_restart_does_not_replay_third_turn(self):
        self.provider.bindings['host--codex']='codex'
        row=self.h.conversation('host--imagen','host--researcher',c='host--codex')
        row['state']='third';self.h.data['chatter']['conversations'].append(row);self.h.save()
        restored=Handoffs(self.provider,self.home,self.mesh)
        self.assertEqual(restored.data['chatter']['conversations'][0]['state'],'unconfirmed')
        self.assertFalse(self.mesh.calls)
