import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestRC2Cleanup(unittest.TestCase):
    def test_retired_bootstrap_routes_and_constants_absent(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("OPENCLAW_ENROLLMENT_BOOTSTRAP_VERSION", source)
        self.assertNotIn("OPENCLAW_ENROLLMENT_BOOTSTRAP_FILENAME", source)
        self.assertNotIn("/api/distribution/openclaw/enrollment-bootstrap", source)
        self.assertNotIn("trusted-baseline", source)

    def test_templates_exist(self):
        self.assertTrue((ROOT / "templates" / "login.html").is_file())
        self.assertTrue((ROOT / "templates" / "index.html").is_file())

if __name__ == "__main__":
    unittest.main()
