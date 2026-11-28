import json
import os
import unittest
from unittest.mock import patch

from gateway.identity.codeseal import CodeSealIdentityVerifier


class _Response:
    status = 200
    def __init__(self, body):
        self._body = body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self._body).encode()


def assertion():
    return {
        "agent_id": "rend",
        "agent_name": "Rend",
        "public_key": "mesh-rend-prod-public-key",
        "codeseal_evidence": {
            "manifest": {
                "event_id": "PTCS-EVT-TEST",
                "mesh_identity": {
                    "agent_id": "rend",
                    "agent_name": "Rend",
                    "public_key": "mesh-rend-prod-public-key",
                    "expires_at": "2099-01-01T00:00:00Z",
                    "revoked": False,
                },
            },
            "registry_signature": "signature",
            "registry_public_key": "registry-key",
        },
    }


class TestCodeSealProductionVerifier(unittest.TestCase):
    def setUp(self):
        self.v = CodeSealIdentityVerifier()

    def test_unconfigured_fails_closed(self):
        with patch.dict(os.environ, {"CODESEAL_VERIFIER_MODE": "unconfigured"}, clear=False):
            result = self.v.verify(assertion())
        self.assertFalse(result.ok)
        self.assertTrue(result.metadata["fail_closed"])

    def test_missing_explicit_evidence_rejected(self):
        a = {
            "agent_id": "rend",
            "agent_name": "Rend",
            "public_key": "mesh-rend-prod-public-key",
            "manifest": assertion()["codeseal_evidence"]["manifest"],
            "registry_signature": "signature",
            "registry_public_key": "registry-key",
        }
        with patch.dict(os.environ, {"CODESEAL_VERIFIER_MODE": "configured"}, clear=False):
            with patch("gateway.identity.codeseal.urlopen") as u:
                result = self.v.verify(a)
        self.assertFalse(result.ok)
        self.assertEqual(
            result.metadata["reason"],
            "missing_manifest_signature_or_registry_key",
        )
        u.assert_not_called()

    def test_missing_mesh_binding_rejected(self):
        a = assertion()
        del a["codeseal_evidence"]["manifest"]["mesh_identity"]
        with patch.dict(os.environ, {"CODESEAL_VERIFIER_MODE": "configured"}, clear=False):
            result = self.v.verify(a)
        self.assertFalse(result.ok)
        self.assertEqual(result.metadata["reason"], "missing_mesh_identity_binding")

    def test_agent_binding_mismatch_rejected_before_network(self):
        a = assertion()
        a["agent_id"] = "lyra"
        with patch.dict(os.environ, {"CODESEAL_VERIFIER_MODE": "configured"}, clear=False):
            with patch("gateway.identity.codeseal.urlopen") as u:
                result = self.v.verify(a)
        self.assertFalse(result.ok)
        self.assertEqual(result.metadata["reason"], "agent_id_mismatch")
        u.assert_not_called()

    def test_valid_live_contract_shape_is_accepted(self):
        body = {
            "valid": True,
            "cryptographic_signature_valid": True,
            "registry_key_known": True,
            "registry_record_match": True,
            "algorithm": "Ed25519",
            "event_id": "PTCS-EVT-TEST",
            "error": None,
        }
        env = {
            "CODESEAL_VERIFIER_MODE": "configured",
            "CODESEAL_VERIFY_URL": "https://codeseal.progretech.com/api/v1/verify",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("gateway.identity.codeseal.urlopen", return_value=_Response(body)):
                result = self.v.verify(assertion())
        self.assertTrue(result.ok)
        self.assertTrue(result.metadata["cryptographic_verification"])
        self.assertTrue(result.metadata["registry_record_match"])
        self.assertEqual(result.metadata["algorithm"], "Ed25519")

    def test_crypto_valid_but_unknown_record_is_rejected(self):
        body = {
            "valid": False,
            "cryptographic_signature_valid": True,
            "registry_key_known": True,
            "registry_record_match": False,
            "algorithm": "Ed25519",
            "event_id": "PTCS-EVT-TEST",
        }
        with patch.dict(os.environ, {"CODESEAL_VERIFIER_MODE": "configured"}, clear=False):
            with patch("gateway.identity.codeseal.urlopen", return_value=_Response(body)):
                result = self.v.verify(assertion())
        self.assertFalse(result.ok)
        self.assertEqual(result.metadata["reason"], "registry_verification_failed")


if __name__ == "__main__":
    unittest.main()
