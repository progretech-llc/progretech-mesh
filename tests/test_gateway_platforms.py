import json
import shutil
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from gateway.platforms import Platform, runtime_key
from gateway.platform_gateway import Connector
from mesh_gateways import activate, visible
from control_center.office import engine, namespace


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        root = self.home / '.hermes'
        root.mkdir()
        (root / 'config.yaml').write_text('model:\n  default: local-model\nmemory:\n  provider: hindsight\n')
        for name in ['progre', 'builder', 'records']:
            p = root / 'profiles' / name
            p.mkdir(parents=True)
            (p / 'config.yaml').write_text('model:\n  default: local-model\nmcp_servers:\n  shared-knowledge: {}\n')
        self.config = {'platform': 'hermes', 'workspace': str(self.home), 'prime': 'progre',
            'agent_id': 'agent-fixture', 'excluded_agents': ['records'], 'mesh': 'https://mesh.example', 'device_credential': 'test'}

    def test_discovers_all_profiles_without_private_context_and_denies_excluded(self):
        platform = Platform(self.config, self.home)
        rows = platform.discover()
        self.assertEqual({r['runtime_id'] for r in rows}, {'default', 'progre', 'builder', 'records'})
        self.assertTrue(platform.rows['builder']['rag_available'])
        self.assertEqual(platform.rows['default']['memory_provider'], 'hindsight')
        with self.assertRaisesRegex(ValueError, 'disabled'):
            platform.complete('records', {'messages': []})

    def test_cli_uses_native_profile_stdin_and_no_permission_bypass(self):
        platform = Platform(self.config, self.home)
        platform.discover()
        with patch('gateway.platforms.shutil.which', return_value='/bin/hermes'), patch('gateway.platforms.subprocess.run') as run:
            run.return_value = __import__('subprocess').CompletedProcess([], 0, 'actual reply', '')
            result = platform.complete('builder', {'messages': [{'role': 'user', 'content': 'secret task'}]})
            self.assertEqual(result['choices'][0]['message']['content'], 'actual reply')
            command = run.call_args.args[0]
            self.assertEqual(command[command.index('--profile') + 1], 'builder')
            self.assertNotIn('secret task', command)
            self.assertNotIn('--yolo', command)
            self.assertIn('secret task', run.call_args.kwargs['input'])

    def test_api_models_bind_exact_model_and_do_not_follow_cloud_target_urls(self):
        platform = Platform({**self.config, 'platform': 'openai'}, self.home)
        with patch.object(platform, 'api', return_value={'data': [{'id': 'llama/model:latest'}]}):
            rows = platform.discover()
        runtime = rows[0]['runtime_id']
        with patch.object(platform, 'api', return_value={'choices': [{'message': {'content': 'ok'}}]}) as api:
            platform.complete(runtime, {'model': 'other-model', 'messages': []})
            self.assertEqual(api.call_args.args[1]['model'], 'llama/model:latest')
        for endpoint in ['http://remote.example/v1', 'https://user:secret@host/v1', 'file:///etc', 'https://host/v1?token=secret']:
            platform.config['endpoint'] = endpoint
            with self.assertRaisesRegex(ValueError, 'endpoint_required'):
                platform.api('/models')

    @unittest.skipUnless(shutil.which('node'), 'Factory board requires host Node.js')
    def test_prime_is_initial_scrum_master_and_change_survives_refresh(self):
        connector = Connector(self.config, self.home)
        office = namespace('progre', 'agent-fixture')
        snapshot = engine(self.home, office, 'snapshot')['snapshot']
        prime = next(r for r in snapshot['agents'] if r['isScrumMaster'])
        self.assertEqual(prime['runtime_id'], 'progre')
        worker = next(r for r in snapshot['agents'] if r.get('runtime_id') == 'builder')
        connector.control('agent-fixture', 'factory.office', {'operation': 'orchestrator.set', 'args': {'id': worker['id']}})
        roster = connector.roster()
        self.assertTrue(next(r for r in roster['agents'] if r['runtime_id'] == 'builder')['is_orchestrator'])
        self.assertFalse(roster['host']['is_orchestrator'])
        disabled = next(r for r in snapshot['agents'] if r.get('runtime_id') == 'records')
        with self.assertRaisesRegex(ValueError, 'enabled_runtime'):
            connector.control('agent-fixture', 'factory.office', {'operation': 'orchestrator.set', 'args': {'id': disabled['id']}})

    @unittest.skipUnless(shutil.which('node'), 'Factory board requires host Node.js')
    def test_prime_roster_crosses_server_boundary_with_its_model_and_runtime(self):
        from mesh_control_center import register_gateway_agents
        connector = Connector(self.config, self.home)
        registry = {'agent-fixture': {'id': 'agent-fixture', 'owner_id': 'owner', 'trust_state': 'verified'}}
        self.assertTrue(register_gateway_agents('agent-fixture', connector.roster(), registry))
        self.assertEqual(registry['agent-fixture']['runtime_id'], 'progre')
        self.assertEqual(registry['agent-fixture']['model'], 'local-model')
        self.assertTrue(registry['agent-fixture']['is_orchestrator'])
        self.assertNotIn('agent-fixture--progre', registry)
        self.assertIn('agent-fixture--builder', registry)

    @unittest.skipUnless(shutil.which('node'), 'Factory board requires host Node.js')
    def test_ide_relay_and_factory_use_bound_runtime_and_return_real_receipts(self):
        connector = Connector(self.config, self.home)
        completion = {'id': 'test', 'object': 'chat.completion', 'model': 'local-model',
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': '{"action":"complete","text":"fixture checked","evidence":"synthetic assertion"}'}, 'finish_reason': 'stop'}]}
        with patch.object(connector.platform, 'complete', return_value=completion) as invoke:
            reply = connector.message({'type': 'ide_chat_request', 'request_id': 'test',
                'payload': {'target': {'agent_id': 'agent-fixture--builder', 'runtime_id': 'builder'},
                    'openai': {'model': 'agent-fixture--builder', 'messages': [{'role': 'user', 'content': 'test'}]}}})
            self.assertTrue(reply['payload']['ok'])
            self.assertEqual(invoke.call_args.args[0], 'builder')
            created = connector.control('agent-fixture', 'factory.office', {'operation': 'task.create',
                'args': {'title': 'Synthetic check', 'description': 'No side effects', 'assignee': '', 'dependsOn': [], 'needsApproval': False}})
            task = created['result']['id']
            connector.control('agent-fixture', 'factory.office', {'operation': 'run', 'args': {'id': task}})
            for _ in range(40):
                snapshot = engine(self.home, namespace('progre', 'agent-fixture'), 'snapshot')['snapshot']
                current = next(t for t in snapshot['tasks'] if t['id'] == task)
                if current['status'] == 'done':
                    break
                time.sleep(.2)
            self.assertEqual(current['status'], 'done')
        wrong = connector.message({'type': 'ide_chat_request', 'request_id': 'bad', 'payload':
            {'target': {'agent_id': 'foreign', 'runtime_id': 'builder'}, 'openai': {}}})
        self.assertFalse(wrong['payload']['ok'])


class GatewaySelectionTests(unittest.TestCase):
    def test_single_owner_slot_replacement_and_old_reconnect_denial(self):
        from unittest.mock import Mock
        old = Mock()
        rows = {'old': {'id': 'old', 'owner_id': 'owner', 'gateway_active': True},
                'new': {'id': 'new', 'owner_id': 'owner', 'gateway_activation_pending': True},
                'foreign': {'id': 'foreign', 'owner_id': 'other', 'gateway_active': True},
                'old--worker': {'id': 'old--worker', 'control_center_gateway': 'old'}}
        sockets = {'old': old, 'foreign': Mock()}
        activate(rows, sockets, 'new')
        old.close.assert_called_once()
        self.assertIn('foreign', sockets)
        self.assertFalse(visible(rows['old--worker'], rows))
        with self.assertRaisesRegex(ValueError, 'another_gateway_active'):
            activate(rows, sockets, 'old')
        activate(rows, sockets, 'new')
        self.assertTrue(rows['new']['gateway_active'])
