"""Offline isolation and real Python-project onboarding, without cloud credentials."""
import json
import os
import sys
import tempfile
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch
from offline.app import create_app
from offline.registry import Registry


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.app = create_app(self.home, 'test-desktop-token', include_starter=False)
        self.client = self.app.test_client()
        self.client.set_cookie('mesh_local', 'test-desktop-token', domain='127.0.0.1')
        self.origin = 'http://127.0.0.1:19291'

    def tearDown(self): self.temp.cleanup()

    def post(self, route, body):
        return self.client.post(route, json=body, base_url=self.origin, headers={'Origin':self.origin})

    def add_python(self):
        script = self.home / 'agent.py'
        script.write_text('import json,sys\nq=json.load(sys.stdin)["question"]\nprint("I am the local Python test agent. " + q)\n')
        response = self.post('/api/local/agents', {'kind':'pycharm', 'name':'Python project', 'executable':sys.executable,
            'workspace':str(self.home), 'entrypoint':str(script), 'confirmed':True, 'intermediary':True})
        self.assertEqual(response.status_code, 200)
        return response.json['agent']

    def test_real_python_agent_is_awake_only_after_answer(self):
        agent = self.add_python()
        self.assertFalse(agent['awake'])
        answer = self.post('/api/local/agents/'+agent['id']+'/ask', {'question':'Identify yourself'})
        self.assertEqual(answer.status_code, 200)
        self.assertIn('local Python test agent', answer.json['answer'])
        self.assertTrue(answer.json['agent']['awake'])
        self.assertFalse(list(self.home.rglob('*.pem')))
        self.assertNotIn('codeseal', json.dumps(answer.json).lower())

    def test_cross_origin_and_missing_desktop_cookie_rejected(self):
        self.assertEqual(self.app.test_client().get('/', base_url=self.origin).status_code, 403)
        response = self.client.post('/api/local/agents', json={}, base_url=self.origin, headers={'Origin':'https://attacker.example'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get('/', base_url='http://attacker.example').status_code, 403)

    def test_import_requires_personal_ownership_and_real_paths(self):
        self.assertEqual(self.post('/api/local/agents', {'kind':'claude'}).status_code, 400)
        self.assertEqual(self.post('/api/local/agents', {'kind':'claude','name':'x','confirmed':True,'intermediary':True,
            'workspace':str(self.home),'executable':'not-an-absolute-path'}).status_code, 400)

    def test_same_local_runtime_cannot_run_two_turns_at_once(self):
        from control_center.file_lock import lock, unlock
        agent = self.add_python()
        identity = '|'.join([agent['kind'], agent['executable'], agent['runtime_id'], agent['workspace']])
        locks = self.home / '.progretech-mesh/offline/runtime-locks'; locks.mkdir()
        with (locks/(hashlib.sha256(identity.encode()).hexdigest()+'.lock')).open('a+') as guard:
            lock(guard, blocking=False)
            try:
                response = self.post('/api/local/agents/'+agent['id']+'/ask', {'question':'Identity'})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['error'], 'local_agent_is_busy')
            finally: unlock(guard)

    def test_office_works_without_model_or_cloud(self):
        with patch('socket.create_connection', side_effect=AssertionError('offline test attempted networking')):
            response = self.post('/api/agents/desktop/office', {'operation':'hire','args':{'name':'Ada','role':'Researcher','goal':'Review local data'}})
        self.assertEqual(response.status_code, 200)
        snapshot = response.json['result']['snapshot']
        self.assertEqual(len(snapshot['agents']), 2)
        self.assertFalse(snapshot['runtimeReady'])

    def test_discovery_only_extracts_public_runtime_fields(self):
        config = self.home / '.openclaw'; config.mkdir()
        (config/'openclaw.json').write_text(json.dumps({'gateway':{'token':'never-import-me'}, 'agents':{'list':[
            {'id':'test','name':'Test','workspace':str(self.home),'private':'never-import-me'}]}}))
        with patch('shutil.which', side_effect=lambda name, **kwargs: sys.executable if name=='openclaw' else None):
            candidates = Registry(self.home).discover(self.home)
        self.assertEqual(candidates[0]['runtime_id'], 'test')
        self.assertNotIn('never-import-me', json.dumps(candidates))

    def test_settings_are_local_gguf_only(self):
        self.assertEqual(self.post('/api/local/settings', {'gguf':'https://example.com/model'}).status_code, 400)
        model = self.home/'fixture.gguf'; model.write_bytes(b'GGUF')
        agent = self.add_python()
        hired = self.post('/api/agents/desktop/office', {'operation':'hire','args':{'name':'Ada','role':'Researcher','goal':'Review'}})
        worker = next(a['id'] for a in hired.json['result']['snapshot']['agents'] if not a['isDirector'])
        self.assertEqual(self.post('/api/local/settings', {'gguf':str(model),'bindings':{worker:agent['id']}}).status_code, 200)
        config = json.loads((self.home/'.progretech-mesh/factory-runtimes.json').read_text())
        self.assertEqual(config['crewai']['gguf'], str(model.resolve()))
        self.assertNotIn('api_key', json.dumps(config))


if __name__ == '__main__': unittest.main()
