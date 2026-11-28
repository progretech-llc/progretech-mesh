import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class TestActivationLifecycleAndReconnectFastPath(unittest.TestCase):
    def setUp(self):
        self.main=(ROOT/'main.py').read_text(encoding='utf-8')
        self.js=(ROOT/'static/js/app.js').read_text(encoding='utf-8')
        self.protocol=(ROOT/'distribution/universal-agent-enrollment-v1.json').read_text(encoding='utf-8')

    def test_activation_has_no_normal_time_expiry(self):
        self.assertNotIn('ACTIVATION_CODE_TTL_SECONDS', self.main)
        self.assertIn('"lifecycle": "until_cancelled_or_redeemed"', self.main)
        self.assertIn('activation_lifecycle="until_cancelled_or_redeemed"', self.main)
        self.assertNotIn('activation_code_expired', self.main)

    def test_existing_active_request_is_reused(self):
        self.assertIn('and not existing.get("cancelled")', self.main)
        self.assertIn('return existing', self.main)
        self.assertNotIn('ACTIVATION_CODES.pop(existing_code, None)', self.main)

    def test_user_cancel_is_authoritative(self):
        self.assertIn('activation["cancelled"] = True', self.main)
        self.assertIn('activation_code_cancelled', self.main)
        self.assertIn('activation["cancelled_at"] = unix_now()', self.main)

    def test_pwa_has_status_not_countdown_and_persists_active_request(self):
        self.assertIn('Active until cancelled or connected', self.js)
        self.assertIn('mesh-active-enrollment-v1', self.js)
        self.assertIn('persistActiveEnrollment()', self.js)
        self.assertIn('restorePersistedEnrollment()', self.js)
        self.assertNotIn('server_clock_offset_seconds', self.js)
        self.assertNotIn('Request expired', self.js)

    def test_existing_installation_fast_path_is_in_prompt(self):
        required=(
            'FIRST check whether a ProgreTech Mesh adapter is already installed',
            'A fast-path adapter is compatible only when its runtime matches',
            'If a valid reconnect credential exists with such a current compatible adapter, connect immediately with it',
            'If a current compatible adapter is installed but its reconnect credential is missing/expired/revoked',
            'If an older Mesh adapter is installed, it is NOT eligible for this fast path',
            'perform one bounded in-place upgrade to plugin_package.version',
            'If activation validation fails for cancellation, replay/use, signature, audience/agent mismatch, or policy rejection, STOP immediately',
        )
        for text in required:
            self.assertIn(text,self.main)

    def test_pwa_remembers_only_pairing_metadata_not_device_credential(self):
        self.assertIn('mesh-paired-agents-v1', self.js)
        self.assertIn('last_connected_at', self.js)
        self.assertNotIn('device_credential', self.js)

if __name__=='__main__': unittest.main()
