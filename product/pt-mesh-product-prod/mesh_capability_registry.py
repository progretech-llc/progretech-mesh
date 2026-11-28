from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIFECYCLE = ("DISCOVERED","QUARANTINED","INSPECTED","CANDIDATE","QUALIFYING","QUALIFIED","ACTIVE","REJECTED","SUPERSEDED","ROLLED_BACK")
ALLOWED_TRANSITIONS = {
    "DISCOVERED": {"QUARANTINED","REJECTED"},
    "QUARANTINED": {"INSPECTED","REJECTED"},
    "INSPECTED": {"CANDIDATE","REJECTED"},
    "CANDIDATE": {"QUALIFYING","REJECTED"},
    "QUALIFYING": {"QUALIFIED","REJECTED"},
    "QUALIFIED": {"ACTIVE","SUPERSEDED","ROLLED_BACK"},
    "ACTIVE": {"SUPERSEDED","ROLLED_BACK"},
    "REJECTED": {"QUARANTINED"},
    "SUPERSEDED": {"ROLLED_BACK"},
    "ROLLED_BACK": {"QUALIFYING","REJECTED"},
}
REGISTRY_LOCK = threading.RLock()

BATCH_A_PINS = {
    "secret-broker": {
        "source": "ProgreTech native + Freedesktop Secret Service",
        "version": "0.1.0",
        "commit": "native:PT-2026-050",
        "license": "ProgreTech internal source; system provider via libsecret/GNOME Keyring",
        "pin_verified_at": "2026-09-22",
        "intake_lane": "native integrated subsystem",
        "network_policy": "none",
        "egress_policy": "none",
        "notes": "Local secret broker over org.freedesktop.secrets. CLI never emits secret values.",
    },
    "imap-review": {
        "source": "ProgreTech native",
        "version": "0.1.0",
        "commit": "native:PT-2026-050",
        "license": "ProgreTech internal source",
        "pin_verified_at": "2026-09-22",
        "intake_lane": "native integrated subsystem",
        "network_policy": "explicit IMAP provider connection only after owner-approved activation",
        "egress_policy": "mail provider connection only; no unrelated egress",
        "notes": "Bounded mailbox review capability. Registration and qualification do not imply activation.",
    },
    "webhooks": {
        "source": "ProgreTech native",
        "version": "0.1.0",
        "commit": "native:PT-2026-050",
        "license": "ProgreTech internal source",
        "pin_verified_at": "2026-09-22",
        "intake_lane": "native integrated subsystem",
        "network_policy": "no public listener; local signed inbox only",
        "egress_policy": "none",
        "notes": "HMAC-verified local event intake/spool. External/public ingress requires a separate bounded adapter.",
    },
    "workboard": {
        "source": "ProgreTech native",
        "version": "0.1.0",
        "commit": "native:PT-2026-050",
        "license": "ProgreTech internal source",
        "pin_verified_at": "2026-09-22",
        "intake_lane": "native integrated subsystem",
        "network_policy": "none",
        "egress_policy": "none",
        "notes": "Local task-state ledger only; records work but grants no execution authority.",
    },
    "mattpocock-skills": {
        "source": "https://github.com/mattpocock/skills",
        "version": "1.2.3",
        "commit": "c55ee46073ed923f86ce59a5eb3b6d895095d1b7",
        "license": "MIT",
        "pin_verified_at": "2026-09-21",
        "intake_lane": "curated skill",
        "network_policy": "source acquisition only; no runtime network requirement by default",
        "egress_policy": "none by default",
        "notes": "Curate individual skills; do not install the repository wholesale.",
    },
    "firecrawl-anydoc": {
        "source": "https://github.com/firecrawl/anydoc",
        "version": "0.2.4",
        "commit": "261fc257d17c3eab0f673be31c408fd9fdc2171a",
        "license": "MIT",
        "pin_verified_at": "2026-09-21",
        "intake_lane": "qualified tool",
        "network_policy": "local conversion default",
        "egress_policy": "hosted OCR explicitly blocked until separately authorized",
        "notes": "Local document-to-Markdown path. Hosted OCR is separate data egress.",
    },
    "archify": {
        "source": "https://github.com/kevinapi/archify-Skill",
        "version": "commit-pinned",
        "commit": "440e16d639ed94e55377fe66ef2350c171bdb971",
        "license": "MIT",
        "pin_verified_at": "2026-09-21",
        "intake_lane": "curated skill / qualified tool",
        "network_policy": "default deny after source acquisition unless qualification proves need",
        "egress_policy": "none by default",
        "notes": "Preferred architecture/workflow/sequence/data-flow/lifecycle visualization candidate.",
    },
}

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

def registry_path() -> Path:
    configured = os.environ.get("MESH_CAPABILITY_REGISTRY_PATH","").strip()
    return Path(configured).expanduser() if configured else Path.home()/".progretech-mesh"/"capability-registry.json"

def _write_registry(data: dict[str, Any]) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)

def default_registry() -> dict[str, Any]:
    items={}
    for cid,pin in BATCH_A_PINS.items():
        items[cid]={
            "id":cid,
            "state":"CANDIDATE",
            "pin":deepcopy(pin),
            "qualification":{
                "evidence":[],
                "representative_success":False,
                "malformed_input":False,
                "offline_behavior":False,
                "timeout_behavior":False,
                "resource_bounds":False,
                "rollback_test":False,
            },
            "activation":{"owner_approved":False,"activated_at":None},
            "history":[{"at":utcnow(),"from":None,"to":"CANDIDATE","reason":"PT-2026-044 Batch A source resolved and pinned; not installed or activated."}],
        }
    return {"schema_version":1,"updated_at":utcnow(),"items":items}

def ensure_registry() -> dict[str, Any]:
    path=registry_path()
    with REGISTRY_LOCK:
        if path.exists():
            data=json.loads(path.read_text(encoding="utf-8"))
            defaults=default_registry()
            changed=False
            for cid,record in defaults["items"].items():
                if cid not in data.setdefault("items",{}):
                    data["items"][cid]=record
                    changed=True
            if changed:
                data["updated_at"]=utcnow()
                _write_registry(data)
            return data
        data=default_registry()
        _write_registry(data)
        return data

def list_records():
    return [deepcopy(v) for v in ensure_registry()["items"].values()]

def get_record(capability_id: str):
    value=ensure_registry()["items"].get(capability_id)
    return deepcopy(value) if value else None

def _qualification_complete(record):
    q=record.get("qualification") or {}
    required=("representative_success","malformed_input","offline_behavior","timeout_behavior","resource_bounds","rollback_test")
    return all(q.get(k) is True for k in required) and bool(q.get("evidence"))

def transition(capability_id: str, target: str, *, reason: str, owner_approved: bool=False, evidence=None):
    target=str(target).upper().strip()
    if target not in LIFECYCLE:
        raise ValueError("invalid_target_state")
    with REGISTRY_LOCK:
        data=ensure_registry()
        record=data["items"].get(capability_id)
        if not record:
            raise KeyError(capability_id)
        current=record["state"]
        if target==current:
            return deepcopy(record)
        if target not in ALLOWED_TRANSITIONS.get(current,set()):
            raise ValueError(f"transition_not_allowed:{current}->{target}")
        if evidence:
            record["qualification"]["evidence"].extend(evidence)
        if target=="QUALIFIED" and not _qualification_complete(record):
            raise ValueError("qualification_evidence_incomplete")
        if target=="ACTIVE":
            if current!="QUALIFIED":
                raise ValueError("activation_requires_qualified")
            if not owner_approved:
                raise ValueError("activation_requires_owner_approval")
            record["activation"]["owner_approved"]=True
            record["activation"]["activated_at"]=utcnow()
        record["state"]=target
        record["history"].append({"at":utcnow(),"from":current,"to":target,"reason":reason.strip() or "state transition"})
        data["updated_at"]=utcnow()
        _write_registry(data)
        return deepcopy(record)

def record_qualification_check(capability_id: str, check: str, passed: bool, *, detail: str, artifact: str|None=None):
    allowed={"representative_success","malformed_input","offline_behavior","timeout_behavior","resource_bounds","rollback_test"}
    if check not in allowed:
        raise ValueError("unknown_qualification_check")
    with REGISTRY_LOCK:
        data=ensure_registry()
        record=data["items"].get(capability_id)
        if not record:
            raise KeyError(capability_id)
        q=record["qualification"]
        q[check]=bool(passed)
        q["evidence"].append({"at":utcnow(),"check":check,"passed":bool(passed),"detail":detail,"artifact":artifact})
        data["updated_at"]=utcnow()
        _write_registry(data)
        return deepcopy(record)

def reset_for_tests(path: Path):
    os.environ["MESH_CAPABILITY_REGISTRY_PATH"]=str(path)
    if path.exists():
        path.unlink()
