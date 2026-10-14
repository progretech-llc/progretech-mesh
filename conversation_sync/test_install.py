import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import install


class InstallPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home'
        self.evidence = self.root / 'evidence'
        self.evidence.mkdir()
        self.runtime = self.home / '.openclaw/openclaw.json'
        self.runtime.parent.mkdir(parents=True)
        self.runtime.write_text('{"agents":{"entries":{}},"bindings":[]}')
        self.original = self.runtime.read_bytes()
        self.sdk = self.home / '.local/share/uv/tools/openhands-agent-server/lib/python3.12/site-packages'
        self.canvas = self.home / '.local/share/progretech-openhands/node_modules/@openhands/agent-canvas'
        self.addCleanup(self.tmp.cleanup)
        for p in [patch.object(install, 'HOME', self.home),
                  patch.object(install, 'ARTIFACT_ROOT', self.root),
                  patch.object(install.os.path, 'ismount', return_value=True)]:
            p.start()
            self.addCleanup(p.stop)

    def assert_untouched(self):
        self.assertEqual(self.runtime.read_bytes(), self.original)
        self.assertFalse((self.home / '.openclaw/extensions').exists())
        self.assertFalse((self.evidence / 'private-backup').exists())

    def test_missing_sdk_stops_before_plugin_copy(self):
        with self.assertRaisesRegex(RuntimeError, 'SDK version'):
            install.install(self.evidence)
        self.assert_untouched()

    def test_canvas_version_mismatch_stops_before_plugin_copy(self):
        (self.sdk / 'openhands_sdk-1.49.6.dist-info').mkdir(parents=True)
        self.canvas.mkdir(parents=True)
        (self.canvas / 'package.json').write_text(json.dumps({'version': '2.0.0'}))
        with self.assertRaisesRegex(RuntimeError, 'Canvas'):
            install.install(self.evidence)
        self.assert_untouched()

    def test_changed_bridge_stops_before_plugin_copy(self):
        (self.sdk / 'openhands_sdk-1.49.6.dist-info').mkdir(parents=True)
        (self.canvas / 'build').mkdir(parents=True)
        (self.canvas / 'package.json').write_text(json.dumps({'version': '1.24.0'}))
        (self.canvas / 'build/index.html').write_text('<body></body>')
        bridge = self.home / 'software-factory-setup/openhands-20260928/integration/factory_acp.py'
        bridge.parent.mkdir(parents=True)
        bridge.write_text('newer unrelated work')
        (self.evidence / 'openhands-before.py').write_text('old')
        (self.evidence / 'openhands-after.py').write_text('reviewed')
        with self.assertRaisesRegex(RuntimeError, 'source changed'):
            install.install(self.evidence)
        self.assert_untouched()
