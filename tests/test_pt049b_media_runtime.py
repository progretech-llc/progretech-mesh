import unittest
from unittest.mock import patch
from types import SimpleNamespace
import mesh_media_runtime as rt
import json
import tempfile
import subprocess
import sys
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
        with tempfile.TemporaryDirectory() as directory:
            foreign=Path(directory)/'unrelated.txt'; foreign.write_text('unrelated fixture')
            def backend(command,timeout):
                job=Path(command[command.index('--output-dir')+1]); (job/'result.json').write_text(json.dumps({'artifact':str(foreign)}))
                return SimpleNamespace(returncode=0,stdout='',stderr='')
            with patch.object(rt,'OUT_ROOT',Path(directory)/'jobs'), patch.object(rt,'_require_output_root'), patch.object(rt.router,'resolve_media_intent',return_value=route), patch.object(rt.router,'resolve_active_role',return_value=route), patch.object(rt,'_run_backend',side_effect=backend):
                result=rt.invoke_intent('generate an image')
                self.assertFalse(result.ok); self.assertIsNone(result.artifact)
                self.assertEqual(result.metadata['error'],'artifact_outside_owned_job')
                self.assertNotIn('artifact',result.metadata)

    def test_storage_destination_still_refuses_outside_mounted_drive(self):
        with patch.object(rt,'OUT_ROOT',Path('/var/empty/foreign-media-output')), patch.object(rt.subprocess,'check_output',return_value='/mnt/pt-context\n'):
            with self.assertRaisesRegex(ValueError,'Invalid artifact destination'):
                rt._require_output_root()

    def test_backend_selection_preserves_explicit_rocm(self):
        with patch.dict(rt.os.environ,{},clear=True):
            self.assertIn('comfyui-rocm',str(rt._image_python()))
        with patch.dict(rt.os.environ,{'FACTORY_IMAGE_DEVICE':'cuda'}):
            self.assertIn('comfyui-cuda',str(rt._image_python()))
        with patch.dict(rt.os.environ,{'FACTORY_IMAGE_DEVICE':'rocm'}):
            self.assertIn('comfyui-rocm',str(rt._image_python()))

    def test_owned_artifact_returned_but_escape_symlink_rejected(self):
        route=SimpleNamespace(role='image_generation',capability_id='fixture')
        with tempfile.TemporaryDirectory() as directory:
            foreign=Path(directory)/'foreign.png';foreign.write_bytes(b'fixture')
            for escape in (False,True):
                def backend(command,timeout):
                    job=Path(command[command.index('--output-dir')+1]);artifact=job/'render.png'
                    if escape:artifact.symlink_to(foreign)
                    else:artifact.write_bytes(b'owned fixture')
                    (job/'result.json').write_text(json.dumps({'artifact':str(artifact)}))
                    return SimpleNamespace(returncode=0,stdout='',stderr='')
                with self.subTest(escape=escape), patch.object(rt,'OUT_ROOT',Path(directory)/'jobs'), patch.object(rt,'_require_output_root'), patch.object(rt.router,'resolve_media_intent',return_value=route), patch.object(rt.router,'resolve_active_role',return_value=route), patch.object(rt,'_run_backend',side_effect=backend):
                    result=rt.invoke_intent('generate an image')
                    self.assertEqual(result.ok,not escape)
                    if escape:self.assertIsNone(result.artifact)

    def test_backend_timeout_reaps_owned_process_without_gpu(self):
        real_popen=rt.subprocess.Popen;started=[]
        def start(*args,**kwargs):
            self.assertTrue(kwargs['start_new_session'])
            proc=real_popen(*args,**kwargs);started.append(proc);return proc
        with patch.object(rt.subprocess,'Popen',side_effect=start):
            with self.assertRaises(subprocess.TimeoutExpired):
                rt._run_backend([sys.executable,'-c','import time; time.sleep(60)'],.1)
        self.assertIsNotNone(started[0].poll())

    def test_successful_backend_preserves_output_and_exit(self):
        result=rt._run_backend([sys.executable,'-c','print("synthetic success")'],5)
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout.strip(),'synthetic success')

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
