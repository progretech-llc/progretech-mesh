import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestPublicOriginContract(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_helpers_exist(self):
        funcs = {n.name for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef)}
        self.assertIn("mesh_public_origin", funcs)
        self.assertIn("websocket_origin_from_http", funcs)

    def test_env_contract_present(self):
        self.assertIn('MESH_PUBLIC_ORIGIN', self.source)
        self.assertIn('MESH_ENVIRONMENT', self.source)
        self.assertIn('production_mesh_public_origin_requires_https', self.source)

    def test_enrollment_uses_canonical_origin(self):
        self.assertIn('mesh_origin = mesh_public_origin()', self.source)
        self.assertIn('ws_base = websocket_origin_from_http(mesh_origin)', self.source)

    def test_frontend_copy_label(self):
        texts = []
        for p in list((ROOT/"templates").glob("*.html")) + list((ROOT/"static"/"js").glob("*.js")):
            texts.append(p.read_text(encoding="utf-8", errors="ignore"))
        joined="\n".join(texts)
        self.assertIn("Copy enrollment message", joined)
        self.assertNotIn("Copy command", joined)

if __name__ == "__main__":
    unittest.main()
