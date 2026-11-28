import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from control_center.host_paths import factory_tool
from control_center.mesh_runtime import role_controls
from control_center.media_jobs import record_activity


class HostPathsTests(unittest.TestCase):
    def test_canonical_helper_wins_and_legacy_only_falls_back_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp)
            for name in ('factory-workday','factory-memory-activity'):
                legacy=home/'Rend/bin'/name;legacy.parent.mkdir(parents=True,exist_ok=True);legacy.write_text('legacy')
                self.assertEqual(factory_tool(home,name),legacy)
                canonical=home/'ptinternal/bin'/name;canonical.parent.mkdir(parents=True,exist_ok=True);canonical.write_text('canonical')
                self.assertEqual(factory_tool(home,name),canonical)
            with self.assertRaises(ValueError):factory_tool(home,'../arbitrary')
    def test_controls_use_actual_canonical_helper_without_legacy_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);helper=home/'ptinternal/bin/factory-workday';helper.parent.mkdir(parents=True);helper.write_text('fixture')
            def run(command,**kwargs):
                self.assertEqual(command,[str(helper),'status'])
                return SimpleNamespace(returncode=0,stdout=json.dumps({'controls':[{'role':'rend','mode':'running','until':None}]}))
            with patch('control_center.mesh_runtime.subprocess.run',side_effect=run):
                self.assertEqual(role_controls(home,refresh=True)['rend']['mode'],'running')
            self.assertFalse((home/'Rend').exists())
    def test_image_activity_uses_canonical_memory_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);helper=home/'ptinternal/bin/factory-memory-activity';helper.parent.mkdir(parents=True);helper.write_text('fixture')
            def run(command,**kwargs):
                self.assertEqual(command[0],str(helper));self.assertEqual(command[1:3],['--agent','imagen'])
                return SimpleNamespace(returncode=0,stdout=json.dumps({'ok':True,'recall_verified':True,'memory_id':'fixture-id'}))
            with patch('control_center.media_jobs.subprocess.run',side_effect=run):
                self.assertEqual(record_activity(home,'imagen','owned',home/'published.png','digest','fixture')['status'],'saved-and-recalled')


if __name__=='__main__':unittest.main()
