import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "static" / "js" / "firebase-email-link.js"

class TestFirebaseClientInitContract(unittest.TestCase):
    def setUp(self):
        self.text = JS.read_text(encoding="utf-8")

    def test_uses_initialize_auth_with_browser_persistence(self):
        self.assertIn("initializeAuth", self.text)
        self.assertIn("browserLocalPersistence", self.text)
        self.assertNotIn("getAuth(", self.text)

    def test_does_not_configure_redirect_resolver(self):
        # Check executable configuration, not comments/documentation text.
        self.assertNotIn("popupRedirectResolver:", self.text)
        self.assertNotIn("browserPopupRedirectResolver", self.text)

    def test_exposes_actionable_client_errors(self):
        self.assertIn("unauthorized-domain", self.text)
        self.assertIn("operation-not-allowed", self.text)
        self.assertIn("invalid-api-key", self.text)

    def test_ready_message_only_after_auth_init(self):
        init = self.text.index("const auth = initializeAuth")
        ready = self.text.index('Passwordless cloud sign-in is ready.')
        self.assertLess(init, ready)

if __name__ == "__main__":
    unittest.main()
