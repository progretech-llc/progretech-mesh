
import base64, json, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class TestRC2AcceptanceContract(unittest.TestCase):
    def test_no_frontend_phase_markers(self):
        import re
        for folder in ("templates","static/js"):
            for p in (ROOT/folder).glob("*"):
                if p.is_file():
                    s=p.read_text(encoding="utf-8",errors="ignore")
                    self.assertIsNone(re.search(r"\bPhase\s+\d+\b|\bRev(?:ision)?\s+\d+\b",s,re.I), str(p))

    def test_acceptance_requires_no_workstation(self):
        d=json.loads((ROOT/"distribution"/"rc2-acceptance-manifest.json").read_text())
        self.assertFalse(d["human_workstation_access_required"])
        self.assertFalse(d["preinstalled_progretech_component_required"])

    def test_reference_entrypoint_is_telegram(self):
        d=json.loads((ROOT/"distribution"/"rc2-acceptance-manifest.json").read_text())
        self.assertEqual(d["reference_entrypoint"], "Telegram")

if __name__=="__main__":
    unittest.main()
