import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from control_center.office import dispatch_office

class ImagenFloorTests(unittest.TestCase):
    def test_configured_imagen_without_fabricated_activity(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);config=home/'.openclaw/openclaw.json';config.parent.mkdir()
            config.write_text(json.dumps({'agents':{'entries':{'imagen':{'name':'Imagen'}}}}))
            with patch('control_center.office.engine',return_value={'snapshot':{'agents':[]}}),patch('control_center.mesh_runtime.role_controls',return_value={}),patch('control_center.memory_status.memory_status',return_value={}):
                result=dispatch_office(home,'main',{'operation':'snapshot','args':{}})
            rows=result['snapshot']['factoryAgents'];self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['id'],'imagen');self.assertEqual(rows[0]['runtime_id'],'imagen')
            self.assertEqual(rows[0]['state'],'unknown');self.assertIsNone(rows[0]['sleeping']);self.assertNotIn('task_id',rows[0])
    def test_absent_inventory_does_not_invent_imagen(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('control_center.office.engine',return_value={'snapshot':{'agents':[]}}),patch('control_center.mesh_runtime.role_controls',return_value={}):
                result=dispatch_office(directory,'main',{'operation':'snapshot','args':{}})
            self.assertEqual(result['snapshot']['factoryAgents'],[])

    def test_new_configured_role_appears_without_inventing_work(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);config=home/'.openclaw/openclaw.json';config.parent.mkdir()
            config.write_text(json.dumps({'agents':{'entries':{'codex':{'name':'Odexi'}}}}))
            with patch('control_center.office.engine',return_value={'snapshot':{'agents':[]}}),patch('control_center.mesh_runtime.role_controls',return_value={}),patch('control_center.memory_status.memory_status',return_value={}):
                result=dispatch_office(home,'main',{'operation':'snapshot','args':{}})
            row=result['snapshot']['factoryAgents'][0]
            self.assertEqual(row['runtime_id'],'codex');self.assertEqual(row['state'],'unknown')
