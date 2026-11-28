import json
import os
import unittest
from unittest.mock import patch

import main
import mesh_firebase_auth
import mesh_ownership
from mesh_owner_access import fleet_owner_id, owner_uid_bindings


class SharedFleetAccess(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "MESH_AUTH_MODE": "firebase-email-link",
            "MESH_OWNER_UID_BINDINGS": '{"secondary":"primary"}',
            "MESH_OWNERSHIP_MODE": "enforce",
            "DEV_SEED_AGENTS": "0",
        })
        self.env.start()
        self.saved_registry = dict(main.DEV_AGENT_REGISTRY)
        main.DEV_AGENT_REGISTRY.clear()
        main.DEV_AGENT_REGISTRY.update({
            "shared": {"id": "shared", "name": "Shared", "owner_id": "primary",
                       "trust_state": "verified", "transport": "not-connected"},
            "other": {"id": "other", "name": "Other", "owner_id": "unrelated",
                      "trust_state": "verified", "transport": "not-connected"},
        })
        self.app = main.create_app()

    def tearDown(self):
        main.DEV_AGENT_REGISTRY.clear()
        main.DEV_AGENT_REGISTRY.update(self.saved_registry)
        self.env.stop()

    def login(self, uid, **body):
        client = self.app.test_client()
        decoded = {"uid": uid, "email": uid + "@example.invalid", "email_verified": True}
        with patch.object(mesh_firebase_auth, "verify_firebase_id_token", return_value=decoded):
            response = client.post("/api/auth/firebase/session", json={"idToken": "fixture", **body})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["id"], uid)
        return client

    def test_both_logins_share_fleet_but_keep_actor_identity(self):
        for uid in ("primary", "secondary"):
            client = self.login(uid)
            result = client.get("/api/agents").get_json()
            self.assertEqual([a["id"] for a in result["agents"]], ["shared"])
            self.assertEqual(client.get("/api/agents/shared/events").status_code, 200)
            self.assertEqual(client.get("/api/agents/other/events").status_code, 404)
            with client.session_transaction() as sess:
                self.assertEqual(sess["mesh_user"]["id"], uid)

    def test_browser_cannot_request_another_owner(self):
        client = self.login("outsider", owner_id="primary", owner_uid="primary")
        self.assertEqual(client.get("/api/agents").get_json()["agents"], [])
        self.assertEqual(client.get("/api/agents/shared/events").status_code, 404)

    def test_new_claim_uses_shared_owner(self):
        client = self.login("secondary")
        response = client.post("/api/ownership/claims", json={"agent_id": "new-role"})
        self.assertEqual(response.status_code, 201)
        claim = mesh_ownership.OWNERSHIP_CLAIMS[response.get_json()["claim_code"]]
        self.assertEqual(claim["owner_id"], "primary")
        mesh_ownership.OWNERSHIP_CLAIMS.pop(claim["code"])

    def test_removing_binding_revokes_access_for_existing_session(self):
        client = self.login("secondary")
        self.assertEqual(client.get("/api/agents/shared/events").status_code, 200)
        os.environ["MESH_OWNER_UID_BINDINGS"] = "{}"
        self.assertEqual(client.get("/api/agents").get_json()["agents"], [])
        self.assertEqual(client.get("/api/agents/shared/events").status_code, 404)

    def test_non_firebase_sessions_do_not_use_binding(self):
        self.assertEqual(fleet_owner_id({"id": "secondary", "auth_source": "development"}), "secondary")

    def test_invalid_configuration_fails_startup(self):
        for value in ('[]', 'null', '{', '{"secondary":null}',
                      '{"a":"b","b":"c"}', '{"a":"b","b":"a"}',
                      '{"a":"a"}', '{"a":"b","a":"c"}',
                      '{"user@example.com":"primary"}',
                      json.dumps({str(i): "primary" for i in range(257)})):
            with self.subTest(value=value):
                os.environ["MESH_OWNER_UID_BINDINGS"] = value
                with self.assertRaisesRegex(ValueError, "invalid_owner_uid_bindings"):
                    main.create_app()

    def test_empty_configuration_keeps_exact_owner_behavior(self):
        os.environ.pop("MESH_OWNER_UID_BINDINGS")
        self.assertEqual(owner_uid_bindings(), {})
        self.assertEqual(fleet_owner_id({"id": "secondary", "auth_source": "firebase-email-link"}), "secondary")


if __name__ == "__main__":
    unittest.main()
