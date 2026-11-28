import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "static" / "js" / "app.js").read_text()
CSS = (ROOT / "static" / "css" / "app.css").read_text()
HTML = (ROOT / "templates" / "index.html").read_text()
PLUGIN = (ROOT / "openclaw-plugin-progretech-mesh" / "index.js").read_text()
MAIN = (ROOT / "main.py").read_text()


class TestTerminalFileExchange(unittest.TestCase):
    def test_terminal_stream_replaces_truncated_event_rows(self):
        self.assertIn("Mesh terminal", HTML)
        self.assertIn("mesh-terminal-stream", HTML)
        self.assertIn("mesh-line", CSS)
        self.assertIn("white-space:pre-wrap", CSS)
        self.assertIn("overflow-wrap:anywhere", CSS)
        self.assertIn("terminalDirection", APP)
        self.assertIn('MeshRuntime.terminalDirection(message)', APP)
        self.assertIn("label:'OUT'", (ROOT/'static/js/runtime-client.js').read_text())

    def test_terminal_payload_details_are_expandable(self):
        self.assertIn("safeDetailPayload", APP)
        self.assertIn("<details><summary>details</summary>", APP)
        self.assertIn("JSON.stringify(detail, null, 2)", APP)

    def test_browser_attachment_path_is_real_gateway_transfer(self):
        self.assertIn('/files/send', APP)
        self.assertIn('type": "file_transfer_start"', MAIN)
        self.assertIn('type": "file_transfer_chunk"', MAIN)
        self.assertIn('type": "file_transfer_end"', MAIN)
        self.assertIn('file_transfer_start', PLUGIN)
        self.assertIn('file_transfer_chunk', PLUGIN)
        self.assertIn('file_transfer_end', PLUGIN)
        self.assertIn('FILE_INBOX_DIR', PLUGIN)
        self.assertIn('file_transfer_sha256_mismatch', PLUGIN)

    def test_agent_file_offer_can_be_downloaded_inline(self):
        self.assertIn('offerBufferToMesh', PLUGIN)
        self.assertIn('demo_file_offer_request', PLUGIN)
        self.assertIn('file_offer_start', PLUGIN)
        self.assertIn('file_offer_chunk', PLUGIN)
        self.assertIn('file_offer_end', PLUGIN)
        self.assertIn('data-terminal-download', APP)
        self.assertIn('/api/files/${encodeURIComponent(file.id)}/download', APP)

    def test_file_transfer_does_not_enable_remote_shell(self):
        self.assertIn('shell=disabled', PLUGIN)
        self.assertNotIn('execSync(', PLUGIN)
        self.assertNotIn('spawnSync(', PLUGIN)


if __name__ == '__main__':
    unittest.main()
