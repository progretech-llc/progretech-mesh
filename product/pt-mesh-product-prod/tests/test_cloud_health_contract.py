import unittest
from flask import Flask
from mesh_cloud_health import register_cloud_health_routes

class TestCloudHealthContract(unittest.TestCase):
    def test_platform_health_is_public_and_stable(self):
        app = Flask(__name__)
        register_cloud_health_routes(app)
        client = app.test_client()
        response = client.get("/api/platform/health")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["service"], "progretech-mesh")

    def test_platform_startup_is_public_and_stable(self):
        app = Flask(__name__)
        register_cloud_health_routes(app)
        response = app.test_client().get("/api/platform/startup")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["started"])

if __name__ == "__main__":
    unittest.main()
