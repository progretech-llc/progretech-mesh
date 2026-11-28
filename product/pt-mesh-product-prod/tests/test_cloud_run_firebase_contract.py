import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestCloudRunFirebaseContract(unittest.TestCase):
    def setUp(self):
        self.deploy = (ROOT / "scripts" / "deploy-cloud-run.sh").read_text(encoding="utf-8")
        self.verify = (ROOT / "scripts" / "verify-cloud-run.sh").read_text(encoding="utf-8")

    def test_deploy_uses_firebase_email_link(self):
        self.assertIn("MESH_AUTH_MODE=progretech-shared", self.deploy)
        self.assertIn("MESH_FIREBASE_API_KEY", self.deploy)
        self.assertIn("MESH_FIREBASE_AUTH_READY", self.deploy)
        self.assertNotIn("MESH_OIDC_READY", self.deploy)

    def test_local_app_remains_publicly_reachable_but_app_authenticated(self):
        self.assertIn("--allow-unauthenticated", self.deploy)
        self.assertIn("DEV_AUTH_ENABLED=0", self.deploy)

    def test_verify_checks_email_link_surface(self):
        self.assertIn("Sign in with ProgreTech", self.verify)
        self.assertIn("/auth/progretech/login", self.verify)

    def test_single_instance_constraint_preserved(self):
        self.assertIn("--max-instances 1", self.deploy)
        self.assertIn("--concurrency 80", self.deploy)

if __name__ == "__main__":
    unittest.main()
