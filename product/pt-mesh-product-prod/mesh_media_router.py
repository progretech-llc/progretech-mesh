from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import mesh_capability_registry as registry

ROLE_TO_CAPABILITY = {
    "image_generation": "animagine-xl-3.1",
    "video_generation": "wan2.2-t2v-a14b-q4km",
    "music_generation": "ace-step-1.5",
}

GENERATION_VERBS = {
    "create","draw","generate","make","render","illustrate","design",
    "animate","compose","produce","write","turn","transform",
}

IMAGE_TERMS = {
    "image","picture","illustration","art","artwork","drawing","poster",
    "icon","sprite","portrait","banner","visual","photo",
}
VIDEO_TERMS = {
    "video","animation","clip","movie","motion","animate","animated",
}
MUSIC_TERMS = {
    "music","song","track","instrumental","soundtrack","melody","beat",
    "audio","score","jingle",
}

@dataclass(frozen=True)
class MediaRoute:
    role: str
    capability_id: str
    reason: str
    state: str
    owner_approved: bool
    runtime: str | None
    model_path: str | None

def _tokens(text: str) -> set[str]:
    normalized="".join(ch.lower() if ch.isalnum() else " " for ch in str(text))
    return {x for x in normalized.split() if x}

def infer_media_role(text: str) -> str | None:
    tokens=_tokens(text)
    if not tokens:
        return None

    has_generation=bool(tokens & GENERATION_VERBS)
    if not has_generation:
        # "animate/animated" or "compose" are inherently action-like in this bounded vocabulary.
        if not (tokens & {"animate","compose","render","generate"}):
            return None

    scores={
        "image_generation": len(tokens & IMAGE_TERMS),
        "video_generation": len(tokens & VIDEO_TERMS),
        "music_generation": len(tokens & MUSIC_TERMS),
    }

    best=max(scores.values())
    if best <= 0:
        return None

    winners=[role for role,score in scores.items() if score==best]
    if len(winners) != 1:
        return None
    return winners[0]

def resolve_active_role(role: str) -> MediaRoute | None:
    cid=ROLE_TO_CAPABILITY.get(str(role))
    if not cid:
        return None
    rec=registry.get_record(cid)
    if not rec:
        return None
    active=rec.get("state")=="ACTIVE"
    approved=bool(rec.get("activation",{}).get("owner_approved"))
    if not (active and approved):
        return None

    meta=rec.get("metadata",{}) or {}
    return MediaRoute(
        role=role,
        capability_id=cid,
        reason="active_owner_approved_provider",
        state=rec.get("state"),
        owner_approved=approved,
        runtime=meta.get("runtime"),
        model_path=meta.get("model_path"),
    )

def resolve_media_intent(text: str) -> MediaRoute | None:
    role=infer_media_role(text)
    if role is None:
        return None
    return resolve_active_role(role)

def routing_snapshot() -> list[dict[str, Any]]:
    out=[]
    for role,cid in ROLE_TO_CAPABILITY.items():
        rec=registry.get_record(cid)
        out.append({
            "role":role,
            "capability_id":cid,
            "state":rec.get("state") if rec else None,
            "owner_approved":bool((rec or {}).get("activation",{}).get("owner_approved")),
            "available":resolve_active_role(role) is not None,
        })
    return out
