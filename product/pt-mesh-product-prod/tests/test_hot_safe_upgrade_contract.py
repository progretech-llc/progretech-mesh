import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class TestHotSafeUpgradeContract(unittest.TestCase):
    def test_prompt_does_not_create_idle_deadlock(self):
        s=(ROOT/'main.py').read_text()
        self.assertIn('declared hot-safe managed adapter install may proceed during this enrollment turn', s)
        self.assertIn('do not wait for generic idle', s.lower())
        self.assertNotIn('STOP and report deferred_until_idle rather than waiting or forcing it', s)

    def test_openclaw_plan_is_hot_safe_no_restart(self):
        p=json.loads((ROOT/'distribution/openclaw-self-bootstrap-plan-v1.json').read_text())
        self.assertTrue(p['safety_contract']['hot_safe_managed_install_during_enrollment'])
        self.assertFalse(p['safety_contract']['automatic_runtime_restart_allowed'])
        ids=[x['id'] for x in p['agent_procedure']]
        self.assertNotIn('wait_for_idle', ids)
        install=next(x for x in p['agent_procedure'] if x['id']=='install')
        self.assertFalse(install['requires_idle'])
        self.assertFalse(install['restart_allowed'])
        self.assertNotIn('idle_wait_max_seconds', p['time_budget'])
        self.assertIn('activation_reload_required', p['activation_handoff']['restart_rule'])

    def test_helper_has_no_idle_wait_or_restart(self):
        h=(ROOT/'distribution/openclaw-self-bootstrap-v1.sh').read_text()
        self.assertNotIn('max_attempts=12', h)
        self.assertNotIn('deferred_until_idle', h)
        self.assertIn('hot-safe managed installation', h)
        self.assertNotIn('gateway restart', h.lower())

    def test_catalog_declares_no_automatic_restart(self):
        c=json.loads((ROOT/'distribution/agent-adapter-catalog-v1.json').read_text())
        a=next(x for x in c['adapters'] if x['id']=='openclaw')
        self.assertFalse(a['installation']['requires_runtime_restart'])
        self.assertTrue(a['installation']['hot_safe_managed_install_during_enrollment'])

if __name__=='__main__': unittest.main()
