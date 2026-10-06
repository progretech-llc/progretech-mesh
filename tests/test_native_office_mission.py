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

    @patch('control_center.office.threading.Thread')
    @patch('control_center.office.engine')
    def test_native_mission_starts_bound_assignee_and_monitor(self, engine, thread):
        engine.return_value = {'result': {'task': {
            'id': 'task-123456789abc', 'title': 'Review Mesh',
            'description': 'Inspect the production behavior.', 'assignee': 'orchestrator'
        }, 'agents': [{'id': 'orchestrator', 'runtime_id': 'codex'}]}}
        provider = SimpleNamespace(bindings={'rend': 'main', 'rend--codex': 'codex'})
        mesh = SimpleNamespace(chat=lambda agent, text, owner_text=None: {'job_id': 'job-1'})
        result = dispatch_native_mission('/tmp/home', 'main', 'task-123456789abc', 'rend', provider, mesh)
        self.assertEqual(result, {'job_id': 'job-1', 'state': 'queued', 'provider': 'openclaw'})
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()


if __name__ == '__main__':
    unittest.main()
