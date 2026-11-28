import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mesh_capabilities


class TestCapabilityRegistryContract(unittest.TestCase):
    def test_required_lifecycle_states(self):
        required = {
            "DISCOVERED","QUARANTINED","INSPECTED","CANDIDATE","QUALIFYING",
            "QUALIFIED","ACTIVE","REJECTED","SUPERSEDED","ROLLED_BACK"
        }
        self.assertEqual(set(mesh_capabilities.LIFECYCLE), required)

    def test_named_pt044_candidates_present(self):
        ids = {c.id for c in mesh_capabilities.CAPABILITIES}
        for expected in {
            "rend-host-control","mattpocock-skills","firecrawl-anydoc","archify",
            "munder-difflin","autonomous-os","odysseus","openmontage"
        }:
            self.assertIn(expected, ids)

    def test_no_candidate_is_active_by_installation(self):
        self.assertFalse(any(c.state == "ACTIVE" for c in mesh_capabilities.CAPABILITIES))

    def test_every_record_has_authority_and_egress_classification(self):
        for cap in mesh_capabilities.CAPABILITIES:
            self.assertTrue(cap.authority_boundary.strip(), cap.id)
            self.assertTrue(cap.data_egress.strip(), cap.id)
            self.assertTrue(cap.network.strip(), cap.id)

    def test_route_registration_symbol_exists(self):
        self.assertTrue(callable(mesh_capabilities.register_capability_routes))

    def test_index_contains_sync_update_entrypoint(self):
        source = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/sync-update"', source)


if __name__ == "__main__":
    unittest.main()
