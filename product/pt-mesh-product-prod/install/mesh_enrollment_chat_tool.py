from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


PAYLOAD_PATTERN = re.compile(r"\bPTM1:([A-Za-z0-9_-]+)\b")


def extract_mesh_enrollment_payload(message_text: str) -> str | None:
    """
    Extract a Mesh enrollment payload from a normal chat message.

    This helper does not install anything on receipt by itself. The agent should call
    `accept_mesh_enrollment()` only after its normal local policy/authorization check.
    """
    match = PAYLOAD_PATTERN.search(message_text or "")
    if not match:
        return None
    return "PTM1:" + match.group(1)


def accept_mesh_enrollment(
    payload: str,
    *,
    runtime_adapter: str = "openclaw_bridge",
    observation_adapter: str = "openclaw_hooks",
) -> subprocess.CompletedProcess:
    helper = Path(__file__).resolve().parent / "agent_enroll.py"

    command = [
        sys.executable,
        str(helper),
        "--payload",
        payload,
        "--runtime-adapter",
        runtime_adapter,
        "--observation-adapter",
        observation_adapter,
    ]

    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )


def enrollment_response(completed: subprocess.CompletedProcess) -> str:
    if completed.returncode == 0:
        return (
            "ProgreTech Mesh enrollment accepted. "
            "I connected using passive plug-and-monitor mode. "
            "My existing tasks and conversations were not interrupted."
        )

    error = (completed.stderr or completed.stdout or "unknown enrollment error").strip()
    return f"I could not complete the Mesh enrollment: {error}"
