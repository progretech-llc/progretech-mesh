import time
import unittest
from unittest.mock import patch
import test_factory_handoffs as fixtures
from control_center.handoffs import Handoffs


class ChatterTabLeaseTests(unittest.TestCase):
    setUp=fixtures.HandoffTests.setUp
    # Reuse the fixture without re-running its inherited behavioral tests.
    def test_enable_requires_explicit_tab_and_status_does_not_enable(self):
        for tab in [None,'',4,'x'*32]:
            args={'enabled':True}
            if tab is not None:args['tab_id']=tab
            with self.assertRaises(ValueError):self.h.dispatch('host','chatter.configure',args)
        self.h.dispatch('host','handoff.list',{});self.h.chatter_tick()
        self.assertFalse(self.h.data['chatter']['enabled']);self.assertFalse(self.mesh.calls)

    def test_expiry_stops_queued_and_requests_active_cancellation(self):
        cancelled=[];self.mesh.cancel_background=cancelled.append
        self.h.dispatch('host','chatter.configure',{'enabled':True,'tab_id':'a'*32})
        self.h.chatter_tick();row=self.h.data['chatter']['conversations'][0]
        row['approach_until']=0;self.h.chatter_tick()
        self.assertEqual(len(self.mesh.calls),1)
        self.h.chatter_session['expires']=time.monotonic()-1
        self.h.chatter_tick()
        self.assertFalse(self.h.data['chatter']['enabled']);self.assertEqual(row['state'],'stopped')
        self.assertEqual(cancelled,[row['id']]);self.assertEqual(len(self.mesh.calls),1)
        with self.assertRaisesRegex(ValueError,'chatter_tab_expired'):
            self.h.dispatch('host','chatter.configure',{'enabled':True,'renew_only':True,'tab_id':'a'*32})

    def test_only_enabling_tab_can_renew_and_old_tab_cannot_disable_new_tab(self):
        self.h.dispatch('host','chatter.configure',{'enabled':True,'tab_id':'a'*32})
        with self.assertRaisesRegex(ValueError,'chatter_tab_expired'):
            self.h.dispatch('host','chatter.configure',{'enabled':True,'renew_only':True,'tab_id':'b'*32})
        with self.assertRaisesRegex(ValueError,'chatter_tab_expired'):
            self.h.dispatch('host--progre','chatter.configure',{'enabled':True,'renew_only':True,'tab_id':'a'*32})
        self.h.chatter_session['expires']=time.monotonic()+1
        self.h.dispatch('host','chatter.configure',{'enabled':True,'renew_only':True,'tab_id':'a'*32})
        self.assertGreater(self.h.chatter_session['expires'],time.monotonic()+29)
        self.h.dispatch('host','chatter.configure',{'enabled':True,'tab_id':'b'*32})
        self.h.dispatch('host','chatter.configure',{'enabled':False,'tab_id':'a'*32})
        self.assertTrue(self.h.data['chatter']['enabled'])
        self.h.dispatch('host','chatter.configure',{'enabled':False,'tab_id':'b'*32})
        self.assertFalse(self.h.data['chatter']['enabled'])

    def test_restart_preserves_settings_but_never_restores_consent(self):
        self.h.dispatch('host','chatter.configure',{'enabled':True,'tab_id':'a'*32,'session_minutes':42})
        restored=Handoffs(self.provider,self.home,self.mesh)
        self.assertFalse(restored.data['chatter']['enabled']);self.assertIsNone(restored.chatter_session)
        self.assertEqual(restored.data['chatter']['session_minutes'],42)
        restored.chatter_tick();self.assertFalse(self.mesh.calls)
