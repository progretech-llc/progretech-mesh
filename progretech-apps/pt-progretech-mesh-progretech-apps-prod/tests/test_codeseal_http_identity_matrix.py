import base64
import copy
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import main


class TestCodeSealHttpIdentityMatrix(unittest.TestCase):
    def setUp(self):
        self.original = copy.deepcopy(main.DEV_AGENT_REGISTRY.get("rend"))
        self.record = copy.deepcopy(self.original) if self.original else {
            "id": "rend",
            "name": "Rend",
            "role": "ProgreTech Agent",
            "public_key": "",
            "codeseal_key": "",
            "codeseal_evidence": None,
            "trust_state": "pending",
            "trust_valid": False,
            "trust_reason": "unverified",
        }
        self.record["name"] = "Rend"
        main.DEV_AGENT_REGISTRY["rend"] = self.record
        main.IDENTITY_CHALLENGES.clear()
        self.client = main.app.test_client()

        self.key = Ed25519PrivateKey.generate()
        self.public_key = self.key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        self.evidence = {
            "manifest": {"mesh_identity": {"agent_id": "rend"}},
            "registry_signature": "sig",
            "registry_public_key": "registry-key",
        }

        self.device_patch = patch(
            "main.validate_device_credential",
            return_value=(True, "ok", {"device_id": "device-1"}),
        )
        self.event_patch = patch("main.append_event")
        self.device_patch.start()
        self.event_patch.start()

    def tearDown(self):
        self.device_patch.stop()
        self.event_patch.stop()
        main.IDENTITY_CHALLENGES.clear()
        if self.original is None:
            main.DEV_AGENT_REGISTRY.pop("rend", None)
        else:
            main.DEV_AGENT_REGISTRY["rend"] = self.original

    def challenge(self):
        response = self.client.post(
            "/api/agents/rend/identity/challenge",
            json={"device_credential": "device-token"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def signed_payload(self, challenge, evidence=None, key=None):
        signer = key or self.key
        signature = base64.b64encode(
            signer.sign(challenge["signing_payload"].encode())
        ).decode()
        return {
            "device_credential": "device-token",
            "public_key": self.public_key,
            "codeseal_evidence": self.evidence if evidence is None else evidence,
            "challenge_id": challenge["challenge_id"],
            "signature": signature,
        }

    @staticmethod
    def verified_result():
        return {
            "state": "verified",
            "valid": True,
            "reason": "codeseal_registry_verified",
            "provider": "codeseal",
            "metadata": {
                "cryptographic_verification": True,
                "fail_closed": True,
                "registry_key_known": True,
                "registry_record_match": True,
            },
        }

    @staticmethod
    def rejected_result():
        return {
            "state": "invalid",
            "valid": False,
            "reason": "CodeSeal evidence verification failed",
            "provider": "codeseal",
            "metadata": {
                "cryptographic_verification": False,
                "fail_closed": True,
            },
        }

    def test_challenge_requires_device_credential(self):
        response = self.client.post(
            "/api/agents/rend/identity/challenge", json={}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "device_credential_required")

    def test_challenge_returns_ed25519_payload(self):
        body = self.challenge()
        self.assertTrue(body["ok"])
        self.assertEqual(body["algorithm"], "Ed25519")
        self.assertIn("progretech-mesh-identity-v1|rend|device-1|", body["signing_payload"])

    def test_assert_missing_codeseal_evidence_fails_closed(self):
        challenge = self.challenge()
        payload = self.signed_payload(challenge)
        payload.pop("codeseal_evidence")
        response = self.client.post("/api/agents/rend/identity/assert", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "codeseal_identity_required")

    def test_assert_missing_proof_fails_closed(self):
        challenge = self.challenge()
        payload = self.signed_payload(challenge)
        payload.pop("signature")
        response = self.client.post("/api/agents/rend/identity/assert", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "identity_proof_required")

    def test_wrong_signature_is_rejected(self):
        challenge = self.challenge()
        wrong = Ed25519PrivateKey.generate()
        payload = self.signed_payload(challenge, key=wrong)
        response = self.client.post("/api/agents/rend/identity/assert", json=payload)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "identity_signature_invalid")

    def test_codeseal_rejection_is_403(self):
        challenge = self.challenge()
        payload = self.signed_payload(challenge)
        with patch("main.verify_runtime_agent_identity", return_value=self.rejected_result()):
            response = self.client.post("/api/agents/rend/identity/assert", json=payload)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "agent_identity_rejected")

    def test_valid_identity_assertion_succeeds(self):
        challenge = self.challenge()
        payload = self.signed_payload(challenge)
        with patch("main.verify_runtime_agent_identity", return_value=self.verified_result()):
            response = self.client.post("/api/agents/rend/identity/assert", json=payload)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["trust_valid"])
        self.assertEqual(body["identity_proof"], "ed25519-challenge")
        self.assertEqual(body["device_id"], "device-1")

    def test_challenge_replay_is_rejected(self):
        challenge = self.challenge()
        payload = self.signed_payload(challenge)
        with patch("main.verify_runtime_agent_identity", return_value=self.verified_result()):
            first = self.client.post("/api/agents/rend/identity/assert", json=payload)
            second = self.client.post("/api/agents/rend/identity/assert", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.get_json()["error"], "identity_challenge_not_found")


    def test_invalid_device_credential_is_rejected(self):
        with patch(
            "main.validate_device_credential",
            return_value=(False, "device_credential_signature_invalid", None),
        ):
            response = self.client.post(
                "/api/agents/rend/identity/challenge",
                json={"device_credential": "bad-device-token"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "device_credential_signature_invalid")

    def test_expired_device_credential_is_rejected(self):
        with patch(
            "main.validate_device_credential",
            return_value=(False, "device_credential_expired", None),
        ):
            response = self.client.post(
                "/api/agents/rend/identity/challenge",
                json={"device_credential": "expired-device-token"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "device_credential_expired")

    def test_revoked_device_credential_is_rejected(self):
        with patch(
            "main.validate_device_credential",
            return_value=(False, "device_credential_revoked", None),
        ):
            response = self.client.post(
                "/api/agents/rend/identity/challenge",
                json={"device_credential": "revoked-device-token"},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "device_credential_revoked")

    def test_evidence_mismatch_is_rejected(self):
        challenge = self.challenge()
        payload = self.signed_payload(challenge)
        rejected = self.rejected_result()
        rejected["reason"] = "registry_verification_failed"
        rejected["metadata"]["reason"] = "registry_verification_failed"
        with patch("main.verify_runtime_agent_identity", return_value=rejected):
            response = self.client.post("/api/agents/rend/identity/assert", json=payload)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "agent_identity_rejected")

    def test_revoked_codeseal_event_is_rejected(self):
        challenge = self.challenge()
        payload = self.signed_payload(challenge)
        rejected = self.rejected_result()
        rejected["reason"] = "registry_event_revoked"
        rejected["metadata"]["reason"] = "registry_event_revoked"
        with patch("main.verify_runtime_agent_identity", return_value=rejected):
            response = self.client.post("/api/agents/rend/identity/assert", json=payload)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "agent_identity_rejected")


if __name__ == "__main__":
    unittest.main()
