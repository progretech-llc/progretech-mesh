import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image, ImageDraw
from control_center.media_jobs import generate, image_request, review_input, review

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.home=Path(self.tmp.name)
        self.source=self.home/'.local/share/rend/runtimes/comfyui-rocm/ComfyUI/output/icon.png';self.source.parent.mkdir(parents=True)
        picture=Image.new('RGB',(1024,1024),'blue');ImageDraw.Draw(picture).rectangle((200,200,800,800),fill='red');picture.save(self.source)
        self.mesh=SimpleNamespace(home=self.home,provider=SimpleNamespace(bindings={'host--imagen':'imagen'}),idle=lambda:True,mark=lambda *a:None)
        self.addCleanup(patch.stopall)
        patch('control_center.media_jobs.record_activity',return_value={'status':'saved-and-recalled','memory_id':'fixture'}).start()
        self.route=SimpleNamespace(capability_id='animagine-xl-3.1')
        patch('mesh_media_router.resolve_active_role',return_value=self.route).start()
        self.invoke=patch('mesh_media_runtime.invoke_intent',return_value=SimpleNamespace(ok=True,capability_id='animagine-xl-3.1',artifact=str(self.source))).start()
        patch('control_center.media_jobs.psutil.virtual_memory',return_value=SimpleNamespace(available=50*1024**3,total=120*1024**3)).start()
    def test_explicit_generation_and_review_are_separate(self):
        for text in ['Generate a small robot icon','Please create a friendly robot image','Draw an icon']:self.assertTrue(image_request(text),text)
        for text in ['Review the generated icon','When imagen is done, review the generated image',"Don't generate an icon",'Generate a status summary']:self.assertFalse(image_request(text),text)
    def test_valid_file_is_published_with_honest_transparency_and_receipt(self):
        result=generate(self.mesh,'host--imagen','Generate a robot icon','a'*32)
        art=result['artifacts'][0];self.assertTrue(Path(art['path']).is_file());self.assertEqual(art['sha256'],hashlib.sha256(self.source.read_bytes()).hexdigest());self.assertFalse(art['alpha']);self.assertIn('opaque',result['reply'])
    def test_success_text_and_empty_or_invalid_file_cannot_complete(self):
        self.source.write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'artifact_unavailable'):generate(self.mesh,'host--imagen','Generate an icon','a'*32)
        self.source.write_bytes(b'not an image')
        with self.assertRaisesRegex(ValueError,'validation_failed'):generate(self.mesh,'host--imagen','Generate an icon','a'*32)
    def test_missing_approval_or_resource_headroom_prevents_invocation(self):
        with patch('mesh_media_router.resolve_active_role',return_value=None):
            with self.assertRaisesRegex(ValueError,'provider_unavailable'):generate(self.mesh,'host--imagen','Generate an icon','a'*32)
        self.mesh.idle=lambda:False
        with self.assertRaisesRegex(ValueError,'other_work'):generate(self.mesh,'host--imagen','Generate an icon','a'*32)
        self.invoke.assert_not_called()
    def test_review_supplies_real_pixels_and_uses_configured_local_vision_model(self):
        result=generate(self.mesh,'host--imagen','Generate a robot icon','a'*32)
        self.mesh.api=lambda path,*args: {'models':[{'name':'qwen3.5:2b'}]} if path=='tags' else {'capabilities':['vision']}
        self.mesh.config=lambda a:({'models':{'providers':{'ollama':{'models':[{'id':'qwen3.5:2b','input':['text','image']}]}}}},'imagen','ollama/text')
        model,content=review_input(self.mesh,[result['artifacts'][0]['path']]);self.assertEqual(model,'ollama/qwen3.5:2b');self.assertTrue(content[0]['image_url']['url'].startswith('data:image/png;base64,'))
        with self.assertRaisesRegex(ValueError,'artifact_unavailable'):review_input(self.mesh,[str(self.source)])

    def test_visual_review_is_bounded_validated_and_publishes_actual_report(self):
        artifact=generate(self.mesh,'host--imagen','Generate an icon','a'*32)['artifacts'][0]['path']
        self.mesh.provider.bindings['host--codex']='codex'
        self.mesh.config=lambda a:({'models':{'providers':{'ollama':{'models':[{'id':'qwen3.5:2b','input':['text','image']}]}}}},'codex','ollama/text')
        calls=[]
        def api(path,body=None,**kwargs):
            if path=='tags':return {'models':[{'name':'qwen3.5:2b'}]}
            if path=='show':return {'capabilities':['vision']}
            calls.append(body)
            return {'message':{'content':'{"verdict":"fail","observations":["Round smiling face"],"concerns":["Background is opaque"]}'}}
        self.mesh.api=api;self.mesh.prepare=lambda *a,**kw:None
        result=review(self.mesh,'host--codex','Review this icon','b'*32,[artifact])
        self.assertEqual(result['review']['source_sha256'],hashlib.sha256(Path(artifact).read_bytes()).hexdigest())
        self.assertTrue((self.home/'pt-context/deliverables/mesh-odexi'/('review-'+'b'*32+'.json')).is_file())
        self.assertTrue(calls[0]['messages'][1]['images']);self.assertFalse(calls[0]['think']);self.assertEqual(calls[0]['options']['num_ctx'],8192)
        self.assertIn('no alpha channel',result['reply'])
        old=self.mesh.api
        self.mesh.api=lambda path,*a,**kw: {'message':{'content':'I am working on unrelated Factory tasks.'}} if path=='chat' else old(path,*a,**kw)
        with self.assertRaisesRegex(ValueError,'review_incomplete'):review(self.mesh,'host--codex','Review icon','c'*32,[artifact])
        self.assertFalse((self.home/'Rend/artifacts/codex'/('review-'+'c'*32+'.json')).exists())
