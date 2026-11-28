import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class TestVersionAwareFastPath(unittest.TestCase):
    def test_prompt_does_not_treat_old_adapter_as_compatible(self):
        s=(ROOT/'main.py').read_text(encoding='utf-8')
        self.assertIn('installed version is the same as the PTM1 plugin_package.version',s)
        self.assertIn('older Mesh adapter is installed, it is NOT eligible for this fast path',s)
        self.assertIn('perform one bounded in-place upgrade to plugin_package.version',s)
    def test_protocol_requires_version_aware_fastpath(self):
        p=json.loads((ROOT/'distribution/universal-agent-enrollment-v1.json').read_text())
        rule=p['selection_policy']['installed_version_rule']
        self.assertIn('Presence of an older adapter alone is not compatibility',rule)
        fp=p['connection_policy']['existing_installation_fast_path']
        self.assertIn('older_adapter_same_known_runtime',fp)
        self.assertIn('in-place upgrade',fp['older_adapter_same_known_runtime'])
if __name__=='__main__': unittest.main()
