import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from control_center.chatter_admission import resources, teaching, GiB

class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.mesh=SimpleNamespace(model=lambda a:a,api=lambda p:{'models':[{'name':'a','size':GiB},{'name':'b','size':GiB}]} if p=='tags' else {'models':[]})
        self.memory=SimpleNamespace(total=64*GiB,available=40*GiB)
        self.addCleanup(patch.stopall)
        patch('control_center.chatter_admission.psutil.virtual_memory',return_value=self.memory).start()
        patch('control_center.chatter_admission.psutil.swap_memory',return_value=SimpleNamespace(percent=0)).start()
        patch('control_center.chatter_admission.os.getloadavg',return_value=(0,0,0)).start()
        patch('control_center.chatter_admission.Path.glob',return_value=[]).start()
    def test_pair_weights_and_context_plus_reserve(self):
        self.assertTrue(resources(self.mesh,['a','b'])[0]);self.memory.available=8*GiB
        self.assertEqual(resources(self.mesh,['a','b']),(False,'Waiting for RAM headroom'))
    def test_cpu_pressure_and_unknown_model_defer(self):
        with patch('control_center.chatter_admission.os.getloadavg',return_value=(99999,0,0)):self.assertIn('CPU',resources(self.mesh,['a','b'])[1])
        self.mesh.model=lambda a:'missing';self.assertFalse(resources(self.mesh,['a','b'])[0])
    def test_missing_telemetry_fails_closed(self):
        self.mesh.api=lambda p: (_ for _ in ()).throw(OSError())
        self.assertIn('unavailable',resources(self.mesh,['a','b'])[1])
    def test_api_participant_does_not_require_ollama_telemetry(self):
        self.mesh.model=lambda a: (_ for _ in ()).throw(ValueError('local_preload_unavailable'))
        self.mesh.config=lambda a: ({},a,'openai/configured-model')
        self.mesh.api=lambda p: (_ for _ in ()).throw(AssertionError('API models have no local weights'))
        self.assertTrue(resources(self.mesh,['remote'])[0])
        self.memory.available=2*GiB
        self.assertIn('RAM',resources(self.mesh,['remote'])[1])

    def test_mixed_api_local_pair_preserves_local_weight_and_capacity_checks(self):
        self.mesh.model=lambda a: 'a' if a=='local' else (_ for _ in ()).throw(ValueError('local_preload_unavailable'))
        self.mesh.config=lambda a: ({},a,'openai/configured-model')
        self.assertTrue(resources(self.mesh,['local','remote'])[0])
        self.mesh.api=lambda p: (_ for _ in ()).throw(OSError())
        self.assertIn('unavailable',resources(self.mesh,['local','remote'])[1])

    def test_gpu_headroom_defer(self):
        with tempfile.TemporaryDirectory() as d:
            device=Path(d)
            for name,value in [('mem_info_vram_total',16*GiB),('mem_info_vram_used',15*GiB)]: (device/name).write_text(str(value))
            with patch('control_center.chatter_admission.Path.glob',return_value=[device]):self.assertEqual(resources(self.mesh,['a','b']),(False,'Waiting for GPU memory headroom'))
    def test_models_may_split_between_gpu_and_reserved_system_ram(self):
        self.mesh.api=lambda p:{'models':[{'name':'a','size':10*GiB},{'name':'b','size':10*GiB}]} if p=='tags' else {'models':[]}
        with tempfile.TemporaryDirectory() as d:
            device=Path(d)
            for name,value in [('mem_info_vram_total',16*GiB),('mem_info_vram_used',GiB)]: (device/name).write_text(str(value))
            with patch('control_center.chatter_admission.Path.glob',return_value=[device]):self.assertTrue(resources(self.mesh,['a','b'])[0])
    def test_small_gpu_reserve_allows_prepared_model_but_keeps_pressure_guards(self):
        with tempfile.TemporaryDirectory() as d:
            device=Path(d)
            (device/'mem_info_vram_total').write_text(str(2*GiB))
            (device/'mem_info_vram_used').write_text(str(2*GiB-320*1024**2))
            (device/'gpu_busy_percent').write_text('1')
            with patch('control_center.chatter_admission.Path.glob',return_value=[device]):
                self.assertTrue(resources(self.mesh,['a','b'])[0])
                (device/'gpu_busy_percent').write_text('90')
                self.assertEqual(resources(self.mesh,['a','b']),(False,'Waiting for GPU capacity'))
                (device/'gpu_busy_percent').write_text('1')
                (device/'mem_info_vram_used').write_text(str(2*GiB-128*1024**2))
                self.assertEqual(resources(self.mesh,['a','b']),(False,'Waiting for GPU memory headroom'))
    def test_memory_scope_and_attribution_before_limit(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'memory.db'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE memories(memory_id,title,content,author_id,provenance_ref,scope,status,project_id,author_type,created_at)')
                for ident,scope,author in [('private','private','reviewer'),('shared','project','reviewer'),('baseline','project','codex'),('other','project','designer')]:
                    db.execute('INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,ident,ident,author,'evidence',scope,'active','ProgreTech','agent',1))
            with patch('control_center.chatter_admission.database',return_value=path):
                rows,status=teaching(d,'reviewer');self.assertEqual({r['id'] for r in rows},{'shared','baseline'});self.assertIn('retrieved',status)
