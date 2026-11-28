import os, tempfile, unittest
from pathlib import Path
import mesh_capability_registry as registry

class TestCapabilityQuarantine(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"registry.json"
        registry.reset_for_tests(self.path)

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("MESH_CAPABILITY_REGISTRY_PATH",None)

    def test_batch_a_is_pinned(self):
        records={r["id"]:r for r in registry.list_records()}
        self.assertEqual(records["mattpocock-skills"]["pin"]["version"],"1.2.3")
        self.assertEqual(records["firecrawl-anydoc"]["pin"]["version"],"0.2.4")
        self.assertEqual(records["archify"]["pin"]["commit"],"440e16d639ed94e55377fe66ef2350c171bdb971")

    def test_candidate_can_enter_qualification(self):
        self.assertEqual(registry.transition("firecrawl-anydoc","QUALIFYING",reason="start")["state"],"QUALIFYING")

    def test_qualified_requires_complete_evidence(self):
        registry.transition("firecrawl-anydoc","QUALIFYING",reason="start")
        with self.assertRaisesRegex(ValueError,"qualification_evidence_incomplete"):
            registry.transition("firecrawl-anydoc","QUALIFIED",reason="premature")

    def test_active_requires_owner_approval(self):
        registry.transition("firecrawl-anydoc","QUALIFYING",reason="start")
        for check in ("representative_success","malformed_input","offline_behavior","timeout_behavior","resource_bounds","rollback_test"):
            registry.record_qualification_check("firecrawl-anydoc",check,True,detail=check+" pass")
        registry.transition("firecrawl-anydoc","QUALIFIED",reason="all checks pass")
        with self.assertRaisesRegex(ValueError,"activation_requires_owner_approval"):
            registry.transition("firecrawl-anydoc","ACTIVE",reason="activate")
        active=registry.transition("firecrawl-anydoc","ACTIVE",reason="owner approved",owner_approved=True)
        self.assertTrue(active["activation"]["owner_approved"])

    def test_hosted_ocr_is_explicit_egress(self):
        self.assertIn("hosted OCR",registry.get_record("firecrawl-anydoc")["pin"]["egress_policy"])

if __name__=="__main__":
    unittest.main()
