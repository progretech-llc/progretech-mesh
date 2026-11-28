import unittest
from unittest.mock import patch
import main

class TestRosterModelRelay(unittest.TestCase):
    def test_no_registry_means_no_invented_models(self):
        with patch.object(main, 'DEV_AGENT_REGISTRY', {}):
            for agent in ['rend','mak','lyra','custom-host']:
                self.assertEqual(main.ide_models(agent), [])

    def test_host_without_current_runtime_has_no_model(self):
        with patch.object(main, 'DEV_AGENT_REGISTRY', {'custom-host': {'owner_id':'owner','trust_state':'verified'}}):
            self.assertEqual(main.ide_models('custom-host'), [])

if __name__ == '__main__': unittest.main()
