import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestReconnectScheduler(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "openclaw-plugin-progretech-mesh/index.js").read_text()

    def test_reconnect_has_bounded_backoff_and_real_attempt_timestamps(self):
        self.assertIn("RECONNECT_BACKOFF_MS = [2000, 5000, 10000, 20000, 30000]", self.source)
        self.assertIn("next_reconnect_attempt_at", self.source)
        self.assertIn("last_reconnect_attempt_at", self.source)
        self.assertIn('reconnect_state: "attempting"', self.source)

    def test_failed_connect_cannot_stall_waiting_for_close_event(self):
        self.assertIn("RECONNECT_CONNECT_TIMEOUT_MS", self.source)
        self.assertIn('queueRetry("connect_timeout")', self.source)
        self.assertIn('queueRetry("websocket_error_before_open")', self.source)
        self.assertIn("Some WebSocket implementations do not reliably emit close", self.source)

    def test_reconnect_timer_is_not_unrefed(self):
        schedule = self.source[self.source.index("function scheduleReconnect"):self.source.index("async function ensureMeshConnection")]
        self.assertNotIn(".unref", schedule)

    def test_success_resets_attempt_counter(self):
        self.assertIn("meshReconnectAttempt = 0", self.source)
        self.assertIn('reconnect_state: "connected"', self.source)

    def test_auth_rejection_still_fails_closed(self):
        self.assertIn("isAuthenticationClose(event?.code)", self.source)
        self.assertIn("Mesh authentication rejected; re-enrollment required", self.source)

if __name__ == "__main__":
    unittest.main()
