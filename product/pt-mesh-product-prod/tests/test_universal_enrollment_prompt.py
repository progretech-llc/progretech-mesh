import ast, json, re, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class TestUniversalEnrollmentPrompt(unittest.TestCase):
    def setUp(self):
        self.source=(ROOT/'main.py').read_text(encoding='utf-8')

    def test_prompt_is_self_describing(self):
        for required in (
            'PROGRETECH MESH AGENT ENROLLMENT',
            "Decode the text after 'PTM1:' as unpadded Base64URL JSON",
            'read the protocol contract:',
            'read the runtime adapter catalog:',
            'No ProgreTech software is assumed to be preinstalled',
            '--- BEGIN PROGRETECH MESH ENROLLMENT ---',
            '--- END PROGRETECH MESH ENROLLMENT ---',
        ):
            self.assertIn(required.lower(),self.source.lower())

    def test_response_exposes_raw_payload_and_discovery(self):
        self.assertIn('enrollment_payload=ptm1', self.source)
        self.assertIn('protocol_url=protocol_url', self.source)
        self.assertIn('adapter_catalog_url=catalog_url', self.source)
        self.assertIn('preinstalled_progretech_component_required=False', self.source)

    def test_no_broken_old_wrapper(self):
        self.assertNotIn('mode and keep You are being asked', self.source)

    def test_protocol_is_zero_preinstall(self):
        p=json.loads((ROOT/'distribution/universal-agent-enrollment-v1.json').read_text())
        self.assertFalse(p['principles']['preinstalled_progretech_component_required'])
        self.assertFalse(p['entrypoint']['preinstalled_progretech_component_required'])
        self.assertFalse(p['entrypoint']['prior_mesh_knowledge_required'])
        self.assertIn('unpadded RFC 4648 Base64URL',p['entrypoint']['ptm1_encoding'])

    def test_send_instructions_have_no_trusted_bootstrap_prerequisite(self):
        s=(ROOT/'SEND_THIS_TO_REND.txt').read_text().lower()
        self.assertIn('no zip transfer',s)
        self.assertIn('no mesh component', (ROOT/'docs/AGENT_LED_ENROLLMENT.md').read_text().lower())
        self.assertNotIn('trusted enrollment bootstrap will',s)

    def test_prompt_bounds_runtime_discovery_and_retries(self):
        required=(
            'Do NOT recursively inspect framework internals',
            'Run at most one probe per available adapter and at most three probes total',
            'Select exactly one available adapter',
            'Retry a failed step at most once',
            'If not connected within 10 minutes of active work, STOP',
        )
        for item in required:
            self.assertIn(item,self.source)
        self.assertNotIn('Inspect your own runtime and available local capabilities', self.source)

    def test_protocol_and_catalog_are_bounded(self):
        protocol=json.loads((ROOT/'distribution/universal-agent-enrollment-v1.json').read_text())
        self.assertEqual(protocol['time_budget']['hard_stop_seconds'],600)
        self.assertEqual(protocol['retry_policy']['per_step_max_retries'],1)
        self.assertFalse(protocol['principles']['recursive_self_inspection_allowed'])
        catalog=json.loads((ROOT/'distribution/agent-adapter-catalog-v1.json').read_text())
        self.assertFalse(catalog['contract']['recursive_runtime_inspection_allowed'])
        available=[a for a in catalog['adapters'] if a.get('status')=='available']
        self.assertTrue(available)
        for adapter in available:
            self.assertIn('names', adapter['runtime_match'])
            self.assertIn('identification_probes', adapter['runtime_match'])

    def test_openclaw_plan_bounds_activation_handoff(self):
        plan=json.loads((ROOT/'distribution/openclaw-self-bootstrap-plan-v1.json').read_text())
        self.assertEqual(plan['time_budget']['hot_safe_install_max_seconds'],60)
        self.assertEqual(plan['time_budget']['post_install_connection_check_max_seconds'],60)
        self.assertIn('PTM1 mesh field', plan['activation_handoff']['authoritative_mesh_target'])
        self.assertIn('127.0.0.1:18789', plan['activation_handoff']['authoritative_mesh_target'])
        self.assertEqual(plan['activation_handoff']['pending_state_file'],'~/.progretech-mesh/pending-enrollment.json')

    def test_helper_uses_hot_safe_install_without_idle_wait(self):
        helper=(ROOT/'distribution/openclaw-self-bootstrap-v1.sh').read_text()
        self.assertIn('hot-safe managed installation', helper)
        self.assertNotIn('max_attempts=12', helper)
        self.assertNotIn('deferred_until_idle', helper)

if __name__=='__main__': unittest.main()
