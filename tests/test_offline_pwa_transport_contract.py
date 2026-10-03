import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class TestOfflinePwaTransport(unittest.TestCase):
 def setUp(self):
  self.main=(ROOT/'main.py').read_text(); self.js=(ROOT/'static/js/app.js').read_text(); self.sw=(ROOT/'static/sw.js').read_text(); self.plugin=(ROOT/'openclaw-plugin-progretech-mesh/index.js').read_text(); self.how=(ROOT/'templates/how_it_works.html').read_text(); self.pkg=json.loads((ROOT/'openclaw-plugin-progretech-mesh/package.json').read_text())
 def test_local_agent_signaling(self):
  self.assertIn('LOCAL_SIGNAL_PORT',self.plugin); self.assertIn('/mesh-local/signal',self.plugin); self.assertIn('/mesh-local/signals',self.plugin); self.assertIn('local_access_token',self.plugin)
 def test_local_metadata_ephemeral(self):
  self.assertIn('mesh_local_route',self.main); self.assertIn('Never persist SDP/ICE or local access credentials',self.main)
 def test_pwa_lna(self):
  self.assertIn('targetAddressSpace:"local"',self.js); self.assertIn('navigator.permissions.query({name:"local-network"})',self.js); self.assertIn('findReachableLocalRoute',self.js)
 def test_offline_shell_no_operational_cache(self):
  self.assertIn('url.pathname.startsWith("/api/")',self.sw); self.assertIn('url.pathname.startsWith("/ws/")',self.sw); self.assertIn('progretech-mesh-shell-v13-all-avatars',self.sw); self.assertIn('url.pathname.startsWith("/agents/")',self.sw)
 def test_how_it_works(self):
  for value in ('Same network','Different networks','Restrictive networks','Direct only','Offline PWA behavior'): self.assertIn(value,self.how)
 def test_acceptance_surface(self): self.assertIn('/api/transport/acceptance',self.main); self.assertIn('offline_same_lan_reconnect',self.main)
 def test_version(self): self.assertEqual(self.pkg['version'],'0.10.1-continuity.1')
 def test_no_frontend_stage_markers(self):
  joined='\n'.join(p.read_text(errors='ignore') for p in list((ROOT/'templates').glob('*.html'))+list((ROOT/'static/js').glob('*.js'))); self.assertIsNone(re.search(r'\bPhase\s+\d+\b|\bRev(?:ision)?\s+\d+\b',joined,re.I))
if __name__=='__main__': unittest.main()
