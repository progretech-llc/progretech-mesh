import base64
import unittest
import main
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

class TestIdentityPopNonce(unittest.TestCase):
    def setUp(self):
        main.IDENTITY_CHALLENGES.clear()

    def test_legitimate_signature(self):
        key=Ed25519PrivateKey.generate()
        pub=key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        c=main.issue_identity_challenge("rend","device-1")
        sig=base64.b64encode(key.sign(c["signing_payload"].encode())).decode()
        ok, reason, consumed=main.consume_identity_challenge("rend","device-1",c["challenge_id"])
        self.assertTrue(ok, reason)
        ok, reason=main.verify_identity_proof(pub, consumed["signing_payload"], sig)
        self.assertTrue(ok, reason)

    def test_wrong_private_key_fails(self):
        key=Ed25519PrivateKey.generate()
        wrong=Ed25519PrivateKey.generate()
        pub=key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        c=main.issue_identity_challenge("rend","device-1")
        sig=base64.b64encode(wrong.sign(c["signing_payload"].encode())).decode()
        ok, reason, consumed=main.consume_identity_challenge("rend","device-1",c["challenge_id"])
        self.assertTrue(ok, reason)
        ok, reason=main.verify_identity_proof(pub, consumed["signing_payload"], sig)
        self.assertFalse(ok)
        self.assertEqual(reason,"identity_signature_invalid")

    def test_replay_fails(self):
        c=main.issue_identity_challenge("rend","device-1")
        ok, reason, _=main.consume_identity_challenge("rend","device-1",c["challenge_id"])
        self.assertTrue(ok, reason)
        ok, reason, _=main.consume_identity_challenge("rend","device-1",c["challenge_id"])
        self.assertFalse(ok)

    def test_stale_challenge_fails(self):
        c=main.issue_identity_challenge("rend","device-1")
        main.IDENTITY_CHALLENGES[c["challenge_id"]]["expires_at"]=main.unix_now()-1
        ok, reason, _=main.consume_identity_challenge("rend","device-1",c["challenge_id"])
        self.assertFalse(ok)
        self.assertEqual(reason,"identity_challenge_expired")

if __name__ == "__main__":
    unittest.main()
