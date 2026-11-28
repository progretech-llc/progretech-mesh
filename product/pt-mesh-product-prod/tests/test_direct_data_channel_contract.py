import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class TestDirectDataChannelContract(unittest.TestCase):
 def setUp(self):
  self.plugin=(ROOT/'openclaw-plugin-progretech-mesh'/'index.js').read_text(); self.browser=(ROOT/'static/js/app.js').read_text(); self.server=(ROOT/'main.py').read_text(); self.pkg=json.loads((ROOT/'openclaw-plugin-progretech-mesh/package.json').read_text())
 def test_dependency(self): self.assertEqual(self.pkg['version'],'0.10.5-portable-host.2'); self.assertEqual(self.pkg['dependencies']['node-datachannel'],'0.33.3')
 def test_agent(self): self.assertIn('new rtc.PeerConnection',self.plugin); self.assertIn('peer.onDataChannel',self.plugin); self.assertIn('meshConversationBody(message,meshIdentity?.agent_id,"webrtc-direct")',self.plugin)
 def test_browser(self): self.assertIn('new RTCPeerConnection({iceServers:currentIceServers',self.browser); self.assertIn('peer.createDataChannel("progretech-mesh"',self.browser); self.assertIn('postDirectSignal(agentId,"offer"',self.browser)
 def test_message_prefers_direct(self): self.assertIn('if (directChannelReady())',self.browser); self.assertIn('cloud_data_path:false',self.browser)
 def test_signal_ephemeral(self): self.assertIn('mesh_direct_signal',self.server); self.assertIn('Never persist SDP/ICE or local access credentials',self.server)
 def test_no_frontend_stage_markers(self):
  joined='\n'.join(p.read_text(errors='ignore') for p in list((ROOT/'templates').glob('*.html'))+list((ROOT/'static/js').glob('*.js'))); self.assertIsNone(re.search(r'\bPhase\s+\d+\b|\bRev(?:ision)?\s+\d+\b',joined,re.I))
if __name__=='__main__': unittest.main()
