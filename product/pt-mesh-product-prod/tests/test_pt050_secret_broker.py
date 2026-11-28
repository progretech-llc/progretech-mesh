import os, tempfile, unittest
from pathlib import Path

import mesh_capability_registry as registry
import mesh_capability_runtime as runtime
import mesh_capabilities

class TestPT050SecretBroker(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"registry.json"
        registry.reset_for_tests(self.path)

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("MESH_CAPABILITY_REGISTRY_PATH",None)

    def test_catalog_registry_runtime_present(self):
        self.assertIn("secret-broker",{c.id for c in mesh_capabilities.CAPABILITIES})
        self.assertIsNotNone(registry.get_record("secret-broker"))
        d=runtime.descriptor("secret-broker")
        self.assertEqual(d["network"],"none")
        self.assertEqual(d["egress"],"none")

    def test_runtime_descriptor_does_not_expose_secret_get(self):
        d=runtime.descriptor("secret-broker")
        blob=repr(d).lower()
        self.assertNotIn(" get ",blob)
        self.assertIn("selftest",blob)

    def test_activation_requires_owner(self):
        registry.transition("secret-broker","QUALIFYING",reason="test")
        for c in ("representative_success","malformed_input","offline_behavior","timeout_behavior","resource_bounds","rollback_test"):
            registry.record_qualification_check("secret-broker",c,True,detail="pass")
        registry.transition("secret-broker","QUALIFIED",reason="qualified")
        with self.assertRaisesRegex(ValueError,"activation_requires_owner_approval"):
            registry.transition("secret-broker","ACTIVE",reason="no owner")
        x=registry.transition("secret-broker","ACTIVE",reason="owner",owner_approved=True)
        self.assertEqual(x["state"],"ACTIVE")

if __name__=="__main__":
    unittest.main()
