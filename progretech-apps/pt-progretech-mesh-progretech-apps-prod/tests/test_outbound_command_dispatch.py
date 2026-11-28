import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = (ROOT / "openclaw-plugin-progretech-mesh" / "index.js").read_text()
MAIN = (ROOT / "main.py").read_text()
APP = (ROOT / "static" / "js" / "app.js").read_text()


class TestOutboundCommandDispatch(unittest.TestCase):
    def test_plugin_handles_mesh_conversation_requests(self):
        self.assertIn('msg?.type === "message_request"', PLUGIN)
        self.assertIn('runMeshConversation(api', PLUGIN)
        self.assertIn('type: "message_response"', PLUGIN)
        self.assertIn('meshConversationBody(payload, meshIdentity?.agent_id, "mesh-websocket")', PLUGIN)

    def test_plugin_handles_approved_safe_actions(self):
        self.assertIn('msg?.type === "approved_action"', PLUGIN)
        self.assertIn('request_terminal_snapshot', PLUGIN)
        self.assertIn('request_task_snapshot', PLUGIN)
        self.assertIn('request_status', PLUGIN)
        self.assertIn('shell=disabled', PLUGIN)

    def test_delivery_acknowledgement_is_end_to_end(self):
        self.assertIn('type: "command_ack"', PLUGIN)
        self.assertIn('elif msg_type == "command_ack":', MAIN)
        self.assertIn('action["status"] = "acknowledged"', MAIN)
        self.assertIn('action["status"] = "dispatched"', MAIN)
        self.assertIn('data.type === "command_ack"', APP)

    def test_mesh_conversation_remains_independent(self):
        self.assertIn('const sessionKey = `agent:${agentId}:mesh:${sessionId}`', PLUGIN)
        self.assertNotIn('telegram', PLUGIN[PLUGIN.index('async function handleGatewayCommand'):PLUGIN.index('function eventPath')].lower())


if __name__ == '__main__':
    unittest.main()
