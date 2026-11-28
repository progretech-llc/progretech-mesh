import tempfile
import unittest
from pathlib import Path
from store import Store

class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'chat.db')
    def tearDown(self): self.store.db.close();self.tmp.cleanup()
    def add(self,key='one',**kw):
        return self.store.append(event_key=key,agent=kw.pop('agent','main'),origin='mesh',session='a',speaker='user',text=kw.pop('text','hello'),**kw)
    def test_restart_idempotency(self):
        a=self.add();self.store.db.close();self.store=Store(Path(self.tmp.name)/'chat.db')
        self.assertEqual(a,self.add());self.assertEqual(len(self.store.history('rend')),1)
    def test_identity_isolation(self):
        self.add();self.add('two',agent='imagen');self.assertEqual(len(self.store.history('main')),1)
        self.assertEqual(self.store.history('coder'),[])
    def test_context_excludes_own_session_and_other_project(self):
        self.add();self.add('product',project='SecretProduct',text='other project')
        self.assertEqual(self.store.context('main','a'),'')
        self.assertNotIn('other project',self.store.context('main','b'))
        self.assertIn('hello',self.store.context('main','b'))
    def test_delivery_crash_never_replays(self):
        seq=self.add();self.assertTrue(self.store.claim(seq,'telegram',0));self.assertFalse(self.store.claim(seq,'telegram',0))
        self.store.receipt(seq,'telegram',0,'uncertain');self.assertFalse(self.store.claim(seq,'telegram',0))
    def test_attachment_metadata_only(self):
        self.add(text='Generated file: /mnt/pt-context/deliverables/task/image.png')
        with self.assertRaises(ValueError):self.add('bytes',text='data:image/png;base64,abc')
    def test_task_changes_do_not_replay_old_tasks(self):
        snapshot={'agents':[{'id':'rend','runtime_id':'main'}],'tasks':[{'id':'task-1','assignee':'rend','title':'Fixture task','status':'todo'}]}
        self.assertEqual(self.store.observe_tasks('office',snapshot),0)
        snapshot['tasks'][0]['status']='done';snapshot['tasks'][0]['result']='Output: /mnt/pt-context/deliverables/test/result.txt'
        self.assertEqual(self.store.observe_tasks('office',snapshot),1)
        self.assertEqual(self.store.observe_tasks('office',snapshot),0)
        self.assertIn('done',self.store.history('main')[0]['text'])
    def test_media_directives_become_paths_without_embeds(self):
        self.add(text='MEDIA:/mnt/pt-context/deliverables/a.png\n![picture](/mnt/pt-context/deliverables/b.png)')
        text=self.store.history('main')[0]['text']
        self.assertNotIn('MEDIA:',text);self.assertNotIn('![',text);self.assertIn('/mnt/pt-context/deliverables/a.png',text)
    def test_cursor_ascending_no_gaps(self):
        for i in range(6):self.add(str(i))
        first=self.store.history('main',limit=2,latest=False)
        rest=self.store.history('main',after=first[-1]['seq'],limit=4,latest=False)
        self.assertEqual([r['seq'] for r in first+rest],list(range(1,7)))

if __name__=='__main__': unittest.main()
