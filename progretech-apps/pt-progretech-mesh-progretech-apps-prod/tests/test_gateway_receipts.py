import copy
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import main
from mesh_gateway_receipts import issue_receipt, restore_receipt

def key():
    return Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.host = {'id':'host','name':'Host','owner_id':'owner','public_key':key(),'trust_state':'verified'}
        self.role = {'id':'host--coder','name':'Mak','role':'Builder','owner_id':'owner','public_key':key(),
                     'codeseal_evidence':{},'fingerprint':'fixture','control_center_gateway':'host',
                     'gateway_candidate_id':'host--coder','gateway_enrollment':True,'runtime':'OpenClaw role','enrolled_at':'fixture'}
        self.receipt = issue_receipt(self.role, self.host, b'server-key')
        self.verifier = lambda *args: {'provider':'codeseal','valid':True,'reason':'fixture'}

    def restore(self, **changes):
        args=dict(receipt=self.receipt,gateway_id='host',host=self.host,secret=b'server-key',candidates={'host--coder'},verify=self.verifier)
        args.update(changes);return restore_receipt(**args)

    def test_signed_enrollment_restores_exact_identity(self):
        restored=self.restore()
        self.assertEqual(restored['public_key'],self.role['public_key'])
        self.assertEqual(restored['owner_id'],'owner');self.assertTrue(restored['gateway_enrollment'])

    def test_receipt_cannot_change_owner_gateway_key_or_runtime_membership(self):
        for change in ({'receipt':self.receipt[:-1]+'x'}, {'secret':b'other'},
                       {'host':{**self.host,'owner_id':'other'}}, {'gateway_id':'other'},
                       {'host':{**self.host,'public_key':key()}}, {'candidates':set()}):
            with self.subTest(change=tuple(change)):
                with self.assertRaises(ValueError):self.restore(**change)

    def test_revoked_or_unverifiable_seal_cannot_restore(self):
        with self.assertRaisesRegex(ValueError,'verification_failed'):
            self.restore(verify=lambda *a:{'provider':'codeseal','valid':False})

    def test_existing_record_is_not_overwritten_or_reverified(self):
        with patch.object(self,'verifier') as verify:
            with self.assertRaisesRegex(ValueError,'already_present'):
                self.restore(existing={'host--coder'},verify=verify)
            verify.assert_not_called()

    def test_restart_restores_role_only_with_owner_receipt(self):
        registry=copy.deepcopy(main.DEV_AGENT_REGISTRY)
        try:
            main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY['host']=self.host
            payload={'agents':[{'id':'host--coder','name':'Mak'}],'enrollment_restore_version':1}
            main.update_from_gateway('host',{'type':'control_center_roster','payload':payload})
            self.assertTrue(main.DEV_AGENT_REGISTRY['host--coder']['gateway_linked'])
            self.assertNotIn('public_key',main.DEV_AGENT_REGISTRY['host--coder'])
            receipt=issue_receipt(self.role,self.host,main.device_credential_secret())
            with patch('main.verify_runtime_agent_identity',side_effect=self.verifier):
                main.update_from_gateway('host',{'type':'control_center_roster','payload':{**payload,'enrollment_receipts':[receipt]}})
            restored=main.DEV_AGENT_REGISTRY['host--coder']
            self.assertEqual(restored['public_key'],self.role['public_key']);self.assertEqual(restored['transport'],'connected')
            self.assertEqual(restored['owner_id'],'owner')
        finally:
            main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY.update(registry)

    def test_repeated_cloud_restarts_restore_without_reenrollment(self):
        previous=main.DEV_AGENT_REGISTRY.copy()
        try:
            receipt=issue_receipt(self.role,self.host,main.device_credential_secret())
            payload={'agents':[{'id':'host--coder','name':'Mak'}],
                     'enrollment_restore_version':1,'enrollment_receipts':[receipt]}
            for restart in range(3):
                main.DEV_AGENT_REGISTRY.clear()
                main.DEV_AGENT_REGISTRY['host']=copy.deepcopy(self.host)
                with patch('main.verify_runtime_agent_identity',side_effect=self.verifier) as verify:
                    main.update_from_gateway('host',{'type':'control_center_roster','payload':payload})
                    main.update_from_gateway('host',{'type':'control_center_roster','payload':payload})
                self.assertEqual(verify.call_count,1)
                restored=main.DEV_AGENT_REGISTRY['host--coder']
                self.assertEqual(restored['public_key'],self.role['public_key'])
                self.assertEqual(restored['owner_id'],'owner')
        finally:
            main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY.update(previous)

    def test_bad_receipt_does_not_prevent_another_role_restore(self):
        previous=main.DEV_AGENT_REGISTRY.copy()
        try:
            main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY['host']=self.host
            receipt=issue_receipt(self.role,self.host,main.device_credential_secret())
            payload={'agents':[{'id':'host--coder','name':'Mak'}],
                     'enrollment_restore_version':1,'enrollment_receipts':['invalid',receipt]}
            with patch('main.verify_runtime_agent_identity',side_effect=self.verifier):
                main.update_from_gateway('host',{'type':'control_center_roster','payload':payload})
            self.assertIn('host--coder',main.DEV_AGENT_REGISTRY)
        finally:
            main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY.update(previous)

    def test_production_refuses_adapter_without_durable_receipts(self):
        registry=main.DEV_AGENT_REGISTRY.copy();gateways=main.GATEWAY_SOCKETS.copy()
        try:
            self.host.update(identified_agents=[{'id':'host--coder','name':'Mak'}])
            main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY['host']=self.host
            main.GATEWAY_SOCKETS['host']=object();client=main.app.test_client()
            with client.session_transaction() as session:session['mesh_user']={'id':'owner'}
            payload={'name':'Mak','agent_id':'host--coder','gateway_id':'host','gateway_candidate_id':'host--coder',
                     'public_key':self.role['public_key'],'codeseal_evidence':{'manifest':{'mesh_identity':{'agent_id':'host--coder'}}}}
            with patch.dict('os.environ',{'APP_ENV':'production'}):
                response=client.post('/api/agents/enroll',json=payload,headers={'Origin':'http://localhost'})
            self.assertEqual(response.status_code,409)
            self.assertEqual(response.json['error'],'gateway_enrollment_adapter_update_required')
            self.assertNotIn('host--coder',main.DEV_AGENT_REGISTRY)
        finally:
            main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY.update(registry)
            main.GATEWAY_SOCKETS.clear();main.GATEWAY_SOCKETS.update(gateways)

    def test_enrollment_requires_gateway_storage_acknowledgement(self):
        registry=main.DEV_AGENT_REGISTRY.copy();gateways=main.GATEWAY_SOCKETS.copy()
        try:
            self.host.update(gateway_enrollment_restore_version=1, identified_agents=[{'id':'host--coder','name':'Mak'}])
            main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY['host']=self.host
            main.GATEWAY_SOCKETS['host']=object()
            client=main.app.test_client()
            with client.session_transaction() as session:session['mesh_user']={'id':'owner'}
            payload={'name':'Mak','agent_id':'host--coder','gateway_id':'host','gateway_candidate_id':'host--coder',
                     'public_key':self.role['public_key'],'codeseal_evidence':{'manifest':{'mesh_identity':{'agent_id':'host--coder'}}}}
            verdict={'provider':'codeseal','valid':True,'state':'verified','reason':'fixture'}
            with patch('main.verify_runtime_agent_identity',return_value=verdict),patch('main.control_relay.dispatch',return_value=({'ok':False},502)):
                response=client.post('/api/agents/enroll',json=payload,headers={'Origin':'http://localhost'})
                self.assertEqual(response.status_code,502);self.assertNotIn('host--coder',main.DEV_AGENT_REGISTRY)
            with patch('main.verify_runtime_agent_identity',return_value=verdict),patch('main.control_relay.dispatch',return_value=({'ok':True,'result':{'stored':True}},200)) as save:
                response=client.post('/api/agents/enroll',json=payload,headers={'Origin':'http://localhost'})
                self.assertEqual(response.status_code,201)
                self.assertEqual(save.call_args.args[:2],('host--coder','identity.enrollment.save'))
                restored=restore_receipt(save.call_args.args[2]['receipt'],'host',self.host,main.device_credential_secret(),{'host--coder'},self.verifier)
                self.assertEqual(restored['public_key'].strip(),self.role['public_key'].strip())
        finally:
            main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY.update(registry)
            main.GATEWAY_SOCKETS.clear();main.GATEWAY_SOCKETS.update(gateways)

class RoleStatusTests(unittest.TestCase):
    def test_role_status_follows_authenticated_host_and_roster(self):
        registry=main.DEV_AGENT_REGISTRY.copy();gateways=main.GATEWAY_SOCKETS.copy()
        try:
            host={'id':'host','name':'Host','owner_id':'owner','trust_state':'verified','identified_agents':[{'id':'host--coder'}]}
            role={'id':'host--coder','owner_id':'owner','trust_state':'verified','gateway_enrollment':True,'control_center_gateway':'host','state':'idle','task':'Awaiting gateway','phase':'Enrollment complete · connecting agent'}
            main.DEV_AGENT_REGISTRY.update({'host':host,'host--coder':role});main.GATEWAY_SOCKETS['host']=object()
            live=main.public_agent(role)
            self.assertEqual(live['task'],'Gateway live');self.assertIn('Idle',live['phase']);self.assertEqual(live['transport'],'connected')
            main.GATEWAY_SOCKETS.pop('host')
            offline=main.public_agent(role);self.assertEqual(offline['task'],'Gateway offline');self.assertEqual(offline['transport'],'not-connected')
        finally:
            main.DEV_AGENT_REGISTRY.clear();main.DEV_AGENT_REGISTRY.update(registry)
            main.GATEWAY_SOCKETS.clear();main.GATEWAY_SOCKETS.update(gateways)
