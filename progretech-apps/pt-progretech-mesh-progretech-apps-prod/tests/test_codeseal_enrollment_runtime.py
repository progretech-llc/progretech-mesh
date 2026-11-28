import os
import unittest
from unittest.mock import patch
import main

class Result:
    def __init__(self, ok=True):
        self.ok=ok
        self.provider="codeseal"
        self.error=None if ok else "bad evidence"
        self.metadata={
            "cryptographic_verification":ok,
            "registry_key_known":ok,
            "registry_record_match":ok,
            "public_key_bound":ok,
        }

class TestCodeSealEnrollmentRuntime(unittest.TestCase):
    def test_codeseal_mode_uses_production_verifier(self):
        payload={"agent_id":"rend","codeseal_evidence":{"manifest":{}}}
        with patch.dict(os.environ,{"MESH_AGENT_IDENTITY_MODE":"codeseal"},clear=False):
            with patch("main.CodeSealIdentityVerifier") as cls:
                cls.return_value.verify.return_value=Result(True)
                result=main.verify_runtime_agent_identity(payload,"Rend","pk","legacy")
        self.assertTrue(result["valid"])
        self.assertEqual(result["provider"],"codeseal")
        cls.return_value.verify.assert_called_once()

    def test_codeseal_mode_fails_closed(self):
        with patch.dict(os.environ,{"MESH_AGENT_IDENTITY_MODE":"codeseal"},clear=False):
            with patch("main.CodeSealIdentityVerifier") as cls:
                cls.return_value.verify.return_value=Result(False)
                result=main.verify_runtime_agent_identity({"agent_id":"rend"},"Rend","pk","legacy")
        self.assertFalse(result["valid"])
        self.assertEqual(result["state"],"invalid")

    def test_development_mode_preserves_legacy_adapter(self):
        with patch.dict(os.environ,{"MESH_AGENT_IDENTITY_MODE":"development"},clear=False):
            with patch("main.verify_codeseal",return_value={"valid":True,"state":"verified"}) as legacy:
                result=main.verify_runtime_agent_identity({},"Rend","pk","CS-REND-DEV-001")
        self.assertTrue(result["valid"])
        legacy.assert_called_once()

if __name__=="__main__":
    unittest.main()
