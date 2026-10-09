import unittest
from unittest.mock import patch
from types import SimpleNamespace
import mesh_media_runtime as rt
import json
import tempfile
from pathlib import Path

class TestPT049BMediaRuntime(unittest.TestCase):
    def test_unknown_image_backend_rejected(self):
        with patch.dict(rt.os.environ,{'FACTORY_IMAGE_DEVICE':'../../other'}):
            with self.assertRaisesRegex(ValueError,'Unsupported'):
                rt._image_python()

    def test_unmounted_storage_never_launches_backend(self):
        route=SimpleNamespace(role='image_generation',capability_id='animagine-xl-3.1')
        with patch.object(rt.router,'resolve_media_intent',return_value=route), patch.object(rt.router,'resolve_active_role',return_value=route), patch.object(rt.subprocess,'check_output',return_value='/\n'), patch.object(rt.subprocess,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'PT_CONTEXT'):
                rt.invoke_intent('generate an image')
            run.assert_not_called()

    def test_foreign_result_file_is_not_returned_as_artifact(self):
        route=SimpleNamespace(role='image_generation',capability_id='animagine-xl-3.1')
        with tempfile.TemporaryDirectory(dir='/mnt/pt-context/job-artifacts/factory-recovery-20261009') as directory:
            foreign=Path(directory)/'unrelated.txt'; foreign.write_text('unrelated fixture')
            real_run=rt.subprocess.run
            def backend(command,**kwargs):
                if command[0]=='findmnt': return real_run(command,**kwargs)
                job=Path(command[command.index('--output-dir')+1]); (job/'result.json').write_text(json.dumps({'artifact':str(foreign)}))
                return SimpleNamespace(returncode=0,stdout='',stderr='')
            with patch.object(rt,'OUT_ROOT',Path(directory)/'jobs'), patch.object(rt.router,'resolve_media_intent',return_value=route), patch.object(rt.router,'resolve_active_role',return_value=route), patch.object(rt.subprocess,'run',side_effect=backend):
                result=rt.invoke_intent('generate an image')
                self.assertFalse(result.ok); self.assertIsNone(result.artifact)
                self.assertEqual(result.metadata['error'],'artifact_outside_owned_job')

    def test_prompt_required(self):
        with self.assertRaisesRegex(ValueError,"prompt_required"):
            rt._validate_prompt("")

    def test_prompt_bounded(self):
        with self.assertRaisesRegex(ValueError,"prompt_too_long"):
            rt._validate_prompt("x"*1201)

    def test_role_script_mapping(self):
        self.assertTrue(str(rt._script_for_role("image_generation")).endswith("media-image-generate.py"))
        self.assertTrue(str(rt._script_for_role("video_generation")).endswith("media-video-generate.py"))
        self.assertTrue(str(rt._script_for_role("music_generation")).endswith("media-music-generate.py"))

    def test_no_route_fails_closed(self):
        with patch("mesh_media_runtime.router.resolve_media_intent",return_value=None):
            x=rt.invoke_intent("discuss images")
            self.assertFalse(x.ok)
            self.assertEqual(x.metadata["error"],"no_unambiguous_active_media_route")

    def test_recheck_active_gate(self):
        route=SimpleNamespace(role="image_generation",capability_id="animagine-xl-3.1")
        with patch("mesh_media_runtime.router.resolve_media_intent",return_value=route), \
             patch("mesh_media_runtime.router.resolve_active_role",return_value=None):
            with self.assertRaisesRegex(PermissionError,"not_active"):
                rt.invoke_intent("make an image")

if __name__=="__main__":
    unittest.main()
