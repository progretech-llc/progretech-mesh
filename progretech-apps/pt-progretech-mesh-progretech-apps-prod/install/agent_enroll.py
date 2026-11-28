from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from mesh_plugin_package import fetch_and_stage_plugin


PREFIX = "PTM1:"


def decode_enrollment(value: str) -> dict:
    token = value.strip()
    if token.startswith(PREFIX):
        token = token[len(PREFIX):]

    padding = "=" * (-len(token) % 4)
    raw = base64.urlsafe_b64decode((token + padding).encode("ascii"))
    payload = json.loads(raw.decode("utf-8"))

    if payload.get("type") not in {"PROGRETECH_MESH_CONNECT_OR_ENROLL", "PROGRETECH_MESH_ENROLL"}:
        raise ValueError("not a ProgreTech Mesh enrollment payload")
    if payload.get("mode") != "plug-and-monitor":
        raise ValueError("enrollment is not plug-and-monitor")
    if payload.get("observation") != "read-only":
        raise ValueError("enrollment does not declare read-only observation")

    return payload


def post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Agent-led ProgreTech Mesh enrollment helper."
    )
    parser.add_argument("--payload", required=True)
    parser.add_argument(
        "--gateway-script",
        default=str(Path(__file__).resolve().parents[1] / "gateway" / "mesh_gateway.py"),
    )
    parser.add_argument(
        "--runtime-adapter",
        default=os.environ.get("MESH_RUNTIME_ADAPTER", "openclaw_bridge"),
    )
    parser.add_argument(
        "--observation-adapter",
        default=os.environ.get("MESH_OBSERVATION_ADAPTER", "openclaw_hooks"),
    )
    args = parser.parse_args()

    envelope = decode_enrollment(args.payload)

    mesh = str(envelope["mesh"]).rstrip("/")
    agent_id = str(envelope["agent_id"])

    state_dir = Path(
        os.path.expanduser(
            os.environ.get("MESH_AGENT_STATE_DIR", "~/.progretech-mesh")
        )
    )
    state_dir.mkdir(parents=True, exist_ok=True)

    plugin_package = envelope.get("plugin_package")
    if args.runtime_adapter == "openclaw_bridge":
        if not isinstance(plugin_package, dict):
            raise SystemExit("Mesh enrollment does not include the required OpenClaw plugin package")
        try:
            staged_plugin_dir = fetch_and_stage_plugin(plugin_package, state_dir=state_dir)
        except Exception as exc:
            raise SystemExit(f"Mesh plugin package rejected: {exc}") from exc
    else:
        staged_plugin_dir = None

    result = post_json(
        f"{mesh}/api/activation/redeem",
        {
            "agent_id": agent_id,
            "activation_code": envelope["activation_code"],
            "activation_signature": envelope["activation_signature"],
        },
    )

    if not result.get("ok"):
        raise SystemExit(f"Mesh enrollment failed: {result}")

    token = result["pairing_token"]
    device_credential = result.get("device_credential")
    device_id = result.get("device_id")

    if not device_credential:
        raise SystemExit("Mesh enrollment did not return a reconnect credential")

    credential_dir = state_dir / "credentials"
    credential_dir.mkdir(parents=True, exist_ok=True)

    credential_path = credential_dir / f"{agent_id}.json"
    credential_record = {
        "version": 1,
        "mesh": mesh,
        "agent_id": agent_id,
        "device_id": device_id,
        "credential": device_credential,
        "expires_at": result.get("device_credential_expires_at"),
        "runtime_adapter": args.runtime_adapter,
        "observation_adapter": args.observation_adapter,
        "gateway_script": str(Path(args.gateway_script).resolve()),
    }

    temp_path = credential_path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(credential_record, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(temp_path, 0o600)
    except OSError:
        pass
    temp_path.replace(credential_path)
    try:
        os.chmod(credential_path, 0o600)
    except OSError:
        pass

    supervisor_script = Path(__file__).resolve().parent / "mesh_gateway_supervisor.py"

    env = os.environ.copy()
    env["MESH_RUNTIME_ADAPTER"] = args.runtime_adapter
    env["MESH_OBSERVATION_ADAPTER"] = args.observation_adapter

    command = [
        sys.executable,
        str(supervisor_script),
        "--credential-file",
        str(credential_path),
    ]

    print("Mesh enrollment accepted.")
    print("Mode: plug-and-monitor")
    print("Observation: read-only")
    print("Existing tasks/sessions remain untouched.")
    print(f"Device ID: {device_id}")
    print(f"Credential stored locally: {credential_path}")
    print("Starting the Mesh gateway supervisor as a separate process.")

    subprocess.Popen(
        command,
        env=env,
        cwd=str(Path(args.gateway_script).resolve().parents[1]),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # OpenClaw integration is provisioned by the agent itself. The bootstrap is
    # detached and may perform the declared hot-safe managed install during this
    # enrollment turn. It never performs an automatic OpenClaw restart.
    if args.runtime_adapter == "openclaw_bridge":
        bootstrap = Path(__file__).resolve().parent / "agent_openclaw_mesh_bootstrap.sh"
        if bootstrap.exists():
            if staged_plugin_dir is not None:
                env["MESH_PLUGIN_STAGED_DIR"] = str(staged_plugin_dir)
            subprocess.Popen(
                [str(bootstrap)],
                env=env,
                cwd=str(Path(args.gateway_script).resolve().parents[1]),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print("OpenClaw Mesh bootstrap scheduled with hot-safe install policy; no automatic runtime restart.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
