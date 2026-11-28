import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from control_center.mesh_runtime import MeshRuntime


class ChatterScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.runtime=MeshRuntime.__new__(MeshRuntime)
        self.runtime.home=Path(self.temp.name)
        self.runtime.provider=SimpleNamespace(bindings={'host':'main','host--mak':'coder','host--lyra':'researcher'})
        self.runtime.lock=threading.RLock();self.runtime.inference=threading.Lock();self.runtime.jobs={}
    def test_live_workday_and_mesh_jobs_block_only_the_same_runtime(self):
        file=self.runtime.home/'.local/state/progretech-workday/activity.json'
        file.parent.mkdir(parents=True)
        file.write_text(json.dumps({'agents':{'mak':{'state':'active'},'lyra':{'state':'idle'}}}))
        self.assertTrue(self.runtime.participant_busy('host--mak'))
        self.assertFalse(self.runtime.participant_busy('host--lyra'))
        self.runtime.jobs={'owner':{'agent_id':'host--lyra','done':False}}
        self.assertTrue(self.runtime.participant_busy('host--lyra'))
        self.assertFalse(self.runtime.participant_busy('host--lyra','owner'))
    def test_background_dispatch_has_no_global_native_idle_gate(self):
        self.runtime.chat_sleeping=lambda agent:False
        self.runtime.idle=lambda:False
        self.runtime.signal=lambda *args:None
        accepted=threading.Event()
        job=self.runtime.start('host--lyra','chat',lambda ident:accepted.set() or {'reply':'Observed'},background='consented-conversation')
        self.assertTrue(accepted.wait(2),'Unrelated native activity must not block an admitted idle participant')
        deadline=time.monotonic()+2
        while not self.runtime.get('host--lyra',job['job_id'])['done'] and time.monotonic()<deadline:time.sleep(.01)
        self.assertFalse(self.runtime.get('host--lyra',job['job_id']).get('error'))
