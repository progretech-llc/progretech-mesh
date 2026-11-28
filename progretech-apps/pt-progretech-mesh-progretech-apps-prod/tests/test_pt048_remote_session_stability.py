import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class TestPT048RemoteSessionStability(unittest.TestCase):
    def setUp(self):
        self.js=(ROOT/"static/js/app.js").read_text()
        self.cloudbuild=(ROOT/"cloudbuild.yaml").read_text()

    def test_ide_copy_available_when_gateway_offline(self):
        self.assertIn('<button data-ide-access="${escapeHtml(agent.id)}">Copy API relay setup</button>', self.js)
        self.assertNotIn('data-ide-access="${agent.id}" ${agent.transport !== "connected" ? "disabled" : ""}', self.js)

    def test_ide_copy_uses_compatible_clipboard_helper(self):
        self.assertIn("const copied = await copyTextCompatible(setup);", self.js)
        self.assertIn("Copy this IDE relay setup manually", self.js)

    def test_monitor_uses_bounded_backoff(self):
        self.assertIn("function monitorReconnectDelay(attempt)", self.js)
        self.assertIn("[2500, 5000, 10000, 20000, 30000]", self.js)
        self.assertIn('["authentication_required","agent_not_found"].includes(reason)', self.js)

    def test_cloud_run_keeps_single_process_routing_contract(self):
        self.assertIn("--max-instances=1", self.cloudbuild)
        self.assertIn("--timeout=3600", self.cloudbuild)

if __name__=="__main__":
    unittest.main()
