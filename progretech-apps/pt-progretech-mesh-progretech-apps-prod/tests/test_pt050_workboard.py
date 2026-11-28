import os,json,subprocess,sys,tempfile,unittest
from pathlib import Path
import mesh_capability_registry as registry
import mesh_capability_runtime as runtime
import mesh_capabilities

ROOT=Path(__file__).resolve().parents[1]

class TestPT050Workboard(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.registry_path=Path(self.temp.name)/"registry.json"
        registry.reset_for_tests(self.registry_path)
    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("MESH_CAPABILITY_REGISTRY_PATH",None)
    def test_catalog_registry_runtime_present(self):
        self.assertIn("workboard",{c.id for c in mesh_capabilities.CAPABILITIES})
        self.assertIsNotNone(registry.get_record("workboard"))
        self.assertEqual(runtime.descriptor("workboard")["network"],"none")
    def test_existing_registry_backfills_without_state_loss(self):
        data=registry.default_registry()
        data["items"].pop("workboard")
        data["items"]["archify"]["state"]="QUALIFIED"
        self.registry_path.write_text(json.dumps(data))
        loaded=registry.ensure_registry()
        self.assertIn("workboard",loaded["items"])
        self.assertEqual(loaded["items"]["archify"]["state"],"QUALIFIED")
    def test_qualification_does_not_activate(self):
        registry.transition("workboard","QUALIFYING",reason="test")
        for c in ("representative_success","malformed_input","offline_behavior","timeout_behavior","resource_bounds","rollback_test"):
            registry.record_qualification_check("workboard",c,True,detail="pass")
        record=registry.transition("workboard","QUALIFIED",reason="qualified")
        self.assertEqual(record["state"],"QUALIFIED")
        with self.assertRaises(PermissionError): runtime.require_active("workboard")
    def test_cli_rejects_blocked_without_reason(self):
        state=Path(self.temp.name)/"wb.json"
        env=os.environ.copy()
        env["MESH_WORKBOARD_PATH"]=str(state)
        tool=ROOT/"scripts/workboard.py"
        p=subprocess.run([sys.executable,str(tool),"create","--title","x"],env=env,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        wid=json.loads(p.stdout)["id"]
        p=subprocess.run([sys.executable,str(tool),"transition",wid,"BLOCKED"],env=env,capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)
        self.assertIn("blocked_reason_required",p.stderr)

if __name__=="__main__": unittest.main()
