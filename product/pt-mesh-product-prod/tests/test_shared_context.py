import json
import tempfile
import unittest
from pathlib import Path
from control_center.shared_context import read_context, context_path, mission_context
from control_center.office import engine, namespace


class SharedContextTests(unittest.TestCase):
    def test_notes_are_gateway_and_runtime_scoped(self):
        with tempfile.TemporaryDirectory() as home:
            p=context_path(home,'host','codex');p.parent.mkdir(parents=True);p.write_text(json.dumps({'text':'Reviewed result','author':'codex'}))
            self.assertEqual(read_context(home,'host','codex')['text'],'Reviewed result')
            self.assertEqual(read_context(home,'other','codex')['text'],'')
            self.assertEqual(read_context(home,'host','coder')['text'],'')
            self.assertRaises(ValueError,context_path,home,'host','../codex')
    def test_mission_results_follow_current_director_and_specialist_scope(self):
        with tempfile.TemporaryDirectory() as home:
            role=namespace('main','host')
            def call(op,args={}):return engine(home,role,op,args)
            call('runtime.sync',{'agents':[{'runtime_id':'codex','name':'Odexi','role':'Architect'},{'runtime_id':'coder','name':'Mak','role':'Developer'}],'bindings':{'orchestrator':'codex'}})
            task=call('task.create',{'title':'Report','description':'Brief','assignee':'','dependsOn':[],'needsApproval':False})['result']['id']
            call('begin',{'id':task});call('finish',{'id':task,'ok':True,'result':'Validated result'})
            self.assertIn('Validated result',mission_context(home,'host','main','codex'))
            self.assertEqual(mission_context(home,'host','main','coder'),'')
            self.assertEqual(mission_context(home,'other','main','codex'),'')
