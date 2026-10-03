import threading
import time
import unittest
from unittest.mock import patch

import main

class TestPT048IdeRelay(unittest.TestCase):
    def setUp(self):
        main.DEV_AGENT_REGISTRY.clear()
        main.IDE_PENDING.clear()
        main.DEV_AGENT_REGISTRY["rend"]={
            "id":"rend","name":"Rend","owner_id":"owner-a",
            "trust_state":"verified","transport":"connected",
        }

    def test_token_is_owner_and_agent_bound(self):
        issued=main.issue_ide_token("owner-a","rend")
        ok,reason,payload=main.validate_ide_token(issued["token"])
        self.assertTrue(ok,reason)
        self.assertEqual(payload["owner_id"],"owner-a")
        self.assertEqual(payload["agent_id"],"rend")
        main.DEV_AGENT_REGISTRY["rend"]["owner_id"]="owner-b"
        ok,reason,_=main.validate_ide_token(issued["token"])
        self.assertFalse(ok)
        self.assertEqual(reason,"ide_owner_mismatch")

    def test_models_requires_bearer_and_returns_aliases(self):
        token=main.issue_ide_token("owner-a","rend")["token"]
        client=main.app.test_client()
        self.assertEqual(client.get("/v1/models").status_code,401)
        allowed=client.get("/v1/models",headers={"Authorization":f"Bearer {token}"})
        self.assertEqual(allowed.status_code,200)
        ids=[item["id"] for item in allowed.get_json()["data"]]
        self.assertTrue({"rend","rend-code","rend-research"}.issubset(ids))

    def test_nonstream_chat_roundtrip(self):
        token=main.issue_ide_token("owner-a","rend")["token"]
        completion={
            "id":"chatcmpl-test","object":"chat.completion","created":int(time.time()),
            "model":"rend-code",
            "choices":[{"index":0,"message":{"role":"assistant","content":"relay-pass"},"finish_reason":"stop"}],
        }
        def fake_send(agent_id,message):
            rid=message["request_id"]
            threading.Timer(0.01,lambda:main.resolve_ide_pending(agent_id,{
                "type":"ide_chat_response","request_id":rid,
                "payload":{"ok":True,"completion":completion},
            })).start()
            return True,None
        client=main.app.test_client()
        with patch.object(main,"send_gateway_message",side_effect=fake_send):
            response=client.post("/v1/chat/completions",
                headers={"Authorization":f"Bearer {token}"},
                json={"model":"rend-code","messages":[{"role":"user","content":"test"}],"stream":False})
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        self.assertEqual(response.get_json()["choices"][0]["message"]["content"],"relay-pass")

    def test_stream_compatibility_uses_sse(self):
        token=main.issue_ide_token("owner-a","rend")["token"]
        completion={
            "id":"chatcmpl-stream","object":"chat.completion","created":int(time.time()),
            "model":"rend",
            "choices":[{"index":0,"message":{"role":"assistant","content":"stream-pass"},"finish_reason":"stop"}],
        }
        def fake_send(agent_id,message):
            rid=message["request_id"]
            threading.Timer(0.01,lambda:main.resolve_ide_pending(agent_id,{
                "type":"ide_chat_response","request_id":rid,
                "payload":{"ok":True,"completion":completion},
            })).start()
            return True,None
        client=main.app.test_client()
        with patch.object(main,"send_gateway_message",side_effect=fake_send):
            response=client.post("/v1/chat/completions",
                headers={"Authorization":f"Bearer {token}"},
                json={"model":"rend","messages":[{"role":"user","content":"test"}],"stream":True})
        self.assertEqual(response.status_code,200)
        body=response.get_data(as_text=True)
        self.assertIn("text/event-stream",response.content_type)
        self.assertIn("stream-pass",body)
        self.assertIn("data: [DONE]",body)

if __name__=="__main__":
    unittest.main()
