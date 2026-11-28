import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from flask import Flask
from gateway.platform_release import installed
from mesh_host_distribution import host_bundle
from mesh_sync import register_sync_routes, release

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mesh_update',ROOT/'distribution/mesh-platform-update-v1.py')
worker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state=Path(self.temp.name)
        self.data,self.sha=host_bundle(ROOT)
        self.latest=release(ROOT)

    def test_installed_fingerprint_matches_published_bundle(self):
        worker.unpack(self.data,self.state,self.sha)
        self.assertEqual(installed(self.state),self.latest['fingerprint'])
        (self.state/'gateway/platforms.py').write_text('local edit')
        self.assertNotEqual(installed(self.state),self.latest['fingerprint'])

    def test_checksum_and_unsafe_archive_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'checksum'):
            worker.unpack(self.data,self.state,'0'*64)
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as z:z.writestr('../connector.json','overwrite')
        body=output.getvalue()
        with self.assertRaisesRegex(ValueError,'unsafe'):
            worker.unpack(body,self.state,hashlib.sha256(body).hexdigest())
        self.assertFalse((self.state.parent/'connector.json').exists())

    def prepare(self):
        worker.unpack(self.data,self.state/'source',self.sha)
        python=self.state/'venv/bin/python';python.parent.mkdir(parents=True);python.touch()
        (self.state/'connector.json').write_text(json.dumps({'mesh':'https://mesh.example','prime':'progre','device_credential':'fixture-private'}))
        (self.state/'source/local-note.txt').write_text('keep custom file')
        (self.state/'source/gateway/platforms.py').write_text('old source')

    def test_update_preserves_config_custom_files_and_old_source_on_failed_preflight(self):
        self.prepare()
        with patch.object(worker,'build_opener') as opener,patch.object(worker.subprocess,'run',side_effect=subprocess.CalledProcessError(1,['fixture'])):
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=self.data
            with self.assertRaises(subprocess.CalledProcessError):worker.update(self.state,self.sha,True)
        self.assertEqual((self.state/'source/gateway/platforms.py').read_text(),'old source')
        self.assertFalse((self.state/'update.lock').exists())
        with patch.object(worker,'build_opener') as opener,patch.object(worker.subprocess,'run'):
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=self.data
            worker.update(self.state,self.sha,True)
        self.assertEqual(json.loads((self.state/'connector.json').read_text())['device_credential'],'fixture-private')
        self.assertEqual((self.state/'source/local-note.txt').read_text(),'keep custom file')
        self.assertEqual(installed(self.state/'source'),self.latest['fingerprint'])

    def test_review_does_not_install_or_replace_source(self):
        self.prepare()
        with patch.object(worker,'build_opener') as opener,patch.object(worker.subprocess,'run') as run:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=self.data
            worker.update(self.state,self.sha,False)
            run.assert_not_called()
        self.assertEqual((self.state/'source/gateway/platforms.py').read_text(),'old source')

    def test_owner_status_reports_current_outdated_unknown_and_offline_without_secrets(self):
        app=Flask(__name__,root_path=str(ROOT))
        app.config.update(BUILD_ID='fixture-build',MESH_VERSION='fixture-version')
        def host(id,**extra):return {'id':id,'owner_id':'owner','trust_state':'verified','platform':'hermes','runtime':'Hermes',**extra}
        registry={'current':host('current',gateway_release={'fingerprint':self.latest['fingerprint']}),
            'old':host('old',gateway_release={'fingerprint':'0'*64}),
            'unknown':host('unknown'),'offline':host('offline'),
            'other':host('other',owner_id='other-owner'),'superseded':host('superseded',gateway_superseded=True),
            'child':host('child',control_center_gateway='current')}
        register_sync_routes(app,lambda f:f,lambda:'owner',registry,{'current':True,'old':True,'unknown':True},lambda:'https://mesh.example')
        client=app.test_client()
        response=client.get('/api/sync-updates')
        self.assertEqual(response.status_code,200)
        rows={r['id']:r for r in response.json['gateways']}
        self.assertEqual({k:r['state'] for k,r in rows.items()}, {'current':'current','old':'update_available','unknown':'unknown','offline':'offline'})
        self.assertIn(self.latest['helper_sha256'],rows['old']['prompt'])
        self.assertIn('--apply',rows['old']['prompt'])
        self.assertNotIn('device_credential',response.get_data(as_text=True))
        self.assertEqual(client.get('/sync-update').status_code,200)
        self.assertEqual(client.get('/api/distribution/platform/update-helper').status_code,200)
