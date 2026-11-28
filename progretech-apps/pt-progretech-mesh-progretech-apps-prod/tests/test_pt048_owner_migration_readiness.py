import unittest
import main
import mesh_ownership

class TestPT048OwnerMigrationReadiness(unittest.TestCase):
    def setUp(self):
        main.DEV_AGENT_REGISTRY.clear()
        main.REVOKED_DEVICE_IDS.clear()
        mesh_ownership.OWNERSHIP_CLAIMS.clear()

    def _login(self, client, uid="owner-a"):
        with client.session_transaction() as sess:
            sess["mesh_user"]={"id":uid,"display_name":uid,"auth_source":"test"}

    def test_public_agent_hides_owner_id(self):
        item=main.public_agent({"id":"rend","name":"Rend","owner_id":"owner-a","codeseal_key":"secret"})
        self.assertNotIn("owner_id",item)
        self.assertNotIn("codeseal_key",item)
        self.assertTrue(item["owner_bound"])
        self.assertEqual(item["ownership_state"],"owned")

    def test_redeem_revokes_old_device(self):
        main.DEV_AGENT_REGISTRY["rend"]={"id":"rend","name":"Rend","trust_state":"verified","transport":"connected"}
        old=main.issue_device_credential("rend")
        ok,reason,payload=main.validate_device_credential("rend",old["credential"])
        self.assertTrue(ok,reason)
        old_device=payload["device_id"]

        client=main.app.test_client()
        self._login(client)
        created=client.post("/api/ownership/claims",json={"agent_id":"rend"})
        self.assertEqual(created.status_code,201)
        claim=created.get_json()["claim_code"]

        redeemed=client.post("/api/ownership/redeem",json={
            "agent_id":"rend",
            "device_credential":old["credential"],
            "claim_code":claim,
        })
        self.assertEqual(redeemed.status_code,200,redeemed.get_data(as_text=True))

        ok,reason,_=main.validate_device_credential("rend",old["credential"])
        self.assertFalse(ok)
        self.assertEqual(reason,"device_credential_revoked")
        self.assertNotEqual(old_device, redeemed.get_json()["device_id"])

    def test_owned_agent_cannot_issue_migration_claim_again(self):
        main.DEV_AGENT_REGISTRY["rend"]={"id":"rend","name":"Rend","trust_state":"verified","owner_id":"owner-a"}
        client=main.app.test_client()
        self._login(client)
        res=client.post("/api/ownership/claims",json={"agent_id":"rend"})
        self.assertEqual(res.status_code,409)
        self.assertEqual(res.get_json()["error"],"ownership_already_bound")

if __name__=="__main__":
    unittest.main()
