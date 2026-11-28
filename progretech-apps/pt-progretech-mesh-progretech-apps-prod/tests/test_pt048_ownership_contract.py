import os
import unittest

import main
import mesh_ownership


class TestPT048OwnershipFoundation(unittest.TestCase):
    def setUp(self):
        self.old_mode = os.environ.get("MESH_OWNERSHIP_MODE")
        os.environ["MESH_OWNERSHIP_MODE"] = "observe"
        mesh_ownership.OWNERSHIP_CLAIMS.clear()
        main.DEV_AGENT_REGISTRY.clear()
        main.EVENT_BUFFERS.clear()
        main.ACTION_REQUESTS.clear()

    def tearDown(self):
        if self.old_mode is None:
            os.environ.pop("MESH_OWNERSHIP_MODE", None)
        else:
            os.environ["MESH_OWNERSHIP_MODE"] = self.old_mode

    def _login(self, client, uid="user-a"):
        with client.session_transaction() as sess:
            sess["mesh_user"] = {
                "id": uid,
                "display_name": uid,
                "email": f"{uid}@example.invalid",
                "auth_source": "test",
            }

    def test_explicit_owner_isolated_even_in_observe_mode(self):
        record = {"id": "a", "owner_id": "user-a"}
        self.assertEqual(mesh_ownership.can_access(record, "user-a"), (True, "ok"))
        self.assertEqual(mesh_ownership.can_access(record, "user-b"), (False, "agent_not_found"))

    def test_unowned_legacy_allowed_only_in_observe_mode(self):
        record = {"id": "legacy"}
        self.assertTrue(mesh_ownership.can_access(record, "user-a")[0])
        os.environ["MESH_OWNERSHIP_MODE"] = "enforce"
        self.assertFalse(mesh_ownership.can_access(record, "user-a")[0])

    def test_device_credential_carries_owner(self):
        item = main.issue_device_credential("rend", owner_id="user-a")
        ok, reason, payload = main.validate_device_credential("rend", item["credential"])
        self.assertTrue(ok, reason)
        self.assertEqual(payload["owner_id"], "user-a")

    def test_activation_carries_owner(self):
        item = main.issue_activation_code("rend", owner_id="user-a")
        self.assertEqual(item["owner_id"], "user-a")

    def test_list_agents_filters_cross_user(self):
        main.DEV_AGENT_REGISTRY.update({
            "mine": {"id":"mine","name":"Mine","trust_state":"verified","owner_id":"user-a","transport":"not-connected"},
            "theirs": {"id":"theirs","name":"Theirs","trust_state":"verified","owner_id":"user-b","transport":"not-connected"},
            "legacy": {"id":"legacy","name":"Legacy","trust_state":"verified","transport":"not-connected"},
        })
        client = main.app.test_client()
        self._login(client)
        res = client.get("/api/agents")
        self.assertEqual(res.status_code, 200)
        ids = {x["id"] for x in res.get_json()["agents"]}
        self.assertIn("mine", ids)
        self.assertIn("legacy", ids)
        self.assertNotIn("theirs", ids)

    def test_cross_user_agent_route_fails_closed(self):
        main.DEV_AGENT_REGISTRY["theirs"] = {
            "id":"theirs","name":"Theirs","trust_state":"verified",
            "owner_id":"user-b","transport":"not-connected"
        }
        client = main.app.test_client()
        self._login(client)
        res = client.get("/api/agents/theirs/events")
        self.assertEqual(res.status_code, 404)

    def test_claim_redeem_binds_owner_and_rotates_credential(self):
        main.DEV_AGENT_REGISTRY["legacy"] = {
            "id":"legacy","name":"Legacy","trust_state":"verified",
            "trust_valid":True,"transport":"connected"
        }
        old = main.issue_device_credential("legacy")
        client = main.app.test_client()
        self._login(client)
        created = client.post("/api/ownership/claims", json={"agent_id":"legacy"})
        self.assertEqual(created.status_code, 201)
        claim = created.get_json()["claim_code"]

        redeemed = client.post("/api/ownership/redeem", json={
            "agent_id":"legacy",
            "device_credential":old["credential"],
            "claim_code":claim,
        })
        self.assertEqual(redeemed.status_code, 200, redeemed.get_data(as_text=True))
        body = redeemed.get_json()
        self.assertEqual(main.DEV_AGENT_REGISTRY["legacy"]["owner_id"], "user-a")
        ok, reason, payload = main.validate_device_credential("legacy", body["device_credential"])
        self.assertTrue(ok, reason)
        self.assertEqual(payload["owner_id"], "user-a")

    def test_enforce_mode_hides_unowned_legacy(self):
        os.environ["MESH_OWNERSHIP_MODE"] = "enforce"
        main.DEV_AGENT_REGISTRY["legacy"] = {
            "id":"legacy","name":"Legacy","trust_state":"verified","transport":"not-connected"
        }
        client = main.app.test_client()
        self._login(client)
        res = client.get("/api/agents")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["agents"], [])


if __name__ == "__main__":
    unittest.main()
