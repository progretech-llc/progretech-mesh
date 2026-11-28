from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mesh_capability_registry import get_record

HOME = Path.home()
MESH_ROOT = HOME / "PycharmProjects" / "progretech-mesh"
STATE_ROOT = HOME / ".progretech-mesh"

RUNTIME_DESCRIPTORS: dict[str, dict[str, Any]] = {
    "secret-broker": {
        "label": "ProgreTech Secret Broker",
        "agents": ["Rend", "Mak", "Lyra"],
        "mode": "bounded_local_secret_service",
        "entrypoint": str(MESH_ROOT / "scripts" / "secret-broker.py"),
        "interpreter": str(MESH_ROOT / ".venv" / "bin" / "python"),
        "network": "none",
        "egress": "none",
        "arguments": ["status|exists|delete|selftest"],
        "timeout_seconds": 15,
        "notes": "Local Secret Service broker. Runtime CLI intentionally has no command that prints secret values.",
    },
    "imap-review": {
        "label": "ProgreTech IMAP Review",
        "agents": ["Rend", "Mak", "Lyra"],
        "mode": "bounded_mail_review",
        "entrypoint": str(MESH_ROOT / "scripts" / "imap-review.py"),
        "interpreter": str(MESH_ROOT / ".venv" / "bin" / "python"),
        "network": "explicit_mail_provider",
        "egress": "mail_provider_only",
        "arguments": ["status|list-headers", "--mailbox", "--limit", "--timeout"],
        "timeout_seconds": 30,
        "notes": "Read-only mailbox header review. Runtime cannot execute unless lifecycle state is ACTIVE with explicit owner approval.",
    },
    "webhooks": {
        "label": "ProgreTech Webhook Inbox",
        "agents": ["Rend", "Mak", "Lyra"],
        "mode": "bounded_local_state",
        "entrypoint": str(MESH_ROOT / "scripts" / "webhooks.py"),
        "interpreter": str(MESH_ROOT / ".venv" / "bin" / "python"),
        "network": "none",
        "egress": "none",
        "arguments": ["command", "args"],
        "timeout_seconds": 10,
        "notes": "Local HMAC verification and event spool only. No public listener is activated.",
    },
    "workboard": {
        "label": "ProgreTech Workboard",
        "agents": ["Rend", "Mak", "Lyra"],
        "mode": "bounded_local_state",
        "entrypoint": str(MESH_ROOT / "scripts" / "workboard.py"),
        "interpreter": str(MESH_ROOT / ".venv" / "bin" / "python"),
        "network": "none",
        "egress": "none",
        "arguments": ["command", "args"],
        "timeout_seconds": 10,
        "notes": "Native task-state ledger. No execution authority; activation remains owner-controlled.",
    },
    "firecrawl-anydoc": {
        "label": "anydoc Local",
        "agents": ["Rend", "Mak", "Lyra"],
        "mode": "bounded_local_tool",
        "entrypoint": str(MESH_ROOT / "scripts" / "anydoc-local.py"),
        "interpreter": str(MESH_ROOT / ".venv" / "bin" / "python"),
        "network": "none",
        "egress": "blocked",
        "arguments": ["input_file"],
        "timeout_seconds": 30,
        "notes": "Local document-to-Markdown only. Hosted OCR remains outside this runtime.",
    },
    "mattpocock-skills": {
        "label": "Curated Engineering Skills",
        "agents": ["Rend", "Mak"],
        "mode": "bounded_skill_library",
        "entrypoint": str(MESH_ROOT / "scripts" / "curated-skill-info.py"),
        "interpreter": str(MESH_ROOT / ".venv" / "bin" / "python"),
        "network": "none",
        "egress": "none",
        "arguments": ["skill_name"],
        "timeout_seconds": 10,
        "notes": "Read-only access to the qualified curated pack. Imported instructions never override ProgreTech governance.",
    },
    "archify": {
        "label": "Archify",
        "agents": ["Rend", "Mak", "Lyra"],
        "mode": "bounded_local_tool",
        "entrypoint": str(MESH_ROOT / "scripts" / "archify-runtime.py"),
        "interpreter": str(MESH_ROOT / ".venv" / "bin" / "python"),
        "network": "none",
        "egress": "none",
        "arguments": ["command", "args"],
        "timeout_seconds": 60,
        "notes": "Qualified local deterministic diagram validation/delivery runtime.",
    },
}


def descriptor(capability_id: str) -> dict[str, Any] | None:
    base = RUNTIME_DESCRIPTORS.get(capability_id)
    if not base:
        return None

    record = get_record(capability_id)
    if not record:
        return None

    result = dict(base)
    result.update({
        "id": capability_id,
        "state": record["state"],
        "active": record["state"] == "ACTIVE",
        "owner_approved": bool(record.get("activation", {}).get("owner_approved")),
        "activated_at": record.get("activation", {}).get("activated_at"),
        "pin": record.get("pin"),
    })
    return result


def all_descriptors() -> list[dict[str, Any]]:
    return [descriptor(cid) for cid in RUNTIME_DESCRIPTORS if descriptor(cid)]


def require_active(capability_id: str) -> dict[str, Any]:
    item = descriptor(capability_id)
    if not item:
        raise KeyError(capability_id)
    if not item["active"]:
        raise PermissionError("capability_not_active")
    if not item["owner_approved"]:
        raise PermissionError("owner_approval_missing")
    return item


def _sanitized_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "FIRECRAWL_API_KEY",
        "FIRECRAWL_API_URL",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
    ):
        env.pop(key, None)
    return env


def invoke(capability_id: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    item = require_active(capability_id)

    executable = Path(item["interpreter"])
    entrypoint = Path(item["entrypoint"])
    if not executable.is_file():
        raise FileNotFoundError(f"interpreter_missing:{executable}")
    if not entrypoint.is_file():
        raise FileNotFoundError(f"entrypoint_missing:{entrypoint}")

    cmd = [str(executable), str(entrypoint), *args]
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=int(item["timeout_seconds"]),
        env=_sanitized_env(),
        cwd=str(MESH_ROOT),
    )
