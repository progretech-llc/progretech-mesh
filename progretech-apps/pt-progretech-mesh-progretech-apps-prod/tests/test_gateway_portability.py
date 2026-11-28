"""Imported runtime identities need no private scheduler, but never bypass one."""
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from control_center.mesh_runtime import MeshRuntime, _CONTROL_CACHE, role_controls, scheduler_record
from control_center.provider import AgentControlProvider


class GatewayPortabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.roles=('main','researcher','coder','custom_writer','codex','moxy')
        self.config={'agents':{'entries':{role:{'model':'remote/model'} for role in self.roles}},
                     'gateway':{'port':18789,'auth':{'token':'fixture'},'http':{'endpoints':{'chatCompletions':{'enabled':True}}}}}
        (self.home/'.openclaw').mkdir()
        self.config_path=self.home/'.openclaw/openclaw.json'
        self.config_path.write_text(json.dumps(self.config))
        self.provider=AgentControlProvider(self.home/'profiles',{'host--'+role:role for role in self.roles},lambda r:{},lambda *a:{})
        self.runtime=MeshRuntime(self.provider,self.home)
        self.runtime.idle=lambda:True
        self.runtime.health=lambda a:{'state':'unknown'}
        self.rows=[]
        self.calls=[]
        self.addCleanup(lambda:_CONTROL_CACHE.pop(str(self.home),None))

    def scheduler(self, rows):
        command=self.home/'ptinternal/bin/factory-workday'
        command.parent.mkdir(parents=True,exist_ok=True);command.touch()
        self.rows=rows
        def run(args,**kwargs):
            self.calls.append(args)
            self.assertEqual(args[:2],[str(command),'status'])
            return SimpleNamespace(returncode=0,stdout=json.dumps({'controls':self.rows}))
        mock=patch('control_center.mesh_runtime.subprocess.run',side_effect=run)
        mock.start();self.addCleanup(mock.stop)
        return command

    def done(self, job):
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            result=self.runtime.get(job['agent_id'],job['job_id'])
            if result['done']:return result
            time.sleep(.01)
        self.fail('Fixture chat did not finish')

    def test_foreign_host_custom_and_legacy_ids_have_chat_without_scheduler_controls(self):
        with patch('control_center.mesh_runtime.subprocess.run') as run:
            for role in self.roles:
                agent='host--'+role
                with self.subTest(role=role):
                    admission=self.runtime.chat_admission(agent)
                    self.assertEqual(admission,{'available':True,'reason':None,'scheduler':'unmanaged'})
                    status=self.runtime.status(agent)
                    self.assertTrue(status['chat_available'])
                    self.assertFalse(status['controls_available'])
                    self.assertFalse(status['active_context_available'])
                    self.assertIsNone(status['sleeping'])
            run.assert_not_called()
        self.assertFalse(scheduler_record(self.home).exists())

    def test_custom_chat_reaches_exact_native_identity_with_no_private_helper(self):
        requests=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,size):return b'{"choices":[{"message":{"content":"fixture reply"}}]}'
        self.runtime.open=lambda req,**kwargs:requests.append(req) or Response()
        result=self.done(self.runtime.chat('host--custom_writer','Fixture request'))
        self.assertEqual(result['result']['reply'],'fixture reply')
        self.assertEqual(len(requests),1)
        self.assertEqual(requests[0].get_header('X-openclaw-agent-id'),'custom_writer')
        self.assertEqual(requests[0].get_header('X-openclaw-session-key'),'agent:custom_writer:mesh-chat:host--custom_writer')

    def test_custom_and_existing_mapped_roles_honor_scheduler_pause(self):
        self.scheduler([{'role':r,'mode':'paused'} for r in ('custom_writer','rend','lyra','mak')])
        for role in ('custom_writer','main','researcher','coder'):
            with self.subTest(role=role):
                agent='host--'+role
                self.assertTrue(self.runtime.sleeping(agent))
                self.assertEqual(self.runtime.chat_admission(agent)['reason'],'mesh_agent_sleeping')
                with self.assertRaisesRegex(ValueError,'^mesh_agent_sleeping$'):
                    self.runtime.chat(agent,'Must not run')
        self.assertFalse(self.runtime.jobs)

    def test_healthy_scheduler_does_not_invent_management_for_unlisted_custom_role(self):
        self.scheduler([{'role':'rend','mode':'running'}])
        self.assertEqual(self.runtime.chat_admission('host--custom_writer')['scheduler'],'unmanaged')
        self.assertTrue(self.runtime.chat_admission('host--custom_writer')['available'])
        self.assertFalse(self.runtime.chat_admission('host--coder')['available'])

    def test_successful_custom_management_is_retained_when_row_or_helper_disappears(self):
        command=self.scheduler([{'role':'custom_writer','mode':'running'}])
        self.assertFalse(self.runtime.sleeping('host--custom_writer'))
        self.assertEqual(json.loads(scheduler_record(self.home).read_text())['roles'],['custom_writer'])
        self.assertEqual(scheduler_record(self.home).stat().st_mode & 0o777,0o600)
        self.rows=[];_CONTROL_CACHE.pop(str(self.home),None)
        with self.assertRaisesRegex(ValueError,'^runtime_controls_unavailable$'):role_controls(self.home)
        command.unlink()
        other=MeshRuntime(self.provider,self.home)
        self.assertFalse(other.chat_admission('host--custom_writer')['available'])
        with self.assertRaisesRegex(ValueError,'^runtime_controls_unavailable$'):
            other.chat('host--custom_writer','Must not run')

    def test_existing_state_or_capability_without_helper_fails_closed(self):
        for kind in ('workday','record','broken_helper','broken_record','broken_legacy'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory:
                home=Path(directory)
                if kind=='workday':(home/'.local/state/progretech-workday').mkdir(parents=True)
                else:
                    path=home/'ptinternal/bin/factory-workday' if kind=='broken_helper' else scheduler_record(home)
                    if kind=='broken_legacy':path=home/'Rend/bin/factory-workday'
                    path.parent.mkdir(parents=True)
                    if kind.startswith('broken'):path.symlink_to(home/'absent')
                    else:path.write_text('{"version":1,"configured":true,"roles":["custom_writer"]}')
                with self.assertRaisesRegex(ValueError,'^runtime_controls_unavailable$'):role_controls(home)

    def test_scheduler_errors_never_become_unmanaged_even_for_old_exempt_roles(self):
        self.scheduler([{'role':'custom_writer','mode':'running'}])
        failures=[SimpleNamespace(returncode=1,stdout='sensitive diagnostic'),
                  SimpleNamespace(returncode=0,stdout='invalid'),
                  SimpleNamespace(returncode=0,stdout='{}'),
                  SimpleNamespace(returncode=0,stdout='{"controls":[{"role":"custom_writer","mode":[]}]}'),
                  SimpleNamespace(returncode=0,stdout='{"controls":[{"role":"custom_writer","mode":"unknown"}]}'),
                  SimpleNamespace(returncode=0,stdout='{"controls":[{"role":"custom_writer","mode":"sleeping","until":true}]}')]
        for response in failures:
            with self.subTest(response=response),patch('control_center.mesh_runtime.subprocess.run',return_value=response):
                for role in ('custom_writer','codex','moxy'):
                    result=self.runtime.chat_admission('host--'+role)
                    self.assertEqual(result,{'available':False,'reason':'runtime_controls_unavailable','scheduler':'unavailable'})
        for error in (PermissionError('private path'),subprocess.TimeoutExpired('fixture',10)):
            with patch('control_center.mesh_runtime.subprocess.run',side_effect=error):
                self.assertFalse(self.runtime.chat_admission('host--custom_writer')['available'])

    def test_corrupt_capability_record_is_not_replaced_with_unmanaged_state(self):
        self.scheduler([{'role':'rend','mode':'running'}])
        record=scheduler_record(self.home);record.parent.mkdir(parents=True,exist_ok=True)
        for payload in ('invalid','{"version":1,"configured":false,"roles":[]}'):
            record.write_text(payload)
            with self.assertRaisesRegex(ValueError,'^runtime_controls_unavailable$'):role_controls(self.home)
            self.assertEqual(record.read_text(),payload)
        record.unlink();record.symlink_to(self.home/'missing')
        with self.assertRaisesRegex(ValueError,'^runtime_controls_unavailable$'):role_controls(self.home)
        self.assertTrue(record.is_symlink())

    def test_unavailable_active_session_capability_has_clean_error_no_send(self):
        with patch('control_center.mesh_runtime.subprocess.run') as run:
            with self.assertRaisesRegex(ValueError,'^runtime_context_unavailable$'):
                self.runtime.context('host--custom_writer','Fixture steering')
            run.assert_not_called()

    def test_custom_active_session_requires_fresh_exact_observation(self):
        self.scheduler([{'role':'custom_writer','mode':'running'}])
        role_controls(self.home)
        file=self.home/'.local/state/progretech-workday/activity.json'
        file.parent.mkdir(parents=True)
        def observe(session):file.write_text(json.dumps({'agents':{'custom_writer':{'state':'active','session':session}}}))
        observe('agent:custom_writer:workday:fixture')
        with patch('control_center.mesh_runtime.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='{"status":"accepted"}')) as run:
            self.assertTrue(self.runtime.context('host--custom_writer','Fixture steering')['accepted'])
            args=json.loads(run.call_args.args[0][-2]);self.assertEqual(args['agentId'],'custom_writer')
            self.assertEqual(args['sessionKey'],'agent:custom_writer:workday:fixture')
            self.assertEqual(args['queueMode'],'steer');self.assertEqual(run.call_count,1)
        observe('agent:other:workday:fixture')
        with self.assertRaisesRegex(ValueError,'^mesh_active_session_unavailable$'):
            self.runtime.context('host--custom_writer','Fixture steering')
        observe('agent:custom_writer:workday:fixture');os.utime(file,(time.time()-100,)*2)
        with self.assertRaisesRegex(ValueError,'^mesh_no_active_work$'):
            self.runtime.context('host--custom_writer','Fixture steering')

    def test_readiness_requires_usable_configuration_as_well_as_binding(self):
        for key,value,reason in (('port',False,'runtime_port_invalid'),('auth',{},'runtime_auth_unavailable')):
            with self.subTest(key=key):
                config=json.loads(json.dumps(self.config));config['gateway'][key]=value
                self.config_path.write_text(json.dumps(config))
                self.assertEqual(self.runtime.chat_admission('host--custom_writer')['reason'],reason)
        self.config_path.write_text(json.dumps({'agents':{'entries':{}},'gateway':self.config['gateway']}))
        self.assertFalse(self.runtime.chat_admission('host--custom_writer')['available'])

    def test_custom_control_uses_exact_scheduler_identity_and_confirms_transition(self):
        command=self.scheduler([{'role':'custom_writer','mode':'paused'}])
        self.assertTrue(self.runtime.sleeping('host--custom_writer'))
        calls=[]
        def resume(args,**kwargs):
            calls.append(args)
            if args[1]=='resume':
                self.assertEqual(args,[str(command),'resume','--agent','custom_writer'])
                self.rows[0]['mode']='running'
            return SimpleNamespace(returncode=0,stdout=json.dumps({'controls':self.rows}))
        with patch('control_center.mesh_runtime.subprocess.run',side_effect=resume):
            self.runtime.control('host--custom_writer',True)
        self.assertEqual([call[1] for call in calls],['resume','status'])
        self.assertFalse(self.runtime.sleeping('host--custom_writer'))

    def test_factory_readiness_distinguishes_bound_paused_unmanaged_and_error(self):
        from flask import Flask
        from control_center.rend_bridge import install
        state=self.home/'.progretech-mesh';state.mkdir(exist_ok=True)
        (state/'control-center-bindings.json').write_text('{"host":"custom_writer"}')
        host=SimpleNamespace(app=Flask(__name__),token=lambda:'fixture',MUTATION_LOCK=threading.Lock())
        with patch('control_center.specklet.start_observer'),patch('control_center.office.SPECKLET_OBSERVER'):
            provider=install(host,self.home)
        provider.mesh_runtime.health=lambda agent:{'state':'unknown'}
        inventory={'available':True,'candidates':[{'runtime_id':'custom_writer','name':'Writer'}]}
        def snapshot(*args):return {'snapshot':{'agents':[{'isDirector':True,'runtime_id':'custom_writer'}],'runtimeReady':False}}
        with patch('offline.registry.Registry.discover_gateway',return_value=inventory),patch('control_center.office_identity.synchronize',return_value={'agents':[]}),patch('control_center.office.dispatch_office',side_effect=snapshot):
            def read():return provider.execute('custom_writer','factory.office',{'operation':'snapshot','args':{}},{'agent_id':'host'})['snapshot']
            unmanaged=read()
            self.assertTrue(unmanaged['nativeRuntimeBound']);self.assertTrue(unmanaged['nativeRuntimeReady'])
            self.scheduler([{'role':'custom_writer','mode':'paused'}])
            paused=read()
            self.assertTrue(paused['nativeRuntimeBound']);self.assertFalse(paused['runtimeReady'])
            self.assertFalse(paused['nativeRuntimeReady']);self.assertEqual(paused['nativeAdmissionReason'],'mesh_agent_sleeping')
            _CONTROL_CACHE.pop(str(self.home),None)
            with patch('control_center.mesh_runtime.subprocess.run',side_effect=PermissionError('fixture')):
                failed=read()
            self.assertTrue(failed['nativeRuntimeBound']);self.assertFalse(failed['nativeRuntimeReady'])
            self.assertEqual(failed['nativeAdmissionReason'],'runtime_controls_unavailable')
