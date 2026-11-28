from __future__ import annotations

import os
import secrets
import time
from typing import Any

OWNERSHIP_CLAIM_TTL_SECONDS = int(os.environ.get("MESH_OWNERSHIP_CLAIM_TTL_SECONDS", "600"))
OWNERSHIP_CLAIMS: dict[str, dict[str, Any]] = {}


def ownership_mode() -> str:
    value = str(os.environ.get("MESH_OWNERSHIP_MODE", "observe")).strip().lower()
    return value if value in {"observe", "enforce"} else "observe"


def owner_id(record: dict[str, Any] | None) -> str:
    return str((record or {}).get("owner_id") or "").strip()


def can_access(record: dict[str, Any] | None, user_id: str) -> tuple[bool, str]:
    if not record:
        return False, "agent_not_found"
    uid = str(user_id or "").strip()
    if not uid:
        return False, "authentication_required"

    current = owner_id(record)
    if current:
        return (current == uid, "ok" if current == uid else "agent_not_found")

    if ownership_mode() == "observe":
        return True, "legacy_unowned_observe"

    return False, "agent_not_found"


def visible(record: dict[str, Any], user_id: str) -> bool:
    return can_access(record, user_id)[0]


def _cleanup_claims() -> None:
    now = int(time.time())
    for code, item in list(OWNERSHIP_CLAIMS.items()):
        if item.get("used") or int(item.get("expires_at", 0)) < now:
            OWNERSHIP_CLAIMS.pop(code, None)


def issue_claim(user_id: str, agent_id: str | None = None) -> dict[str, Any]:
    _cleanup_claims()
    uid = str(user_id or "").strip()
    if not uid:
        raise ValueError("ownership_user_required")
    aid = str(agent_id or "").strip() or None
    code = secrets.token_urlsafe(24)
    now = int(time.time())
    item = {
        "code": code,
        "owner_id": uid,
        "agent_id": aid,
        "issued_at": now,
        "expires_at": now + OWNERSHIP_CLAIM_TTL_SECONDS,
        "used": False,
    }
    OWNERSHIP_CLAIMS[code] = item
    return dict(item)


def consume_claim(code: str, agent_id: str) -> tuple[bool, str, dict[str, Any] | None]:
    _cleanup_claims()
    key = str(code or "").strip()
    aid = str(agent_id or "").strip()
    item = OWNERSHIP_CLAIMS.get(key)
    if not item:
        return False, "ownership_claim_not_found", None
    if item.get("used"):
        return False, "ownership_claim_used", None
    if int(item.get("expires_at", 0)) < int(time.time()):
        OWNERSHIP_CLAIMS.pop(key, None)
        return False, "ownership_claim_expired", None
    expected = str(item.get("agent_id") or "").strip()
    if expected and expected != aid:
        return False, "ownership_claim_agent_mismatch", None

    item["used"] = True
    consumed = dict(item)
    OWNERSHIP_CLAIMS.pop(key, None)
    return True, "ok", consumed
