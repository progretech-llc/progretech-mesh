import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from mesh_runtime_enrollment import register_runtime_enrollment
from gateway.platform_register import candidate, register


class RuntimeEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask(__name__,root_path=str(Path(__file__).resolve().parents[1]));self.app.secret_key='test'
        self.owner='owner'
        self.registry={'host':{'id':'host','owner_id':'owner','trust_state':'verified'},
                       'other':{'id':'other','owner_id':'other','trust_state':'verified'}}
        register_runtime_enrollment(self.app,lambda f:f,lambda:self.owner,self.registry,lambda:'https://mesh.test',
                                   lambda aid,secret:(secret=='device-secret','ok',{}))
        self.client=self.app.test_client()

    def begin(self,**overrides):
        return self.client.post('/api/runtime-enrollment',json={'gateway':'host','platform':'codex','name':'Coder','personally_hosted':True,'accept_intermediary':True,**overrides},headers={'Origin':'http://localhost'})

    def test_owner_and_origin_are_required(self):
        self.assertEqual(self.begin(gateway='other').status_code,403)
        self.assertEqual(self.client.post('/api/runtime-enrollment',json={}).status_code,403)
        self.assertEqual(self.begin(platform=[]).status_code,400)
        self.assertEqual([h['id'] for h in self.client.get('/api/runtime-enrollment/hosts').json['hosts']],['host'])

    def test_invitation_is_exact_host_bound_and_retry_is_idempotent(self):
        response=self.begin();self.assertEqual(response.status_code,201)
        payload=next(line for line in response.json['prompt'].splitlines() if line.startswith('PTMR1:'))
        invitation=json.loads(base64.urlsafe_b64decode(payload[6:]))
        self.assertNotIn('device-secret',response.json['prompt'])
        url='/api/runtime-enrollment/'+response.json['id']+'/redeem'
        headers={'Authorization':'Bearer '+invitation['token']}
        body={'agent_id':'host','device_credential':'bad','native_id':'local'}
        self.assertEqual(self.client.post(url,json=body,headers=headers).status_code,403)
        body['device_credential']='device-secret'
        self.assertEqual(self.client.post(url,json=body,headers=headers).status_code,200)
        self.assertEqual(self.client.post(url,json=body,headers=headers).status_code,200)
        status='/api/runtime-enrollment/'+response.json['id']
        self.assertEqual(self.client.get(status).json['state'],'authorized')
        complete=status+'/complete'
        self.assertEqual(self.client.post(complete,json={**body,'device_credential':'bad'},headers=headers).status_code,403)
        self.assertEqual(self.client.post(complete,json=body,headers=headers).status_code,200)
        self.assertEqual(self.client.get(status).json['state'],'complete')
        body['native_id']='another'
        self.assertEqual(self.client.post(url,json=body,headers=headers).status_code,409)
        self.owner='other'
        self.assertEqual(self.client.get('/api/runtime-enrollment/'+response.json['id']).status_code,404)

    def test_manifest_preserves_identity_and_other_members(self):
        old={'platform':'hermes','prime':'imagen','workspace':'/tmp','agent_id':'host','device_credential':'secret'}
        mixed,key=candidate(old,'codex','local')
        self.assertEqual(mixed['prime'],'imagen');self.assertEqual(mixed['device_credential'],'secret')
        self.assertEqual(len(mixed['runtimes']),2)
        again,same=candidate(mixed,'codex','local')
        self.assertEqual((again,same),(mixed,key));self.assertEqual(old['platform'],'hermes')

    def test_failed_native_probe_does_not_replace_config(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'connector.json';p.write_text(json.dumps({'platform':'hermes','prime':'imagen','workspace':d}))
            before=p.read_bytes()
            with patch('gateway.platform_register.Platform') as cls:
                cls.return_value.rows={}
                with self.assertRaisesRegex(ValueError,'not_ready'):register(p,'codex','missing')
            self.assertEqual(p.read_bytes(),before)

    def test_helper_rejects_different_origin_before_credentials_leave_host(self):
        spec=importlib.util.spec_from_file_location('join',Path(self.app.root_path)/'distribution/mesh-runtime-join-v1.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d:
            state=Path(d)/'.progretech-mesh/platform';state.mkdir(parents=True)
            (state/'connector.json').write_text(json.dumps({'mesh':'https://mesh.test','agent_id':'host','device_credential':'secret'}))
            p=Path(d)/'payload';p.write_text('PTMR1:'+base64.urlsafe_b64encode(json.dumps({'mesh':'https://evil.test','gateway':'host'}).encode()).decode())
            with self.assertRaisesRegex(ValueError,'does_not_match'):module.load_binding(p,d)

class NativeHarnessGrantTests(unittest.TestCase):
    def test_an_existing_native_grant_needs_no_new_permission_or_pane(self):
        from gateway.platform_register import harness_control
        from types import SimpleNamespace
        with patch('gateway.platform_register.shutil.which',return_value='/bin/harness'), patch('gateway.platform_register.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='{"allowed":true}')) as run:
            self.assertEqual(harness_control('native',grant=True),'ready')
            self.assertEqual(run.call_count,1)
            self.assertEqual(run.call_args.kwargs['env']['TMUX_PANE'],'')

    def test_only_the_actual_session_may_opt_in_and_it_uses_the_native_grant(self):
        from gateway.platform_register import harness_control
        from types import SimpleNamespace
        responses=[SimpleNamespace(returncode=0,stdout='{"allowed":false}'),SimpleNamespace(returncode=0,stdout='{"context":{"caller":{"inside":true,"id":"native"}}}'),SimpleNamespace(returncode=0,stdout='{"allowed":true}')]
        with patch('gateway.platform_register.shutil.which',return_value='/bin/harness'), patch('gateway.platform_register.subprocess.run',side_effect=responses) as run:
            self.assertEqual(harness_control('native',grant=True),'granted')
            self.assertEqual(run.call_args.args[0][1],'delegate-followup')
            self.assertNotIn('env',run.call_args.kwargs) # Actual pane, never a fabricated one.
        responses=[SimpleNamespace(returncode=0,stdout='{"allowed":false}'),SimpleNamespace(returncode=0,stdout='{"context":{"caller":{"inside":true,"id":"someone-else"}}}')]
        with patch('gateway.platform_register.shutil.which',return_value='/bin/harness'), patch('gateway.platform_register.subprocess.run',side_effect=responses) as run:
            with self.assertRaisesRegex(ValueError,'exact_native'):harness_control('native',grant=True)
            self.assertEqual(run.call_count,2)
