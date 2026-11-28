import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestIdentityReplayDeploymentContract(unittest.TestCase):
    def test_dockerfile_uses_one_gunicorn_worker(self):
        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("--workers 1", text)

    def test_deploy_contract_limits_cloud_run_to_one_instance(self):
        text = (ROOT / "scripts" / "deploy-cloud-run.sh").read_text(encoding="utf-8")
        self.assertIn("--max-instances 1", text)
        self.assertIn("--concurrency 80", text)

    def test_deploy_contract_declares_bounded_replay_mode(self):
        text = (ROOT / "scripts" / "deploy-cloud-run.sh").read_text(encoding="utf-8")
        self.assertIn(
            "MESH_IDENTITY_REPLAY_MODE=${MESH_IDENTITY_REPLAY_MODE:-single-process-bounded}",
            text,
        )


if __name__ == "__main__":
    unittest.main()
