import unittest
from mesh_presence import observed_state

class PresenceTests(unittest.TestCase):
    def test_activity_expires_even_with_fresh_heartbeat(self):
        row={'state':'working','activity':{'observed_at':'2026-10-08T12:00:00+00:00'},'last_heartbeat':1791460800}
        at=1791460800
        self.assertEqual(observed_state(row,at),'working')
        self.assertEqual(observed_state(row,at+181),'unknown')
        row['last_heartbeat']=at+181
        self.assertEqual(observed_state(row,at+181),'unknown')
    def test_missing_invalid_future_and_naive_evidence_fail_unknown(self):
        for at in (None,'bad',float('nan'),2000,'2026-10-08T12:00:00'):
            self.assertEqual(observed_state({'state':'working','activity':{'observed_at':at}},1000),'unknown')
    def test_live_standalone_and_idle(self):
        self.assertEqual(observed_state({'state':'working','last_heartbeat':990},1000),'working')
        self.assertEqual(observed_state({'state':'idle'},1000),'idle')
