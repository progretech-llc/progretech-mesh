"""Both Mesh front ends must ship the common memory surface and controls."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class ReleaseParityTests(unittest.TestCase):
    def test_release_version_matches_all_hosted_and_local_entrypoints(self):
        version=json.loads((ROOT/'mesh-release.json').read_text())['version']
        for name in ('main.py','cloudbuild.yaml','scripts/deploy-cloud-run.sh'):
            self.assertIn(version,(ROOT/name).read_text(),name)

    def test_shared_memory_ui_shipped_to_every_surface(self):
        for name in ('index','office','offline','control_center'):
            self.assertIn('/static/js/agent-memory.js',(ROOT/f'templates/{name}.html').read_text())
        desktop=(ROOT/'offline/app.py').read_text()
        self.assertIn("'/api/agents/<aid>/management'",desktop)
        self.assertIn("'memory.status'",desktop)
    def test_local_web_uses_same_owner_actions_and_release_source(self):
        source=(ROOT/'main.py').read_text()
        self.assertIn("MESH_LOCAL_CONTROL_CENTER",source)
        self.assertIn('GATEWAY_SOCKETS, management_send',source)
        installer=(ROOT/'scripts/install-local-release.py').read_text()
        self.assertIn('DEV_SEED_AGENTS=0',installer)
        self.assertIn('BUILD_ID={commit[:7]}',installer)

    def test_factory_features_and_shared_status_are_in_every_release(self):
        office=(ROOT/'templates/office.html').read_text()
        for control in ('officeChatter','chatterMinutes','chatterConcurrency','chatterGroup','floorNodes'):
            self.assertIn(control,office)
        for page in ('index','office'):
            self.assertIn('runtime-client.js',(ROOT/f'templates/{page}.html').read_text())
        self.assertIn('MeshRuntime.unifiedOffice', (ROOT/'static/js/office.js').read_text())
        self.assertIn('MeshRuntime.terminalDirection', (ROOT/'static/js/app.js').read_text())

    def test_factory_status_avatar_and_proximity_contract(self):
        office=(ROOT/'static/js/office.js').read_text()
        fleet=(ROOT/'static/js/app.js').read_text()
        css=(ROOT/'static/css/office.css').read_text()
        avatars=(ROOT/'static/js/avatars.js').read_text()
        self.assertIn('MeshRuntime.workLabel',office)
        self.assertIn('MeshRuntime.workLabel',fleet)
        self.assertIn('chatterEligible',office)
        self.assertIn("binding.startsWith(host()+'--')",office)
        self.assertIn('first===second',office)
        self.assertIn('d<90',office)
        self.assertNotIn("chatter?.enabled&&id.startsWith('factory-')",office)
        self.assertIn('.floor-node.working,.floor-node.busy{color:#6fb7ff}',css)
        self.assertIn('.floor-node.sleeping,.floor-node.offline{color:#8198aa',css)
        self.assertIn('.floor-link.instruction{stroke:#62d6ed;stroke-dasharray:none}',css)
        self.assertIn('.floor-link.conversation{stroke:#b38cf3;stroke-dasharray:3 6}',css)
        self.assertIn('agent?.native?.runtime_id',avatars)
        self.assertIn('moxy.png?v=2',avatars)
