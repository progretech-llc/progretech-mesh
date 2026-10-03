import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from control_center import artifacts
from control_center.management import validate_management

class ArtifactsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.home=Path(self.tmp.name)
    def call(self,role,action,**args):return artifacts.dispatch(self.home,role,action,args)
    def test_chunk_upload_digest_and_role_binding(self):
        data=b'owner attachment\n';r=self.call('designer','files.begin',name='brief.txt',size=len(data));uid=r['upload_id']
        with self.assertRaisesRegex(ValueError,'not_found'):self.call('reviewer','files.chunk',upload_id=uid,offset=0,data=base64.b64encode(data).decode())
        self.call('designer','files.chunk',upload_id=uid,offset=0,data=base64.b64encode(data).decode())
        with self.assertRaisesRegex(ValueError,'chunk'):self.call('designer','files.chunk',upload_id=uid,offset=0,data='eA==')
        with self.assertRaisesRegex(ValueError,'digest'):self.call('designer','files.finish',upload_id=uid,sha256='0'*64)
        r=self.call('designer','files.finish',upload_id=uid,sha256=hashlib.sha256(data).hexdigest())
        self.assertEqual(Path(r['path']).read_bytes(),data);self.assertEqual(Path(r['path']).stat().st_mode&0o777,0o600)
        self.assertEqual(self.call('main','files.list')['files'],[])
    def test_current_visual_role_can_receive_reference_image(self):
        data=b'fixture image bytes'
        upload=self.call('imagen','files.begin',name='reference.png',size=len(data))
        self.call('imagen','files.chunk',upload_id=upload['upload_id'],offset=0,data=base64.b64encode(data).decode())
        receipt=self.call('imagen','files.finish',upload_id=upload['upload_id'],sha256=hashlib.sha256(data).hexdigest())
        self.assertEqual(Path(receipt['path']).read_bytes(),data)
        self.assertIn('/imagen/',receipt['path'])
    def test_shared_publish_download_references_and_changed_file(self):
        p=self.home/'Rend/artifacts/designer/icon.svg';p.parent.mkdir(parents=True);p.write_text('<svg/>')
        rows=self.call('main','files.list')['files'];self.assertEqual(rows[0]['producer'],'designer');self.assertNotIn('path',rows[0])
        fid=rows[0]['id'];r=self.call('reviewer','files.read',id=fid,offset=0);self.assertEqual(base64.b64decode(r['data']),b'<svg/>')
        self.assertIn(str(p),self.call('reviewer','files.reference',id=fid)['reference'])
        p.write_text('changed')
        with self.assertRaisesRegex(ValueError,'changed'):self.call('main','files.read',id=fid,offset=0)
    def test_catalog_excludes_private_roots_symlinks_credentials_and_inbox(self):
        root=self.home/'Rend/artifacts/designer';root.mkdir(parents=True)
        outside=self.home/'private-memory.md';outside.write_text('private');(root/'leak.md').symlink_to(outside)
        (root/'credentials.json').write_text('{}');(root/'.env').write_text('private')
        hidden=root/'private';hidden.mkdir();(hidden/'notes.md').write_text('private')
        job=self.home/'Rend/jobs/task/deliverables';job.mkdir(parents=True);(job/'report.md').write_text('approved')
        rows=self.call('main','files.list')['files'];self.assertEqual([r['name'] for r in rows],['report.md'])
        with self.assertRaises(ValueError):self.call('designer','files.begin',name='../leak.txt',size=1)
        with self.assertRaises(ValueError):self.call('designer','files.begin',name='credentials.json',size=1)
        with self.assertRaises(ValueError):self.call('main','files.read',id='../file',offset=0)
    def test_chunk_and_transfer_limits(self):
        with self.assertRaises(ValueError):validate_management('files.begin',{'name':'report.txt','size':artifacts.MAX_FILE+1})
        r=self.call('main','files.begin',name='report.txt',size=1)
        with self.assertRaises(ValueError):self.call('main','files.chunk',upload_id=r['upload_id'],offset=0,data='not-base64')
        with self.assertRaises(ValueError):self.call('main','files.finish',upload_id=r['upload_id'],sha256='0'*64)
        self.assertTrue(self.call('main','files.cancel',upload_id=r['upload_id'])['cancelled'])
        with self.assertRaises(ValueError):self.call('main','files.read',id='0'*32,offset=-1)
    def test_symlinked_attachment_directory_is_rejected(self):
        outside=self.home/'outside';outside.mkdir();root=self.home/'.progretech-mesh/prompt-attachments';root.mkdir(parents=True);(root/'designer').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'path_unavailable'):self.call('designer','files.begin',name='brief.txt',size=1)
