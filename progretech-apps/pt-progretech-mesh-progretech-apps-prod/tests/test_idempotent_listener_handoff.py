import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class TestIdempotentListenerHandoff(unittest.TestCase):
    def test_plugin_handles_eaddrinuse_with_authenticated_mesh_probe(self):
        s=(ROOT/'openclaw-plugin-progretech-mesh/index.js').read_text()
        self.assertIn('probeExistingMeshLocalServer',s)
        self.assertIn('error?.code !== "EADDRINUSE"',s)
        self.assertIn('/mesh-local/status',s)
        self.assertIn('X-Mesh-Local-Token',s)
        self.assertIn('reused_existing_mesh_listener',s)
        self.assertIn('port_conflict',s)
        self.assertNotIn('process.kill',s)
    def test_plan_declares_ownership_aware_reuse(self):
        p=json.loads((ROOT/'distribution/openclaw-self-bootstrap-plan-v1.json').read_text())
        self.assertIn('local_signal_port_in_use',p['failure_behavior'])
        self.assertIn('reuse',p['failure_behavior']['local_signal_port_in_use'].lower())
        c=json.loads((ROOT/'distribution/agent-adapter-catalog-v1.json').read_text())
        a=c['adapters'][0]
        self.assertTrue(a['lifecycle']['ownership_aware_port_reuse'])
        self.assertIn('port_conflict',a['installation']['stable_listener_handoff'])
if __name__=='__main__': unittest.main()
