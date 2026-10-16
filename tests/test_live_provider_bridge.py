import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestLiveProviderBridge(unittest.TestCase):
    def setUp(self):
        self.main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.plugin = (ROOT / "openclaw-plugin-progretech-mesh" / "index.js").read_text(encoding="utf-8")
        self.cap_html = (ROOT / "templates" / "capabilities.html").read_text(encoding="utf-8")
        self.cap_js = (ROOT / "static" / "js" / "capabilities.js").read_text(encoding="utf-8")

    def test_plugin_reads_local_control_center_only(self):
        self.assertIn("http://127.0.0.1:8787", self.plugin)
        self.assertIn("/api/mesh/provider", self.plugin)
        self.assertIn("/api/mesh/provider/health", self.plugin)
        self.assertIn("capabilityProviderSnapshot", self.plugin)

    def test_heartbeat_carries_provider_snapshot(self):
        self.assertIn("capability_provider: capabilityProviderSnapshot", self.plugin)
        self.assertIn('capability_provider=payload.get("capability_provider")', self.main)

    def test_mesh_exposes_provider_route(self):
        self.assertIn('@app.get("/api/agents/<agent_id>/capability-provider")', self.main)
        self.assertIn("capability_provider_not_reported", self.main)

    def test_ui_has_live_provider_surface(self):
        self.assertIn('id="liveProviderPanel"', self.cap_html)
        self.assertIn("loadLiveProvider", self.cap_js)

    def test_adapter_version_bumped(self):
        self.assertIn('OPENCLAW_PLUGIN_PACKAGE_VERSION = "0.10.4-roster-relay.3"', self.main)
        self.assertIn('"version": "0.10.4-roster-relay.3"', (ROOT / "openclaw-plugin-progretech-mesh" / "package.json").read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
