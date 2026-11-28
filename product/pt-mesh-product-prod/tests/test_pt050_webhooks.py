import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

import mesh_capability_registry as registry
import mesh_capability_runtime as runtime
import mesh_capabilities

ROOT=Path(__file__).resolve().parents[1]

class TestPT050Webhooks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.registry_path=Path(self.temp.name)/"registry.json"
        registry.reset_for_tests(self.registry_path)

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("MESH_CAPABILITY_REGISTRY_PATH",None)

    def test_catalog_registry_runtime_present(self):
        self.assertIn("webhooks",{c.id for c in mesh_capabilities.CAPABILITIES})
        self.assertIsNotNone(registry.get_record("webhooks"))
        d=runtime.descriptor("webhooks")
        self.assertEqual(d["network"],"none")
        self.assertEqual(d["egress"],"none")

    def test_qualification_then_activation_requires_owner(self):
        registry.transition("webhooks","QUALIFYING",reason="test")
        for c in ("representative_success","malformed_input","offline_behavior","timeout_behavior","resource_bounds","rollback_test"):
            registry.record_qualification_check("webhooks",c,True,detail="pass")
        registry.transition("webhooks","QUALIFIED",reason="qualified")
        with self.assertRaisesRegex(ValueError,"activation_requires_owner_approval"):
            registry.transition("webhooks","ACTIVE",reason="no owner")
        x=registry.transition("webhooks","ACTIVE",reason="owner approved",owner_approved=True)
        self.assertEqual(x["state"],"ACTIVE")

    def test_invalid_signature_fails(self):
        env=os.environ.copy()
        env["MESH_WEBHOOK_STATE_ROOT"]=str(Path(self.temp.name)/"webhooks")
        tool=ROOT/"scripts/webhooks.py"
        p=subprocess.run([sys.executable,str(tool),"ingest","--event-id","evt-1","--payload",'{"ok":true}',"--signature","00"],env=env,capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("signature_invalid",p.stderr)

    def test_duplicate_event_fails(self):
        env=os.environ.copy()
        env["MESH_WEBHOOK_STATE_ROOT"]=str(Path(self.temp.name)/"webhooks")
        tool=ROOT/"scripts/webhooks.py"
        sig=subprocess.run([sys.executable,str(tool),"sign","--event-id","evt-1","--payload",'{"ok":true}'],env=env,capture_output=True,text=True,check=True).stdout.strip()
        cmd=[sys.executable,str(tool),"ingest","--event-id","evt-1","--payload",'{"ok":true}',"--signature",sig]
        self.assertEqual(subprocess.run(cmd,env=env,capture_output=True,text=True).returncode,0)
        p=subprocess.run(cmd,env=env,capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("duplicate_event_id",p.stderr)

if __name__=="__main__":
    unittest.main()
