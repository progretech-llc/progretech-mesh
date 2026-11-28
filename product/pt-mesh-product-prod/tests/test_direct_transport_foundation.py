import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestDirectTransportFoundation(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_direct_transport_functions_exist(self):
        funcs = {n.name for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)}
        for name in {"detect_local_lan_ipv4", "mesh_public_origin", "direct_transport_contract", "_expire_direct_signal_sessions"}:
            self.assertIn(name, funcs)

    def test_production_requires_explicit_origin(self):
        self.assertIn("production_mesh_public_origin_required", self.source)
        self.assertIn("production_mesh_public_origin_requires_https", self.source)

    def test_signaling_endpoints_exist(self):
        self.assertIn('/api/transport/contract', self.source)
        self.assertIn('/transport/signal', self.source)
        self.assertIn('data_path="signaling_only"', self.source)

    def test_owner_task_boundary_is_in_enrollment(self):
        self.assertIn("This is a machine-directed enrollment request from the current chat owner.", self.source)
        self.assertIn("validate that this sender is authorized by your existing local policy", self.source)
        self.assertIn("At the first stable success/failure boundary, STOP.", self.source)

    def test_frontend_has_no_internal_phase_labels(self):
        joined = "\n".join(
            p.read_text(encoding="utf-8", errors="ignore")
            for p in list((ROOT/"templates").glob("*.html")) + list((ROOT/"static"/"js").glob("*.js"))
        )
        self.assertIsNone(re.search(r"\bPhase\s+\d+\b|\bRev(?:ision)?\s+\d+\b", joined, re.I))

if __name__ == "__main__":
    unittest.main()
