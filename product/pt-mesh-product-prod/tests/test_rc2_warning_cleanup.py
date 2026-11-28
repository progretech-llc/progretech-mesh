import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestWarningCleanup(unittest.TestCase):
    def test_standard_template_layout_declared(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('template_folder="templates"', source)
        self.assertIn('static_folder="static"', source)
        self.assertTrue((ROOT / "templates" / "login.html").is_file())
        self.assertTrue((ROOT / "templates" / "index.html").is_file())

    def test_temp_cleanup_is_shared(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("def _expire_temp_entries(", source)
        self.assertEqual(source.count("_expire_temp_entries(FILE_"), 2)

if __name__ == "__main__":
    unittest.main()
