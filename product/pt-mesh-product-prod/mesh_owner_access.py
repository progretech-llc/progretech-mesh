"""Administrator-bound Firebase logins sharing an existing fleet owner."""
from __future__ import annotations

import json
import os
import re
from typing import Any


def owner_uid_bindings() -> dict[str, str]:
    """Read exact UID bindings; ambiguous or transitive configuration fails closed."""
    raw = os.environ.get("MESH_OWNER_UID_BINDINGS", "{}").strip()

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("invalid_owner_uid_bindings")
            result[key] = value
        return result

    try:
        bindings = json.loads(raw, object_pairs_hook=unique_pairs)
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid_owner_uid_bindings") from exc
    if not isinstance(bindings, dict) or len(bindings) > 256:
        raise ValueError("invalid_owner_uid_bindings")
    for login_uid, owner_uid in bindings.items():
        if any(not isinstance(uid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", uid)
               for uid in (login_uid, owner_uid)):
            raise ValueError("invalid_owner_uid_bindings")
        if owner_uid in bindings:
            raise ValueError("invalid_owner_uid_bindings")
    return bindings


def fleet_owner_id(user: dict[str, Any] | None) -> str:
    """Resolve ownership without replacing the authenticated actor's identity."""
    user = user or {}
    uid = str(user.get("id") or "").strip()
    if not uid or user.get("auth_source") != "firebase-email-link":
        return uid
    return owner_uid_bindings().get(uid, uid)
