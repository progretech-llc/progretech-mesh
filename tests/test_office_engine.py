import tempfile
import unittest
from control_center.office import engine, validate_office


class OfficeTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        self.role = 'test-runtime'

    def run_op(self, op, args=None):
        return engine(self.home.name, self.role, op, args)

    def test_real_hive_workflow(self):
        first = self.run_op('snapshot')
        self.assertEqual(first['snapshot']['agents'][0]['id'], 'orchestrator')
        worker = self.run_op('hire', {'name': 'Ada', 'role': 'Researcher', 'goal': 'Research bounded tasks'})['result']['id']
        task = self.run_op('task.create', {'title': 'Research', 'description': 'Gather evidence', 'assignee': worker, 'dependsOn': [], 'needsApproval': True})['result']['id']
        self.assertRaisesRegex(ValueError, 'task_not_ready', self.run_op, 'begin', {'id': task})
        self.run_op('task.approve', {'id': task, 'answer': 'Approved'})
        self.run_op('message', {'to': worker, 'text': 'Use primary sources'})
        mission = self.run_op('begin', {'id': task})['result']
        self.assertIn('Use primary sources', next(a for a in mission['agents'] if a['id'] == worker)['messages'])
        self.run_op('finish', {'id': task, 'ok': True, 'result': 'Evidence found'})
        final = self.run_op('snapshot')['snapshot']
        self.assertEqual(final['tasks'][0]['status'], 'done')
        self.assertEqual(final['tasks'][0]['result'], 'Evidence found')
        self.assertEqual(final['tasks'][0]['humanQA'][0]['a'], 'Approved')

    def test_dependencies_and_pause(self):
        a = self.run_op('task.create', {'title': 'First', 'description': '', 'assignee': '', 'dependsOn': [], 'needsApproval': False})['result']['id']
        b = self.run_op('task.create', {'title': 'Second', 'description': '', 'assignee': '', 'dependsOn': [a], 'needsApproval': False})['result']['id']
        self.assertRaisesRegex(ValueError, 'task_not_ready', self.run_op, 'begin', {'id': b})
        self.run_op('pause', {'paused': True})
        self.assertRaisesRegex(ValueError, 'office_paused', self.run_op, 'begin', {'id': a})

    def test_role_isolation_and_memory(self):
        a = self.run_op('hire', {'name': 'Ada', 'role': 'Researcher', 'goal': 'Research'})['result']['id']
        self.run_op('memory.save', {'id': a, 'text': 'Reviewed fact'})
        self.assertEqual(self.run_op('memory', {'id': a})['result']['text'], 'Reviewed fact')
        other = engine(self.home.name, 'other-runtime', 'snapshot')['snapshot']
        self.assertEqual(len(other['agents']), 1)
        self.assertRaisesRegex(ValueError, 'office_agent_not_found', self.run_op, 'memory', {'id': '../orchestrator'})

    def test_protocol_rejects_commands_and_paths(self):
        for args in [{'operation': 'shell', 'args': {}}, {'operation': 'snapshot', 'args': {'home': '/etc'}},
                     {'operation': 'settings', 'args': {'maxIterations': True}}, {'operation': 'run', 'args': {'id': 'x', 'command': 'id'}}]:
            self.assertRaises(ValueError, validate_office, args)

    def test_enrollment_isolation_on_the_same_runtime(self):
        from control_center.office import dispatch_office
        operation = {'operation': 'hire', 'args': {'name': 'Ada', 'role': 'Researcher', 'goal': 'Research'}}
        dispatch_office(self.home.name, self.role, operation, 'owner-a-agent')
        other = dispatch_office(self.home.name, self.role, {'operation': 'snapshot', 'args': {}}, 'owner-b-agent')
        self.assertEqual([a['name'] for a in other['snapshot']['agents']], ['Scrum Master'])
