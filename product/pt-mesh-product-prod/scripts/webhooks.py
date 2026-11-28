#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

MAX_PAYLOAD_BYTES = 65536

def state_root() -> Path:
    configured = os.environ.get("MESH_WEBHOOK_STATE_ROOT","").strip()
    return Path(configured).expanduser() if configured else Path.home()/".progretech-mesh"/"webhooks"

def secret_path() -> Path:
    return state_root()/"secret"

def inbox_path() -> Path:
    return state_root()/"inbox.jsonl"

def ensure_root() -> None:
    root=state_root()
    root.mkdir(parents=True,exist_ok=True)
    os.chmod(root,0o700)

def ensure_secret() -> bytes:
    ensure_root()
    p=secret_path()
    if not p.exists():
        tmp=p.with_suffix(".tmp")
        tmp.write_bytes(secrets.token_bytes(32))
        os.chmod(tmp,0o600)
        tmp.replace(p)
        os.chmod(p,0o600)
    data=p.read_bytes()
    if len(data) < 32:
        raise ValueError("webhook_secret_invalid")
    return data

def canonical_message(event_id: str, payload: str) -> bytes:
    return (event_id+"\n"+payload).encode("utf-8")

def validate_payload(payload: str) -> object:
    raw=payload.encode("utf-8")
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise ValueError("payload_too_large")
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json") from exc

def signature_for(event_id: str, payload: str) -> str:
    key=ensure_secret()
    return hmac.new(key,canonical_message(event_id,payload),hashlib.sha256).hexdigest()

def verify_signature(event_id: str, payload: str, signature: str) -> bool:
    expected=signature_for(event_id,payload)
    return hmac.compare_digest(expected,signature.strip().lower())

def load_ids() -> set[str]:
    p=inbox_path()
    if not p.exists():
        return set()
    ids=set()
    for line in p.read_text(encoding="utf-8",errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row=json.loads(line)
        except Exception:
            continue
        if row.get("event_id"):
            ids.add(str(row["event_id"]))
    return ids

def append_event(event_id: str, payload_obj: object) -> dict:
    ensure_root()
    if event_id in load_ids():
        raise ValueError("duplicate_event_id")
    row={
        "event_id":event_id,
        "received_at":time.time(),
        "payload":payload_obj,
    }
    p=inbox_path()
    with p.open("a",encoding="utf-8") as f:
        f.write(json.dumps(row,separators=(",",":"))+"\n")
    os.chmod(p,0o600)
    return row

def cmd_init_secret(args):
    p=secret_path()
    ensure_secret()
    print(json.dumps({"ok":True,"secret_path":str(p),"mode":"0600"}))

def cmd_sign(args):
    validate_payload(args.payload)
    print(signature_for(args.event_id,args.payload))

def cmd_ingest(args):
    if not args.event_id.strip():
        raise ValueError("event_id_required")
    payload_obj=validate_payload(args.payload)
    if not verify_signature(args.event_id,args.payload,args.signature):
        raise ValueError("signature_invalid")
    row=append_event(args.event_id,payload_obj)
    print(json.dumps(row,indent=2))

def cmd_list(args):
    p=inbox_path()
    rows=[]
    if p.exists():
        for line in p.read_text(encoding="utf-8",errors="replace").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    if args.limit:
        rows=rows[-args.limit:]
    print(json.dumps(rows,indent=2))

def parser():
    p=argparse.ArgumentParser(description="ProgreTech local signed webhook inbox")
    s=p.add_subparsers(dest="cmd",required=True)
    x=s.add_parser("init-secret"); x.set_defaults(fn=cmd_init_secret)
    x=s.add_parser("sign"); x.add_argument("--event-id",required=True); x.add_argument("--payload",required=True); x.set_defaults(fn=cmd_sign)
    x=s.add_parser("ingest"); x.add_argument("--event-id",required=True); x.add_argument("--payload",required=True); x.add_argument("--signature",required=True); x.set_defaults(fn=cmd_ingest)
    x=s.add_parser("list"); x.add_argument("--limit",type=int,default=50); x.set_defaults(fn=cmd_list)
    return p

def main():
    a=parser().parse_args()
    try:
        a.fn(a)
    except ValueError as exc:
        raise SystemExit(str(exc))

if __name__=="__main__":
    main()
