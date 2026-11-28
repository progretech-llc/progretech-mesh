import os
import unittest
from unittest.mock import patch
from flask import Flask
import mesh_firebase_auth as authmod

class TestFirebaseEmailLinkAuth(unittest.TestCase):
    def setUp(self):
        self.saved = dict(os.environ)
        for key in (
            "MESH_AUTH_MODE","MESH_FIREBASE_API_KEY","MESH_FIREBASE_AUTH_DOMAIN",
            "MESH_FIREBASE_PROJECT_ID","MESH_FIREBASE_APP_ID","MESH_FIREBASE_AUTH_READY",
        ):
            os.environ.pop(key, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def app(self):
        app = Flask(__name__)
        app.secret_key = "test-secret"
        authmod.register_firebase_auth_routes(app)
        return app

    def configure(self):
        os.environ["MESH_AUTH_MODE"] = "firebase-email-link"
        os.environ["MESH_FIREBASE_API_KEY"] = "public-web-api-key"
        os.environ["MESH_FIREBASE_AUTH_DOMAIN"] = "mesh.example.firebaseapp.com"
        os.environ["MESH_FIREBASE_PROJECT_ID"] = "mesh-example"
        os.environ["MESH_FIREBASE_APP_ID"] = "1:123:web:abc"

    def test_local_mode_does_not_expose_firebase_config(self):
        self.assertEqual(self.app().test_client().get("/api/auth/firebase/config").status_code, 404)

    def test_production_config_exposes_public_values(self):
        self.configure()
        body = self.app().test_client().get("/api/auth/firebase/config").get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["config"]["projectId"], "mesh-example")

    def test_verified_email_creates_server_session(self):
        self.configure()
        decoded = {"uid":"u1","sub":"u1","email":"owner@example.com","email_verified":True}
        client = self.app().test_client()
        with patch.object(authmod, "verify_firebase_id_token", return_value=decoded):
            response = client.post("/api/auth/firebase/session", json={"idToken":"token"})
        self.assertEqual(response.status_code, 200)
        with client.session_transaction() as sess:
            self.assertEqual(sess["mesh_user"]["auth_source"], "firebase-email-link")

    def test_missing_token_rejected(self):
        self.configure()
        self.assertEqual(self.app().test_client().post("/api/auth/firebase/session", json={}).status_code, 400)

if __name__ == "__main__":
    unittest.main()
