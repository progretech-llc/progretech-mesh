import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestAdapterCodeSealReconnectContract(unittest.TestCase):
    def setUp(self):
        self.plugin = (
            ROOT / "openclaw-plugin-progretech-mesh" / "index.js"
        ).read_text(encoding="utf-8")

    def test_adapter_has_identity_material_contract(self):
        self.assertIn("identityMaterialPaths", self.plugin)
        self.assertIn("PROGRETECH_MESH_IDENTITY_DIR", self.plugin)
        self.assertIn("codeseal_evidence.json", self.plugin)
        self.assertIn("identity_private.pem", self.plugin)
        self.assertIn("identity_public.pem", self.plugin)

    def test_adapter_asserts_before_websocket_reconnect(self):
        assertion = self.plugin.index("await assertCodeSealIdentity(record)")
        websocket = self.plugin.index("new WebSocket(url)")
        self.assertLess(assertion, websocket)

    def test_adapter_signs_ed25519_challenge(self):
        self.assertIn("crypto.sign(null", self.plugin)
        self.assertIn("/identity/challenge", self.plugin)
        self.assertIn("/identity/assert", self.plugin)

    def test_production_mesh_missing_identity_material_fails_closed(self):
        self.assertIn('hostname === "mesh.progretech.com"', self.plugin)
        self.assertIn("codeseal_identity_material_missing", self.plugin)


if __name__ == "__main__":
    unittest.main()
