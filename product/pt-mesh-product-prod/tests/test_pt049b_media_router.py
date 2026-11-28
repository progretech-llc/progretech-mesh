import os
import tempfile
import unittest
from pathlib import Path

import mesh_capability_registry as registry
import mesh_media_router as router

class TestPT049BMediaRouter(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"registry.json"
        os.environ["MESH_CAPABILITY_REGISTRY_PATH"]=str(self.path)
        registry.reset_for_tests(self.path)

        # Seed minimal PT049B records using complete native qualification shape.
        reg=registry.ensure_registry()
        for role,cid in router.ROLE_TO_CAPABILITY.items():
            reg["items"][cid]={
                "id":cid,
                "state":"ACTIVE",
                "pin":{"source":"test","version":"1","commit":None,"license":"test","pin_verified_at":"test","egress_policy":"local","notes":""},
                "qualification":{
                    "representative_success":True,
                    "malformed_input":True,
                    "offline_behavior":True,
                    "timeout_behavior":True,
                    "resource_bounds":True,
                    "rollback_test":True,
                    "evidence":[],
                },
                "activation":{"owner_approved":True,"activated_at":"test"},
                "history":[],
                "metadata":{"role":role,"runtime":"test","model_path":"/test"},
            }
        registry._write_registry(reg)

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("MESH_CAPABILITY_REGISTRY_PATH",None)

    def test_image_intent(self):
        x=router.resolve_media_intent("make an anime illustration of a robot")
        self.assertEqual(x.role,"image_generation")
        self.assertEqual(x.capability_id,"animagine-xl-3.1")

    def test_video_intent(self):
        x=router.resolve_media_intent("animate this into a short video clip")
        self.assertEqual(x.role,"video_generation")
        self.assertEqual(x.capability_id,"wan2.2-t2v-a14b-q4km")

    def test_music_intent(self):
        x=router.resolve_media_intent("compose a short instrumental soundtrack")
        self.assertEqual(x.role,"music_generation")
        self.assertEqual(x.capability_id,"ace-step-1.5")

    def test_discussion_is_not_generation(self):
        self.assertIsNone(router.resolve_media_intent("tell me about music generation models"))

    def test_ambiguous_media_request_fails_closed(self):
        self.assertIsNone(router.resolve_media_intent("make an image video"))

    def test_inactive_provider_fails_closed(self):
        reg=registry.ensure_registry()
        reg["items"]["animagine-xl-3.1"]["state"]="QUALIFIED"
        registry._write_registry(reg)
        self.assertIsNone(router.resolve_media_intent("draw an image"))

    def test_owner_unapproved_fails_closed(self):
        reg=registry.ensure_registry()
        reg["items"]["ace-step-1.5"]["activation"]["owner_approved"]=False
        registry._write_registry(reg)
        self.assertIsNone(router.resolve_media_intent("compose music"))

if __name__=="__main__":
    unittest.main()
