import json
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class TestRoutingPolicyContract(unittest.TestCase):
    def setUp(self):
        self.server=(ROOT/"main.py").read_text(encoding="utf-8")
        self.browser=(ROOT/"static/js/app.js").read_text(encoding="utf-8")
        self.plugin=(ROOT/"openclaw-plugin-progretech-mesh/index.js").read_text(encoding="utf-8")
        self.template=(ROOT/"templates/index.html").read_text(encoding="utf-8")
        self.pkg=json.loads((ROOT/"openclaw-plugin-progretech-mesh/package.json").read_text())

    def test_owner_policies(self):
        for value in ("direct_preferred","direct_only","relay_allowed"):
            self.assertIn(value,self.server)
            self.assertIn(value,self.browser)
            self.assertIn(value,self.template)

    def test_stun_turn_config(self):
        self.assertIn("MESH_STUN_URLS",self.server)
        self.assertIn("MESH_TURN_URLS",self.server)
        self.assertIn("/api/transport/config",self.server)

    def test_browser_uses_server_ice_config(self):
        self.assertIn("currentIceServers",self.browser)
        self.assertIn("iceServers:currentIceServers",self.browser)
        self.assertIn('route_policy:',self.browser); self.assertIn('currentRoutePolicy',self.browser)

    def test_agent_filters_turn_for_direct_only(self):
        self.assertIn('routePolicy === "direct_only"',self.plugin)
        self.assertIn('startsWith("turn:")',self.plugin)
        self.assertIn('startsWith("turns:")',self.plugin)

    def test_version(self):
        self.assertEqual(self.pkg["version"],"0.10.4-roster-relay.1")

    def test_no_frontend_internal_labels(self):
        joined="\n".join(p.read_text(errors="ignore") for p in list((ROOT/"templates").glob("*.html"))+list((ROOT/"static/js").glob("*.js")))
        self.assertIsNone(re.search(r"\bPhase\s+\d+\b|\bRev(?:ision)?\s+\d+\b",joined,re.I))

if __name__=="__main__": unittest.main()
