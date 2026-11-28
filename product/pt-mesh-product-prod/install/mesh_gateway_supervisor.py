from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def load_record(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Keep the ProgreTech Mesh gateway connected without controlling the agent runtime."
    )
    parser.add_argument("--credential-file", required=True)
    parser.add_argument("--retry-seconds", type=int, default=5)
    args = parser.parse_args()

    credential_path = Path(args.credential_file).expanduser().resolve()
    stopped = False
    active: subprocess.Popen | None = None

    def stop_handler(signum, frame):
        nonlocal stopped, active
        stopped = True
        if active and active.poll() is None:
            active.terminate()

    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    while not stopped:
        try:
            record = load_record(credential_path)
        except Exception as exc:
            print(f"[mesh-supervisor] credential read failed: {exc}", file=sys.stderr)
            return 2

        gateway_script = Path(record["gateway_script"]).expanduser().resolve()
        env = os.environ.copy()
        env["MESH_RUNTIME_ADAPTER"] = record.get("runtime_adapter", "demo")
        env["MESH_OBSERVATION_ADAPTER"] = record.get("observation_adapter", "none")

        command = [
            sys.executable,
            str(gateway_script),
            "--mesh",
            record["mesh"],
            "--agent",
            record["agent_id"],
            "--credential",
            record["credential"],
        ]

        print(
            f"[mesh-supervisor] connecting {record['agent_id']} "
            f"device={record.get('device_id')}"
        )

        active = subprocess.Popen(
            command,
            env=env,
            cwd=str(gateway_script.parent.parent),
        )
        rc = active.wait()
        active = None

        if stopped:
            break

        print(
            f"[mesh-supervisor] gateway exited rc={rc}; "
            f"retrying in {max(2, args.retry_seconds)}s"
        )
        time.sleep(max(2, args.retry_seconds))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
