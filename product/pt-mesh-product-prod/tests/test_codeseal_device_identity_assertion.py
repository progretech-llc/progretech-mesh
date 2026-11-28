import os
import unittest
from unittest.mock import patch
import main

class Result:
    ok=True
    provider="codeseal"
    error=None
    metadata={"cryptographic_verification":True,"registry_key_known":True,"registry_record_match":True,"public_key_bound":True}

class TestDeviceIdentityAssertionContract(unittest.TestCase):
    def test_runtime_verifier_still_accepts_codeseal_mode(self):
        with patch.dict(os.environ,{"MESH_AGENT_IDENTITY_MODE":"codeseal"},clear=False):
            with patch("main.CodeSealIdentityVerifier") as cls:
                cls.return_value.verify.return_value=Result()
                r=main.verify_runtime_agent_identity(
                    {"agent_id":"rend","codeseal_evidence":{"manifest":{}}},
                    "Rend","pk","",
                )
        self.assertTrue(r["valid"])
        self.assertEqual(r["provider"],"codeseal")

if __name__=="__main__":
    unittest.main()
