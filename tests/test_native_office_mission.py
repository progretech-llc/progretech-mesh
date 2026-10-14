import unittest
from types import SimpleNamespace
from unittest.mock import patch

from control_center.office import dispatch_native_mission, native_binding


class NativeOfficeMissionTests(unittest.TestCase):
    def test_binding_is_scoped_to_the_enrolled_gateway(self):
        provider = SimpleNamespace(bindings={
            'rend': 'main', 'rend--codex': 'codex', 'other--codex': 'codex'
        })
        self.assertEqual(native_binding(provider, 'rend', 'main'), 'rend')
        self.assertEqual(native_binding(provider, 'rend', 'codex'), 'rend--codex')
        self.assertIsNone(native_binding(provider, 'rend', 'researcher'))

    @patch('control_center.office_native.threading.Thread')
    @patch('control_center.office.engine')
    def test_native_mission_starts_bound_assignee_and_monitor(self, engine, thread):
        engine.return_value = {'result': {'task': {
            'id': 'task-123456789abc', 'title': 'Review Mesh',
            'description': 'Inspect the production behavior.', 'assignee': 'orchestrator', 'runId':'test-lease', 'coordinator':'orchestrator'
        }, 'agents': [{'id': 'orchestrator', 'runtime_id': 'codex'}]}, 'snapshot':{'paused':False}}
        engine.return_value['snapshot'].update(tasks=[dict(engine.return_value['result']['task'],queued=True)],agents=[{'id':'orchestrator','runtime_id':'codex','isScrumMaster':True}])
        provider = SimpleNamespace(bindings={'rend': 'main', 'rend--codex': 'codex'})
        calls = []
        def chat(agent, text, owner_text=None, response_timeout=None, mission=False):
            calls.append((agent, response_timeout))
            return {'job_id': 'job-1'}
        mesh = SimpleNamespace(chat=chat)
        result = dispatch_native_mission('/tmp/home', 'main', 'task-123456789abc', 'rend', provider, mesh)
        self.assertEqual(result, {'job_id': 'job-1', 'task_id':'task-123456789abc', 'state': 'queued', 'provider': 'openclaw'})
        self.assertEqual(calls, [('rend--codex', 7200)])
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()


if __name__ == '__main__':
    unittest.main()
