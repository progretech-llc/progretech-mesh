#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import secrets
import shutil
import subprocess
import sys

ATTR_NAMESPACE="progretech-capability"
ATTR_VALUE="secret-broker"
SECRET_TOOL=shutil.which("secret-tool") or "/usr/bin/secret-tool"

def _run(args, *, input_text=None, timeout=10):
    return subprocess.run(
        [SECRET_TOOL, *args],
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=os.environ.copy(),
    )

def _attrs(name: str) -> list[str]:
    if not name or len(name)>128:
        raise ValueError("invalid_secret_name")
    return [ATTR_NAMESPACE, ATTR_VALUE, "name", name]

def status() -> dict:
    tool_ok=os.path.isfile(SECRET_TOOL) and os.access(SECRET_TOOL,os.X_OK)
    return {
        "provider":"freedesktop-secret-service",
        "secret_tool_present":tool_ok,
        "dbus_session_present":bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS")),
        "secret_values_exposed_by_cli":False,
    }

def put_secret(name: str, value: str) -> None:
    if not value:
        raise ValueError("empty_secret")
    p=_run(["store","--label",f"ProgreTech · {name}",*_attrs(name)],input_text=value)
    if p.returncode!=0:
        raise RuntimeError("secret_store_failed:"+p.stderr.strip()[:300])

def get_secret(name: str) -> str | None:
    p=_run(["lookup",*_attrs(name)])
    if p.returncode!=0:
        return None
    return p.stdout.rstrip("\n")

def delete_secret(name: str) -> bool:
    p=_run(["clear",*_attrs(name)])
    return p.returncode==0

def cmd_status(args):
    import json
    print(json.dumps(status(),indent=2))

def cmd_exists(args):
    found=get_secret(args.name) is not None
    print("PRESENT" if found else "ABSENT")

def cmd_delete(args):
    delete_secret(args.name)
    print("DELETED_OR_ABSENT")

def cmd_selftest(args):
    marker="pt050-probe-"+secrets.token_hex(6)
    secret=secrets.token_urlsafe(32)
    try:
        put_secret(marker,secret)
        recovered=get_secret(marker)
        if recovered!=secret:
            raise SystemExit("secret_roundtrip_mismatch")
        print("STORE: PASS")
        print("LOOKUP_COMPARE_WITHOUT_DISCLOSURE: PASS")
    finally:
        delete_secret(marker)
    if get_secret(marker) is not None:
        raise SystemExit("secret_delete_failed")
    print("DELETE: PASS")
    print("SECRET_BROKER_SELFTEST: PASS")

def parser():
    p=argparse.ArgumentParser(description="ProgreTech local secret broker")
    s=p.add_subparsers(dest="cmd",required=True)
    x=s.add_parser("status"); x.set_defaults(fn=cmd_status)
    x=s.add_parser("exists"); x.add_argument("name"); x.set_defaults(fn=cmd_exists)
    x=s.add_parser("delete"); x.add_argument("name"); x.set_defaults(fn=cmd_delete)
    x=s.add_parser("selftest"); x.set_defaults(fn=cmd_selftest)
    return p

def main():
    if not (os.path.isfile(SECRET_TOOL) and os.access(SECRET_TOOL,os.X_OK)):
        raise SystemExit("secret_tool_missing")
    a=parser().parse_args()
    try:
        a.fn(a)
    except (ValueError,RuntimeError) as exc:
        raise SystemExit(str(exc))

if __name__=="__main__":
    main()
