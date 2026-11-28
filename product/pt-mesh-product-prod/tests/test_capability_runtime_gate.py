import os
import tempfile
import unittest
from pathlib import Path

import mesh_capability_registry as registry
import mesh_capability_runtime as runtime


class TestCapabilityRuntimeGate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "registry.json"
        registry.reset_for_tests(self.path)

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("MESH_CAPABILITY_REGISTRY_PATH", None)

    def _qualify(self, cid):
        registry.transition(cid, "QUALIFYING", reason="test")
        for check in (
            "representative_success","malformed_input","offline_behavior",
            "timeout_behavior","resource_bounds","rollback_test",
        ):
            registry.record_qualification_check(cid, check, True, detail="pass")
        registry.transition(cid, "QUALIFIED", reason="test qualified")

    def test_qualified_is_not_executable(self):
        self._qualify("firecrawl-anydoc")
        with self.assertRaisesRegex(PermissionError, "capability_not_active"):
            runtime.require_active("firecrawl-anydoc")

    def test_active_requires_owner_approval(self):
        self._qualify("archify")
        registry.transition("archify", "ACTIVE", reason="approved", owner_approved=True)
        item = runtime.require_active("archify")
        self.assertTrue(item["active"])
        self.assertTrue(item["owner_approved"])

    def test_runtime_descriptors_do_not_expose_secrets(self):
        for item in runtime.all_descriptors():
            blob = repr(item).lower()
            self.assertNotIn("api_key", blob)
            self.assertNotIn("token", blob)

    def test_expected_batch_a_runtime_descriptors_exist(self):
        ids = {x["id"] for x in runtime.all_descriptors()}
        expected = {"firecrawl-anydoc","mattpocock-skills","archify","workboard","webhooks","secret-broker"}
        self.assertTrue(expected.issubset(ids))


if __name__ == "__main__":
    unittest.main()
