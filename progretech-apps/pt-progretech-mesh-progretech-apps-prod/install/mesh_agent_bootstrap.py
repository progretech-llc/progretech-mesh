from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen


def post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap a customer-owned ProgreTech Mesh agent gateway."
    )
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--activation-code", required=True)
    parser.add_argument("--activation-signature", required=True)
    parser.add_argument(
        "--gateway-script",
        default=str(Path(__file__).resolve().parents[1] / "gateway" / "mesh_gateway.py"),
    )
    args = parser.parse_args()

    mesh = args.mesh.rstrip("/")
    response = post_json(
        f"{mesh}/api/activation/redeem",
        {
            "agent_id": args.agent,
            "activation_code": args.activation_code,
            "activation_signature": args.activation_signature,
        },
    )

    if not response.get("ok"):
        raise SystemExit(f"Activation failed: {response}")

    token = response["pairing_token"]

    print("Activation accepted.")
    print("This installation remains customer-owned; Mesh is only the front-end/session relay.")
    print("Starting the local gateway...")

    command = [
        sys.executable,
        args.gateway_script,
        "--mesh",
        mesh,
        "--agent",
        args.agent,
        "--token",
        token,
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
