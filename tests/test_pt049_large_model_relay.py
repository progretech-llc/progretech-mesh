import unittest
import main

class TestPT049LargeModelRelay(unittest.TestCase):
    def test_rend_exposes_qualified_specialist_aliases(self):
        self.assertEqual(
            [alias for alias in main.ide_models("rend") if alias.startswith("rend")],
            [
                "rend",
                "rend-code",
                "rend-research",
            ],
        )

    def test_other_agents_do_not_inherit_rend_specialists(self):
        self.assertEqual(main.ide_models("mak"), ["mak", "mak-code"])
        self.assertEqual(main.ide_models("lyra"), ["lyra", "lyra-code"])
        self.assertNotIn("rend-research", main.ide_models("mak"))

    def test_research_alias_is_allowlisted_only_as_explicit_model_name(self):
        self.assertIn("rend-research", main.ide_models("rend"))
        self.assertNotIn("rend-research", main.ide_models("lyra"))

if __name__ == "__main__":
    unittest.main()
