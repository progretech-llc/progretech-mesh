import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from mesh_gateway_agents import enrollment_binding
from offline.registry import MAX_GATEWAY_ROSTER_BYTES, Registry, runtime_executable


def pem():
    return Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


class GatewayIdentityTests(unittest.TestCase):
    def setUp(self):
        self.registry = {'host':{'id':'host','owner_id':'owner','trust_state':'verified',
            'public_key':pem(),'identified_agents':[{'id':'host--mak','name':'Mak'}]}}
        self.gateways = {'host':object()}
        self.payload = {'gateway_id':'host','gateway_candidate_id':'host--mak',
            'agent_id':'host--mak','public_key':pem(),
            'codeseal_evidence':{'manifest':{'mesh_identity':{'agent_id':'host--mak'}}}}

    def test_each_selected_agent_has_an_independent_key_and_binding(self):
        binding = enrollment_binding(self.payload, 'owner', self.registry, self.gateways)
        self.assertEqual(binding['control_center_gateway'],'host')
        self.assertTrue(binding['gateway_enrollment'])
        self.assertNotIn('host--mak',self.registry)

    def test_cannot_inherit_host_pem_or_reuse_other_agent_pem(self):
        self.payload['public_key']=self.registry['host']['public_key']
        with self.assertRaisesRegex(ValueError,'own_pem'):
            enrollment_binding(self.payload,'owner',self.registry,self.gateways)
        self.registry['other']={'public_key':pem()}
        self.payload['public_key']=self.registry['other']['public_key']
        with self.assertRaisesRegex(ValueError,'own_pem'):
            enrollment_binding(self.payload,'owner',self.registry,self.gateways)

    def test_owner_connection_candidate_and_signed_id_are_rechecked(self):
        for mutation in ('owner','offline','retired','mismatched','duplicate','bad-evidence'):
            with self.subTest(mutation=mutation):
                registry=copy.deepcopy(self.registry);payload=copy.deepcopy(self.payload);gateways=dict(self.gateways)
                if mutation=='owner':registry['host']['owner_id']='other'
                if mutation=='offline':gateways.clear()
                if mutation=='retired':registry['host']['identified_agents']=[]
                if mutation=='mismatched':payload['agent_id']='unrelated'
                if mutation=='duplicate':registry['host--mak']={'owner_id':'owner','control_center_gateway':'host','gateway_enrollment':True}
                if mutation=='bad-evidence':payload['codeseal_evidence']='invalid'
                with self.assertRaises(ValueError):enrollment_binding(payload,'owner',registry,gateways)


class LocalGatewayTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.home=Path(self.directory.name)
        self.registry=Registry(self.home)
        self.exe=self.home/'openclaw';self.exe.write_text('');self.exe.chmod(0o700)

    def tearDown(self):self.directory.cleanup()

    @unittest.skipIf(os.name == 'nt', 'POSIX desktop/service PATH regression')
    def test_boot_path_discovers_user_installed_gateway_without_shell_setup(self):
        bindir=self.home/'.local/bin';bindir.mkdir(parents=True)
        executable=bindir/'openclaw';executable.write_text('');executable.chmod(0o700)
        def run(args, **kwargs):
            self.assertEqual(args[0],str(executable))
            return subprocess.CompletedProcess(args,0,json.dumps({'agents':[
                {'id':'main','name':'Main','workspace':str(self.home)}]}),'')
        with patch.dict(os.environ, {'PATH':str(self.home/'empty-path')}):
            first=self.registry.discover_gateway(self.home,run)
            restarted=Registry(self.home).discover_gateway(self.home,run)
        self.assertTrue(first['available'])
        self.assertEqual(first,restarted)
        self.assertEqual(len(first['candidates']),1)

    @unittest.skipIf(os.name == 'nt', 'POSIX executable permissions')
    def test_user_bin_fallback_is_allowlisted_and_requires_executable(self):
        bindir=self.home/'.local/bin';bindir.mkdir(parents=True)
        for kind in ('openclaw','hermes','claude','unapproved'):
            executable=bindir/kind;executable.write_text('');executable.chmod(0o700)
        with patch.dict(os.environ, {'PATH':str(self.home/'empty-path')}):
            self.assertIsNone(runtime_executable('unapproved',self.home))
            self.assertEqual({r['kind'] for r in self.registry.discover(self.home)}, {'hermes','claude'})
            if os.name!='nt':
                (bindir/'openclaw').chmod(0o600)
                self.assertIsNone(runtime_executable('openclaw',self.home))

    @unittest.skipIf(os.name == 'nt', 'POSIX executable fixture')
    def test_existing_path_selection_precedes_user_bin(self):
        with patch.dict(os.environ, {'PATH':str(self.home)}):
            self.assertEqual(runtime_executable('openclaw',self.home),str(self.exe))

    def test_live_inventory_is_public_only_and_does_not_auto_import(self):
        public={'id':'mak','name':'Mak','workspace':str(self.home), 'private_memory':'must-not-return', 'credential':'must-not-return'}
        calls=[]
        def run(args,**kwargs):
            calls.append(args);return subprocess.CompletedProcess(args,0,json.dumps({'agents':[public]}),'')
        with patch('offline.registry.shutil.which',return_value=str(self.exe)):
            result=self.registry.discover_gateway(self.home,run)
        self.assertTrue(result['available']);self.assertEqual(self.registry.all(),[])
        self.assertEqual(calls[0][-3:],['--expect-url','ws://127.0.0.1:18789','--json'])
        self.assertNotIn('must-not-return',json.dumps(result))
        candidate=result['candidates'][0];candidate.pop('source')
        row=self.registry.add({**candidate,'confirmed':True,'intermediary':True})
        self.assertEqual(row['runtime_id'],'mak');self.assertNotIn('public_key',row)
        with self.assertRaisesRegex(ValueError,'already_added'):
            self.registry.add({**candidate,'confirmed':True,'intermediary':True})
        with patch('offline.registry.shutil.which',return_value=str(self.exe)):
            self.assertEqual(self.registry.discover_gateway(self.home,run)['candidates'],[])

    def test_inline_avatars_fit_bounded_inventory_but_are_not_returned(self):
        public={'id':'codex','name':'Odexi','workspace':str(self.home),
                'identity':{'avatar':'data:image/jpeg;base64,'+'A'*(5*1024*1024)}}
        def run(args,**kwargs):return subprocess.CompletedProcess(args,0,json.dumps({'agents':[public]}),'')
        with patch('offline.registry.shutil.which',return_value=str(self.exe)):
            result=self.registry.discover_gateway(self.home,run)
        self.assertTrue(result['available'])
        self.assertEqual(result['candidates'][0]['name'],'Odexi')
        self.assertNotIn('avatar',json.dumps(result))
        public['identity']['avatar']='A'*MAX_GATEWAY_ROSTER_BYTES
        with patch('offline.registry.shutil.which',return_value=str(self.exe)):
            self.assertFalse(self.registry.discover_gateway(self.home,run)['available'])

    def test_gateway_failure_is_explicit_and_never_uses_config_as_live_result(self):
        def run(args,**kwargs):return subprocess.CompletedProcess(args,1,'','diagnostic with private details')
        with patch('offline.registry.shutil.which',return_value=str(self.exe)):
            result=self.registry.discover_gateway(self.home,run)
        self.assertFalse(result['available']);self.assertEqual(result['candidates'],[])
        self.assertNotIn('private details',json.dumps(result))




class HostRosterTests(unittest.TestCase):
    def test_live_roles_get_exact_bindings_and_retired_roles_cannot_dispatch(self):
        import threading
        from types import SimpleNamespace
        from flask import Flask
        from control_center.rend_bridge import install
        # This test verifies host binding admission, independent of the host-only
        # Node coordination runtime. Real Hive persistence is exercised by
        # test_office_engine and test_office_identity on the host/CI runtime.
        office = patch('control_center.office_identity.synchronize', return_value={'agents': []})
        office.start(); self.addCleanup(office.stop)
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);(home/'.progretech-mesh').mkdir();(home/'.openclaw').mkdir()
            (home/'.progretech-mesh/control-center-bindings.json').write_text(json.dumps({'host':'main'}))
            (home/'.openclaw/openclaw.json').write_text(json.dumps({'agents':{'entries':{'main':{},'newrole':{}}}}))
            app=Flask(__name__);provider=install(SimpleNamespace(app=app,token=lambda:'fixture',MUTATION_LOCK=threading.Lock()),home)
            inventory={'available':True,'candidates':[{'runtime_id':'newrole','name':'New role'}]}
            with patch('offline.registry.Registry.discover_gateway',return_value=inventory):
                response=app.test_client().get('/api/mesh/control-center/agents?gateway_id=host',headers={'X-ProgreTech-Mesh-Local-Token':'fixture'})
            self.assertEqual(response.status_code,200);self.assertEqual(provider.bindings['host--newrole'],'newrole')
            self.assertEqual(response.json['agents'][0]['id'],'host--newrole')
            self.assertEqual(app.test_client().get('/api/mesh/control-center/agents?gateway_id=host').status_code,401)
            with patch('offline.registry.Registry.discover_gateway',return_value={'available':True,'candidates':[]}):
                app.test_client().get('/api/mesh/control-center/agents?gateway_id=host',headers={'X-ProgreTech-Mesh-Local-Token':'fixture'})
            with self.assertRaisesRegex(ValueError,'binding_required'):provider.dispatch('host--newrole','profile.get',{})

if __name__=='__main__':unittest.main()
