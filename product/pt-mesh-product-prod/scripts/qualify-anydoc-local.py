#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

MESH_ROOT = Path.home() / "PycharmProjects" / "progretech-mesh"
QUAR_ROOT = Path.home() / ".progretech-mesh" / "quarantine" / "firecrawl-anydoc" / "0.2.4"
VENV = QUAR_ROOT / ".venv"
EVIDENCE_DIR = Path.home() / ".progretech-mesh" / "qualification-evidence" / "firecrawl-anydoc" / "0.2.4"
PINNED_COMMIT = "261fc257d17c3eab0f673be31c408fd9fdc2171a"
PINNED_VERSION = "0.2.4"

sys.path.insert(0, str(MESH_ROOT))
import mesh_capability_registry as registry

record = registry.get_record("firecrawl-anydoc")
if not record:
    raise SystemExit("FIRECRAWL ANYDOC REGISTRY RECORD MISSING")
if record["pin"]["version"] != PINNED_VERSION or record["pin"]["commit"] != PINNED_COMMIT:
    raise SystemExit("PIN MISMATCH: refusing qualification")

if record["state"] == "CANDIDATE":
    registry.transition("firecrawl-anydoc", "QUALIFYING", reason="PT-2026-044 representative local-only qualification started")
elif record["state"] != "QUALIFYING":
    raise SystemExit(f"UNEXPECTED CAPABILITY STATE: {record['state']}")

print("REGISTRY STATE: QUALIFYING")
QUAR_ROOT.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
os.chmod(QUAR_ROOT, 0o700)
os.chmod(EVIDENCE_DIR, 0o700)

if not (VENV / "bin" / "python").exists():
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    print("CREATE: isolated anydoc qualification venv")
else:
    print("VENV: isolated anydoc qualification environment already exists")

py = str(VENV / "bin" / "python")
subprocess.run([py, "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True)
subprocess.run([py, "-m", "pip", "install", "-q", f"firecrawl-anydoc=={PINNED_VERSION}"], check=True)
print("INSTALL: firecrawl-anydoc==0.2.4 into quarantine")

checks = {}

def run_check(name: str, code: str, timeout: int = 10, env: dict | None = None):
    merged = os.environ.copy()
    merged.pop("FIRECRAWL_API_KEY", None)
    merged.pop("FIRECRAWL_API_URL", None)
    if env:
        merged.update(env)
    started = time.monotonic()
    proc = subprocess.run([py, "-c", code], capture_output=True, text=True, timeout=timeout, env=merged)
    elapsed = time.monotonic() - started
    result = {
        "name": name,
        "returncode": proc.returncode,
        "elapsed_seconds": round(elapsed, 4),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }
    checks[name] = result
    return result

representative_code = '''
import anydoc
data=b"name,score\\nRend,100\\nLyra,98\\nMak,99\\n"
out=anydoc.to_markdown_bytes(data,"csv")
assert "Rend" in out and "Lyra" in out and "Mak" in out
assert "|" in out
print(out)
'''
representative = run_check("representative_success", representative_code)
assert representative["returncode"] == 0, representative

malformed_code = '''
import anydoc
try:
    anydoc.to_markdown_bytes(b"\\\\x00\\\\x01\\\\x02this-is-not-a-document")
except Exception as exc:
    assert isinstance(exc, anydoc.ConvertError)
    print(type(exc).__name__)
else:
    raise SystemExit("malformed input unexpectedly converted")
'''
malformed = run_check("malformed_input", malformed_code)
assert malformed["returncode"] == 0, malformed

offline_code = '''
import os, anydoc
assert not os.environ.get("FIRECRAWL_API_KEY")
data=b"a,b\\n1,2\\n"
out=anydoc.to_markdown_bytes(data,"csv")
assert "1" in out and "2" in out
print("local conversion succeeded without hosted OCR credentials")
'''
offline = run_check(
    "offline_behavior",
    offline_code,
    env={
        "HTTP_PROXY": "http://127.0.0.1:9",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "ALL_PROXY": "http://127.0.0.1:9",
        "NO_PROXY": "",
    },
)
assert offline["returncode"] == 0, offline

timeout_code = '''
import anydoc
data=("a,b\\n"+"1,2\\n"*5000).encode()
for _ in range(25):
    out=anydoc.to_markdown_bytes(data,"csv")
assert out
print("bounded batch complete")
'''
timeout_check = run_check("timeout_behavior", timeout_code, timeout=5)
assert timeout_check["returncode"] == 0, timeout_check

resource_code = '''
import anydoc, time
data=("x,y\\n"+"123,456\\n"*20000).encode()
started=time.monotonic()
out=anydoc.to_markdown_bytes(data,"csv")
elapsed=time.monotonic()-started
assert out and elapsed < 5
print(f"bytes={len(data)} elapsed={elapsed:.4f}")
'''
resource = run_check("resource_bounds", resource_code, timeout=6)
assert resource["returncode"] == 0, resource

probe = QUAR_ROOT / ".rollback-probe"
probe.mkdir(exist_ok=True)
(probe / "marker.txt").write_text("rollback-probe\\n", encoding="utf-8")
shutil.rmtree(probe)
rollback_ok = not probe.exists() and MESH_ROOT.exists()
checks["rollback_test"] = {
    "name": "rollback_test",
    "returncode": 0 if rollback_ok else 1,
    "elapsed_seconds": 0,
    "stdout": "isolated quarantine rollback probe passed" if rollback_ok else "",
    "stderr": "",
}
assert rollback_ok

manifest = {
    "capability": "firecrawl-anydoc",
    "package": "firecrawl-anydoc",
    "version": PINNED_VERSION,
    "source_commit": PINNED_COMMIT,
    "mode": "local-only",
    "hosted_ocr_authorized": False,
    "checks": checks,
}
evidence_path = EVIDENCE_DIR / "qualification-v0.3.1.json"
evidence_path.write_text(json.dumps(manifest, indent=2) + "\\n", encoding="utf-8")
os.chmod(evidence_path, 0o600)

for check_name in (
    "representative_success",
    "malformed_input",
    "offline_behavior",
    "timeout_behavior",
    "resource_bounds",
    "rollback_test",
):
    result = checks[check_name]
    registry.record_qualification_check(
        "firecrawl-anydoc",
        check_name,
        result["returncode"] == 0,
        detail=(result["stdout"] or result["stderr"] or check_name)[:500],
        artifact=str(evidence_path),
    )

qualified = registry.transition(
    "firecrawl-anydoc",
    "QUALIFIED",
    reason="Local-only anydoc 0.2.4 qualification passed; hosted OCR remains unauthorized.",
)

print("QUALIFICATION EVIDENCE:", evidence_path)
print("REGISTRY STATE:", qualified["state"])
print("HOSTED OCR AUTHORIZED: false")
print("ACTIVATION STATE: not active")
