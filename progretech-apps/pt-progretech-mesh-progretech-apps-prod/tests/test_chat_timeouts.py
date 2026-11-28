import unittest
from unittest.mock import patch, MagicMock
from mesh_control_center import ControlRelay

class ChatTimeoutTests(unittest.TestCase):
    def test_chat_has_longer_budget_without_extending_other_actions(self):
        relay=ControlRelay(timeout=45,chat_timeout=320)
        for action,timeout in [('communication.chat',320),('communication.get',45)]:
            event=MagicMock();event.wait.return_value=False
            with patch('mesh_control_center.threading.Event',return_value=event):
                result,status=relay.dispatch('host--coder',action,{},lambda *a:(True,None),'host')
            event.wait.assert_called_once_with(timeout)
            self.assertEqual(status,504);self.assertEqual(relay.pending,{})
