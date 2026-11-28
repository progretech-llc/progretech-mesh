import os
import tempfile
import unittest
from pathlib import Path

import mesh_capabilities
import mesh_capability_registry as registry
import mesh_capability_runtime as runtime


class TestPT050ImapReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "registry.json"
        registry.reset_for_tests(self.path)

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("MESH_CAPABILITY_REGISTRY_PATH", None)

    def test_registry_contains_imap_review(self):
        self.assertIn("imap-review", registry.BATCH_A_PINS)

    def test_registry_starts_imap_review_as_candidate(self):
        record = registry.get_record("imap-review")
        self.assertIsNotNone(record)
        self.assertEqual(record["state"], "CANDIDATE")
        self.assertFalse(record["activation"]["owner_approved"])

    def test_runtime_descriptor_exists(self):
        item = runtime.descriptor("imap-review")
        self.assertIsNotNone(item)
        self.assertEqual(item["id"], "imap-review")
        self.assertFalse(item["active"])

    def test_runtime_requires_activation(self):
        with self.assertRaisesRegex(PermissionError, "capability_not_active"):
            runtime.require_active("imap-review")

    def test_catalog_contains_imap_review(self):
        matches = [x for x in mesh_capabilities.CAPABILITIES if x.id == "imap-review"]
        self.assertEqual(len(matches), 1)
        item = matches[0]
        self.assertEqual(item.state, "CANDIDATE")
        self.assertIn("Rend", item.supported_agents)
        self.assertIn("Mak", item.supported_agents)
        self.assertIn("Lyra", item.supported_agents)

    def test_credentials_are_broker_bounded(self):
        item = next(x for x in mesh_capabilities.CAPABILITIES if x.id == "imap-review")
        self.assertIn("Secret Broker", item.credentials)

    def test_registration_does_not_make_runtime_active(self):
        item = runtime.descriptor("imap-review")
        self.assertFalse(item["active"])
        self.assertFalse(item["owner_approved"])


if __name__ == "__main__":
    unittest.main()
