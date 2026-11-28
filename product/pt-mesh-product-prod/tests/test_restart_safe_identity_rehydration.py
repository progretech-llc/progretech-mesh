import base64
import copy
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import main


class TestRestartSafeIdentityRehydration(unittest.TestCase):
    def setUp(self):
        self.original = copy.deepcopy(main.DEV_AGENT_REGISTRY.get("rend"))
        main.DEV_AGENT_REGISTRY.pop("rend", None)
        main.IDENTITY_CHALLENGES.clear()
        self.client = main.app.test_client()
        self.key = Ed25519PrivateKey.generate()
        self.public_key = self.key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        self.evidence = {
            "manifest": {
                "mesh_identity": {
                    "agent_id": "rend",
                    "agent_name": "Rend",
                    "public_key": self.public_key,
                }
            },
            "registry_signature": "sig",
            "registry_public_key": "registry",
        }
        self.device = patch(
            "main.validate_device_credential",
            return_value=(True, "ok", {"agent_id":"rend","device_id":"device-1"}),
        )
        self.events = patch("main.append_event")
        self.device.start()
        self.events.start()

    def tearDown(self):
        self.device.stop()
        self.events.stop()
        main.IDENTITY_CHALLENGES.clear()
        if self.original is not None:
            main.DEV_AGENT_REGISTRY["rend"] = self.original
        else:
            main.DEV_AGENT_REGISTRY.pop("rend", None)

    @staticmethod
    def verified():
        return {
            "state":"verified",
            "valid":True,
            "reason":"codeseal_registry_verified",
            "provider":"codeseal",
            "metadata":{"cryptographic_verification":True,"fail_closed":True},
        }

    def test_challenge_survives_empty_process_registry(self):
        response = self.client.post(
            "/api/agents/rend/identity/challenge",
            json={"device_credential":"credential"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertTrue(response.get_json()["ok"])

    def test_valid_identity_rehydrates_agent_after_revision(self):
        challenge = self.client.post(
            "/api/agents/rend/identity/challenge",
            json={"device_credential":"credential"},
        ).get_json()
        signature = base64.b64encode(
            self.key.sign(challenge["signing_payload"].encode())
        ).decode()
        payload = {
            "device_credential":"credential",
            "public_key":self.public_key,
            "codeseal_evidence":self.evidence,
            "challenge_id":challenge["challenge_id"],
            "signature":signature,
        }
        with patch("main.verify_runtime_agent_identity", return_value=self.verified()):
            response = self.client.post("/api/agents/rend/identity/assert", json=payload)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertIn("rend", main.DEV_AGENT_REGISTRY)
        record = main.DEV_AGENT_REGISTRY["rend"]
        self.assertEqual(record["name"], "Rend")
        self.assertTrue(record["trust_valid"])
        self.assertEqual(record["identity_device_id"], "device-1")


if __name__ == "__main__":
    unittest.main()
