
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestLifecyclePolicy(unittest.TestCase):
    def test_catalog_lifecycle_guarantees(self):
        data=json.loads((ROOT/"distribution"/"agent-adapter-catalog-v1.json").read_text())
        a=next(x for x in data["adapters"] if x["id"]=="openclaw")
        life=a["lifecycle"]
        self.assertTrue(life["idempotent_same_version"])
        self.assertTrue(life["credential_expiry_stops_mesh_only"])
        self.assertTrue(life["server_revocation_stops_mesh_only"])
        self.assertEqual(life["downgrade_default"], "reject")

    def test_helper_has_downgrade_guard(self):
        s=(ROOT/"distribution"/"openclaw-self-bootstrap-v1.sh").read_text()
        self.assertIn("refusing Mesh adapter downgrade", s)
        self.assertIn("already installed; skipping reinstall", s)

    def test_plugin_revocation_does_not_stop_openclaw(self):
        s=(ROOT/"openclaw-plugin-progretech-mesh"/"index.js").read_text()
        self.assertIn("markRevoked", s)
        self.assertNotIn("gateway restart", s)
        self.assertNotIn("gateway stop", s)

if __name__=="__main__":
    unittest.main()
