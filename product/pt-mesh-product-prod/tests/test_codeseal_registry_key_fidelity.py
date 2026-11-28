import json
import os
import unittest
from unittest.mock import patch

from gateway.identity.codeseal import CodeSealIdentityVerifier

class _Response:
    status = 200
    def __init__(self, body):
        self._body = body
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self): return json.dumps(self._body).encode()

class TestCodeSealRegistryKeyFidelity(unittest.TestCase):
    def test_registry_public_key_trailing_newline_is_preserved(self):
        pem = "-----BEGIN PUBLIC KEY-----\nABC\n-----END PUBLIC KEY-----\n"
        evidence = {
            "manifest": {
                "event_id":"PTCS-EVT-TEST",
                "mesh_identity":{
                    "agent_id":"rend",
                    "agent_name":"Rend",
                    "public_key":"mesh-key",
                    "expires_at":"2099-01-01T00:00:00Z",
                    "revoked":False,
                },
            },
            "registry_signature":"sig",
            "registry_public_key":pem,
        }
        assertion={
            "agent_id":"rend",
            "agent_name":"Rend",
            "public_key":"mesh-key",
            "codeseal_evidence":evidence,
        }
        body={
            "valid":True,
            "cryptographic_signature_valid":True,
            "registry_key_known":True,
            "registry_record_match":True,
            "algorithm":"Ed25519",
            "event_id":"PTCS-EVT-TEST",
        }
        captured={}
        def fake_urlopen(req, timeout=None):
            payload=json.loads(req.data.decode())
            captured.update(payload)
            return _Response(body)

        env={
            "CODESEAL_VERIFIER_MODE":"configured",
            "CODESEAL_VERIFY_URL":"https://codeseal.progretech.com/api/v1/verify",
        }
        with patch.dict(os.environ,env,clear=False):
            with patch("gateway.identity.codeseal.urlopen",side_effect=fake_urlopen):
                result=CodeSealIdentityVerifier().verify(assertion)

        self.assertTrue(result.ok)
        self.assertEqual(captured["registry_public_key"],pem)
        self.assertTrue(captured["registry_public_key"].endswith("\n"))

if __name__=="__main__":
    unittest.main()
