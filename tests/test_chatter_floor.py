import copy
import json
import math
import time
import unittest
from unittest.mock import patch
import test_factory_handoffs as fixtures
from control_center.chatter_ideas import validate_encounter
from control_center.handoffs import Handoffs
from control_center.office import engine, namespace, validate_office


class FloorChatterTests(unittest.TestCase):
    setUp = fixtures.HandoffTests.setUp

    def enable(self, **settings):
        self.h.dispatch('host','chatter.configure',{'enabled':True,'tab_id':'a'*32,'floor_encounters':True,**settings})

    def encounter(self, people=None, idea='', **changes):
        people=people or ['host--researcher','host--progre']
        args={'tab_id':'a'*32,'participants':people,'positions':[{'x':500,'y':350} for _ in people],'idea_id':idea,**changes}
        return self.h.dispatch('host','chatter.encounter',args)

    def finish(self, row, replies):
        actual=next(c for c in self.h.data['chatter']['conversations'] if c['id']==row['id'])
        actual['approach_until']=0
        self.h.chatter_tick()
        for reply in replies:
            key=(actual['turn_agent'],actual['job_id'])
            self.mesh.jobs[key].update(done=True,result={'reply':reply})
            self.h.chatter_tick()
        return actual

    def idea(self):
        self.enable()
        row=self.encounter()
        self.finish(row,['Evidence and possible improvement',json.dumps({'idea':{'title':'Improve offline recovery','context':'Validate recovery without losing local work.'}})])
        return self.h.data['chatter']['ideas'][0]

    def test_no_random_conversations_in_floor_mode_and_disabled_encounters_rejected(self):
        with self.assertRaisesRegex(ValueError,'chatter_tab_expired'):self.encounter()
        self.enable();self.h.chatter_tick()
        self.assertEqual(self.h.data['chatter']['conversations'],[])
        row=self.encounter();self.assertEqual(row['state'],'approaching');self.assertFalse(self.mesh.calls)
        self.h.dispatch('host','chatter.configure',{'enabled':False,'tab_id':'a'*32})
        self.h.chatter_tick();self.assertFalse(self.mesh.calls)
        self.assertEqual(self.h.data['chatter']['conversations'][0]['state'],'stopped')

    def test_tab_host_distance_capacity_and_duplicate_runtime_guards(self):
        self.enable()
        self.provider.bindings['other--progre']='progre'
        for changes in [dict(tab_id='b'*32),dict(participants=['host--researcher','other--progre']),dict(positions=[{'x':100,'y':100},{'x':900,'y':600}])]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.encounter(**changes)
        self.provider.bindings['host--alias']='researcher'
        with self.assertRaises(ValueError):self.encounter(['host--researcher','host--alias'])
        self.encounter()
        with self.assertRaisesRegex(ValueError,'chatter_capacity'):self.encounter()
        for x in [True,float('nan'),float('inf'),-1,1001]:
            with self.subTest(x=x),self.assertRaises(ValueError):validate_encounter({'tab_id':'a'*32,'participants':['host--progre'],'positions':[{'x':x,'y':350}],'idea_id':'a'*32})

    def test_group_switch_and_three_unique_turns(self):
        self.enable()
        people=['host--researcher','host--progre','host--imagen']
        with self.assertRaises(ValueError):self.encounter(people)
        self.enable(experimental_group_chat=True)
        row=self.encounter(people)
        self.assertEqual(self.h.participants(row),people)
        # Avoid the unrelated legacy group artifact publication in this unit scope.
        actual=self.h.data['chatter']['conversations'][0];actual.pop('experimental')
        self.finish(row,['One','Two','Three'])
        self.assertEqual([a for a,_ in self.mesh.calls],people)

    def test_idea_requires_explicit_proposal_and_actual_completed_review(self):
        idea=self.idea();self.assertEqual(len(idea['reviews']),0)
        review=self.encounter(['host--imagen'],idea['id'])
        self.assertEqual(len(idea['reviews']),0)
        self.finish(review,['Add a recovery test and preserve unsynced edits.'])
        self.assertEqual(len(idea['reviews']),1)
        with self.assertRaisesRegex(ValueError,'chatter_already_reviewed'):self.encounter(['host--imagen'],idea['id'])
        restored=Handoffs(self.provider,self.home,self.mesh)
        self.assertEqual(len(restored.data['chatter']['ideas'][0]['reviews']),1)
        self.assertFalse(restored.data['chatter']['enabled'])

    def test_five_distinct_receipts_promote_once_and_gate_execution(self):
        idea=self.idea()
        self.provider.bindings.update({'host--coder':'coder','host--codex':'codex'})
        for who in ['imagen','coder','codex','researcher','progre']:
            self.finish(self.encounter(['host--'+who],idea['id']),['Reviewed '+who+': add a scoped acceptance check.'])
        self.assertEqual(len(idea['reviews']),5)
        # Fixture admission engine was mocked; test promotion with the real isolated ledger.
        with patch('control_center.office.engine',wraps=engine):
            self.h.promote_ideas()
            first=engine(self.home,namespace('main','host'),'snapshot')['snapshot']
            self.assertEqual(len(first['tasks']),1)
            task=first['tasks'][0]
            self.assertEqual(task['id'],idea['task_id']);self.assertEqual(task['stage'],'blocked')
            self.assertFalse(task.get('queued'));self.assertEqual(len(task['comments']),5)
            with self.assertRaises(ValueError):engine(self.home,namespace('main','host'),'begin',{'id':task['id'],'native':True})
            idea.pop('task_id')  # Simulate crash before the second ledger save.
            self.h.promote_ideas()
            self.assertEqual(len(engine(self.home,namespace('main','host'),'snapshot')['snapshot']['tasks']),1)
        with self.assertRaises(ValueError):validate_office({'operation':'chatter.promote','args':{}})

    def test_small_team_can_revisit_after_another_reviewer_but_not_duplicate_a_receipt(self):
        idea=self.idea()
        for index,who in enumerate(['imagen','researcher','imagen','researcher','imagen']):
            # Cooldown protects encounter floods, not later review rounds.
            for c in self.h.data['chatter']['conversations']:c['created']=0
            row=self.finish(self.encounter(['host--'+who],idea['id']),['Review round '+str(index)])
            self.h.finish_idea(row)
            self.assertEqual(len(idea['reviews']),index+1)

    def test_failed_or_empty_review_does_not_count(self):
        idea=self.idea();row=self.encounter(['host--imagen'],idea['id'])
        actual=self.h.data['chatter']['conversations'][-1];actual['approach_until']=0;self.h.chatter_tick()
        self.mesh.jobs[(actual['turn_agent'],actual['job_id'])].update(done=True,error='mesh_provider_rejected')
        self.h.chatter_tick();self.assertFalse(idea['reviews'])
        self.assertFalse(idea.get('task_id'))
