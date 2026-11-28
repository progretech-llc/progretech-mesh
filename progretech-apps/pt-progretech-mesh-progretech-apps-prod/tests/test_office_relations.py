import json
import tempfile
import unittest
from pathlib import Path
from control_center.office_relations import interactions


class RelationshipLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.path = self.home / '.progretech-mesh/artifact-handoffs.json'
        self.path.parent.mkdir()

    def links(self, rules=None, conversations=None):
        state = {'rules': rules or [], 'chatter': {'session_minutes': 120, 'conversations': conversations or []}}
        raw = json.dumps(state)
        self.path.write_text(raw)
        result = interactions({}, self.home)
        self.assertEqual(self.path.read_text(), raw, 'Projection must preserve historical receipts')
        return result

    def test_handoff_removes_line_immediately_when_delivered(self):
        rule = {'id': 'handoff', 'state': 'running', 'source': 'designer', 'target_role': 'architect', 'text': 'Review', 'artifact': {'name': 'icon'}}
        self.assertEqual(len(self.links(rules=[rule])), 1)
        for state in ['delivered', 'failed', 'cancelled', 'unconfirmed', 'waiting', 'paused']:
            with self.subTest(state=state):
                rule['state'] = state
                self.assertEqual(self.links(rules=[rule]), [])

    def test_conversation_removes_line_at_completion_independent_of_session_duration(self):
        chat = {'id': 'chat', 'a_role': 'architect', 'b_role': 'designer', 'topic': 'Review', 'messages': [], 'created': 0}
        for state in ['first', 'reply_wait', 'second']:
            chat['state'] = state
            self.assertEqual(len(self.links(conversations=[chat])), 1)
        for state in ['queued', 'approaching', 'complete', 'failed', 'stopped', 'unconfirmed']:
            with self.subTest(state=state):
                chat.update(state=state, finished=9999999999)
                self.assertEqual(self.links(conversations=[chat]), [])

    def test_shared_task_link_follows_actual_participant_state(self):
        snap = {'factoryAgents': [{'id': 'architect', 'state': 'active', 'task_id': 'task'}, {'id': 'designer', 'state': 'active', 'task_id': 'task'}]}
        self.assertEqual(len(interactions(snap, self.home)), 1)
        snap['factoryAgents'][1]['state'] = 'success'
        self.assertEqual(interactions(snap, self.home), [])

    def test_group_projection_connects_all_three_and_clears_at_completion(self):
        chat={'id':'group','a_role':'architect','b_role':'designer','c_role':'reviewer','topic':'PWA','messages':[],'state':'third'}
        links=self.links(conversations=[chat]);self.assertEqual(len(links),3)
        self.assertEqual({p for l in links for p in [l['from'],l['to']]},{'factory-architect','factory-designer','factory-reviewer'})
        chat['state']='complete';self.assertEqual(self.links(conversations=[chat]),[])

    def test_completed_mission_does_not_keep_mailbox_line(self):
        snap={'messages':[{'id':'old','from':'orchestrator','to':'worker','subject':'Delegation'}], 'tasks':[{'id':'job','status':'done'}], 'events':[{'kind':'delegation','agentId':'orchestrator','to':'worker','taskId':'job'}]}
        self.assertEqual(interactions(snap,self.home),[])
        snap['tasks'][0]['status']='doing'
        self.assertEqual(len(interactions(snap,self.home)),1)
