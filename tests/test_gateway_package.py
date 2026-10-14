import hashlib, json, re, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class GatewayPackageTests(unittest.TestCase):
 def test_published_package_is_consistent(self):
  index=json.loads((ROOT/'distribution/openclaw-plugin-index.json').read_text())
  package=json.loads((ROOT/'openclaw-plugin-progretech-mesh/package.json').read_text())
  self.assertEqual(index['version'],package['version'])
  main=(ROOT/'main.py').read_text()
  self.assertIn('OPENCLAW_PLUGIN_PACKAGE_VERSION = "'+index['version']+'"', main)
  self.assertIn('OPENCLAW_PLUGIN_PACKAGE_FILENAME = "'+index['filename']+'"', main)
  self.assertEqual(hashlib.sha256((ROOT/'distribution'/index['filename']).read_bytes()).hexdigest(),index['sha256'])
  for name in ['agent-adapter-catalog-v1.json','openclaw-self-bootstrap-plan-v1.json']:
   def check(obj):
    if isinstance(obj,dict):
     if obj.get('package_id')==index['package_id']:
      self.assertEqual(obj['version'],index['version']);self.assertEqual(obj['sha256'],index['sha256'])
      if 'filename' in obj:self.assertEqual(obj['filename'],index['filename'])
     for value in obj.values():check(value)
    elif isinstance(obj,list):
     for value in obj:check(value)
   check(json.loads((ROOT/'distribution'/name).read_text()))
 def test_published_adapter_contains_current_control_protocol(self):
  import tarfile
  index=json.loads((ROOT/'distribution/openclaw-plugin-index.json').read_text())
  with tarfile.open(ROOT/'distribution'/index['filename']) as archive:
   for filename in ['control-center.js','ide-client.js','index.js','package.json']:
    self.assertEqual(archive.extractfile('package/'+filename).read(),(ROOT/'openclaw-plugin-progretech-mesh'/filename).read_bytes())
