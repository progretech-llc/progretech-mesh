import json
import tempfile
import unittest
from pathlib import Path
from control_center.gateway_roster import native_roster

class NativeRosterTests(unittest.TestCase):
    def test_roster_models_and_permissions_follow_current_config(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);(home/'.openclaw').mkdir()
            path=home/'.openclaw/openclaw.json'
            config={'agents':{'defaults':{'model':{'primary':'local/default','fallbacks':['local/small']}},
                'entries':{'lead.custom':{'name':'Custom lead','workspace':directory,'subagents':{'allowAgents':['worker','retired']}},
                           'worker':{'name':'Current worker','subagents':{'allowAgents':['worker']}}}}}
            path.write_text(json.dumps(config));rows=native_roster(home)
            self.assertEqual([r['id'] for r in rows],['lead.custom','worker'])
            self.assertTrue(rows[0]['controller']);self.assertEqual(rows[0]['delegation_targets'],['worker'])
            self.assertFalse(rows[1]['controller']);self.assertIsNone(rows[1]['workspace_ready'])
            self.assertEqual(rows[0]['model']['fallbacks'],['local/small'])
            self.assertTrue(rows[0]['workspace_ready']);self.assertIsNone(rows[0]['mail_identity'])
            del config['agents']['entries']['worker'];path.write_text(json.dumps(config))
            self.assertEqual(len(native_roster(home)),1);self.assertFalse(native_roster(home)[0]['controller'])

    def test_explicit_wildcard_only_targets_current_other_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);(home/'.openclaw').mkdir()
            (home/'.openclaw/openclaw.json').write_text(json.dumps({'agents':{
                'defaults':{'subagents':{'allowAgents':['*']}},'entries':{'main':{},'new-role':{},'bad/id':{}}}}))
            rows=native_roster(home)
            self.assertEqual([r['id'] for r in rows],['main','new-role'])
            self.assertTrue(all(r['controller'] for r in rows));self.assertEqual(rows[0]['mail_identity'],'rend')
