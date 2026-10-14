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
    def test_attachment_card_only_in_the_originating_conversation(self):
        root=Path(self.tmp.name)/'deliverables';root.mkdir();file=root/'result.txt';file.write_text('fixture')
        db=Store(self.path);db.append('output','main','openhands','agent:main:factory-api:ProgreTech:own','assistant','File: '+str(file));db.db.close()
        with patch.object(openhands_server,'DELIVERABLE_ROOT',root):
            self.assertEqual(openhands_server.project_events(self.conversation)['mirrored'],1)
        event=next(iter(self.conversation.state.events.values()))
        self.assertEqual(event.sender,'origin-attachments')
        self.assertIn('#progretech-file=',event.llm_message.content[0].text)
        self.conversation.id='another';self.conversation.agent._session_id='other';self.conversation.state=State()
        self.assertEqual(openhands_server.project_events(self.conversation)['mirrored'],1)
        event=next(iter(self.conversation.state.events.values()))
        self.assertEqual(event.sender,'conversation-sync');self.assertNotIn('#progretech-file=',event.llm_message.content[0].text)
    def test_attachment_traversal_and_symlink_refused(self):
        root=Path(self.tmp.name)/'deliverables';root.mkdir();secret=Path(self.tmp.name)/'outside.txt';secret.write_text('fixture')
        (root/'link.txt').symlink_to(secret)
        with patch.object(openhands_server,'DELIVERABLE_ROOT',root):
            self.assertEqual(openhands_server.origin_files(str(root/'link.txt')),[])
            self.assertEqual(openhands_server.origin_files(str(root/'../outside.txt')),[])
    def test_only_verified_images_receive_previews(self):
        from PIL import Image
        root=Path(self.tmp.name)/'deliverables';root.mkdir()
        valid=root/'valid.png';Image.new('RGB',(2,2),'blue').save(valid)
        invalid=root/'invalid.png';invalid.write_text('not an image')
        with patch.object(openhands_server,'DELIVERABLE_ROOT',root):
            content=openhands_server.origin_files(str(valid))
            self.assertEqual(len(content),2)
            self.assertTrue(content[1].image_urls[0].startswith('data:image/png;base64,'))
            self.assertEqual(len(openhands_server.origin_files(str(invalid))),1)
    def test_empty_and_oversized_files_are_excluded(self):
        root=Path(self.tmp.name)/'deliverables';root.mkdir()
        empty=root/'empty.txt';empty.touch()
        large=root/'large.txt'
        with large.open('wb') as stream:stream.truncate(10*1024*1024+1)
        with patch.object(openhands_server,'DELIVERABLE_ROOT',root):
            self.assertEqual(openhands_server.origin_files(str(empty)+' '+str(large)),[])
    def test_busy_and_own_messages_are_not_injected(self):
        db=Store(self.path);db.append('own','main','openhands','agent:main:factory-api:ProgreTech:own','user','hello');db.db.close()
        self.assertEqual(openhands_server.project_events(self.conversation)['mirrored'],0)
        self.conversation.state.execution_status='running'
        self.assertTrue(openhands_server.project_events(self.conversation)['busy'])

if __name__=='__main__':unittest.main()
