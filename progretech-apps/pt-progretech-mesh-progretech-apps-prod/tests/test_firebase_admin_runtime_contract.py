import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "mesh_firebase_auth.py"

class TestFirebaseAdminRuntimeContract(unittest.TestCase):
    def setUp(self):
        self.text = AUTH.read_text(encoding="utf-8")

    def test_revocation_check_remains_enabled(self):
        self.assertIn("verify_id_token(id_token, check_revoked=True)", self.text)

    def test_backend_logs_verification_failure(self):
        self.assertIn("firebase_token_verification_failed", self.text)
        self.assertIn("app.logger.exception", self.text)

    def test_raw_exception_not_returned_to_client(self):
        self.assertNotIn("error=str(exc)", self.text)

if __name__ == "__main__":
    unittest.main()
