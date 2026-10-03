import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import openhands_server
from store import Store

class State:
    execution_status='finished'
    def __init__(self):self.events={}
    def __enter__(self):return self
    def __exit__(self,*args):pass
class DisplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db'
        self.conversation=SimpleNamespace(id='test',agent=SimpleNamespace(_session_id='own'),state=State())
        self.conversation._on_event=lambda e:self.conversation.state.events.update({e.id:e})
        self.patch=patch.object(openhands_server,'Store',lambda:Store(self.path));self.patch.start()
        self.role=patch.object(openhands_server,'role_for',return_value='main');self.role.start()
    def tearDown(self):self.patch.stop();self.role.stop();self.tmp.cleanup()
    def test_display_does_not_execute_or_change_state(self):
        db=Store(self.path);db.append('first','main','mesh','remote','user','hello');db.db.close()
        self.assertEqual(openhands_server.project_events(self.conversation)['mirrored'],1)
        event=next(iter(self.conversation.state.events.values()))
        self.assertEqual(event.llm_message.role,'assistant')
        self.assertEqual(self.conversation.state.execution_status,'finished')
        self.assertEqual(openhands_server.project_events(self.conversation)['mirrored'],0)
    def test_busy_and_own_messages_are_not_injected(self):
        db=Store(self.path);db.append('own','main','openhands','agent:main:factory-api:ProgreTech:own','user','hello');db.db.close()
        self.assertEqual(openhands_server.project_events(self.conversation)['mirrored'],0)
        self.conversation.state.execution_status='running'
        self.assertTrue(openhands_server.project_events(self.conversation)['busy'])

if __name__=='__main__':unittest.main()
