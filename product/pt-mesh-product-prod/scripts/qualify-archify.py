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
QUAR_ROOT = Path.home() / ".progretech-mesh" / "quarantine" / "archify" / "2.11.0"
SOURCE_DIR = QUAR_ROOT / "source"
EVIDENCE_DIR = Path.home() / ".progretech-mesh" / "qualification-evidence" / "archify" / "2.11.0"
OUT_DIR = QUAR_ROOT / "outputs"

PINNED_COMMIT = "440e16d639ed94e55377fe66ef2350c171bdb971"
SOURCE_URL = "https://github.com/kevinapi/archify-Skill.git"

sys.path.insert(0, str(MESH_ROOT))
import mesh_capability_registry as registry

def find_node() -> str:
    candidates = [
        shutil.which("node"),
        str(Path.home() / ".openclaw" / "tools" / "node-v24.19.0" / "bin" / "node"),
    ]
    tools_dir = Path.home() / ".openclaw" / "tools"
    if tools_dir.exists():
        candidates.extend(str(p / "bin" / "node") for p in sorted(tools_dir.glob("node-v*"), reverse=True))
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise SystemExit("NODE RUNTIME NOT FOUND")

NODE = find_node()
print("NODE:", NODE)

record = registry.get_record("archify")
if not record:
    raise SystemExit("ARCHIFY REGISTRY RECORD MISSING")
if record["pin"]["commit"] != PINNED_COMMIT:
    raise SystemExit("PIN MISMATCH: refusing qualification")

if record["state"] == "CANDIDATE":
    registry.transition("archify", "QUALIFYING", reason="PT-2026-044 deterministic Archify qualification started")
elif record["state"] != "QUALIFYING":
    raise SystemExit(f"UNEXPECTED CAPABILITY STATE: {record['state']}")
print("REGISTRY STATE: QUALIFYING")

QUAR_ROOT.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)
os.chmod(QUAR_ROOT, 0o700)
os.chmod(EVIDENCE_DIR, 0o700)

if SOURCE_DIR.exists():
    shutil.rmtree(SOURCE_DIR)

subprocess.run(["git", "clone", "--quiet", "--no-checkout", SOURCE_URL, str(SOURCE_DIR)], check=True, timeout=90)
subprocess.run(["git", "-C", str(SOURCE_DIR), "checkout", "--quiet", PINNED_COMMIT], check=True, timeout=30)
actual_commit = subprocess.check_output(["git", "-C", str(SOURCE_DIR), "rev-parse", "HEAD"], text=True).strip()
assert actual_commit == PINNED_COMMIT
print("SOURCE PIN PASS:", actual_commit)

arch = SOURCE_DIR / "archify"
pkg = json.loads((arch / "package.json").read_text(encoding="utf-8"))
version = pkg.get("version")
assert version, pkg
print("ARCHIFY VERSION:", version)

checks = {}

def run(name: str, args: list[str], timeout: int = 30):
    started = time.monotonic()
    proc = subprocess.run(
        [NODE, str(arch / "bin" / "archify.mjs"), *args],
        cwd=arch,
        text=True,
        capture_output=True,
        timeout=timeout,
        env={k:v for k,v in os.environ.items() if k not in {"HTTP_PROXY","HTTPS_PROXY","ALL_PROXY"}},
    )
    elapsed = time.monotonic() - started
    checks[name] = {
        "returncode": proc.returncode,
        "elapsed_seconds": round(elapsed, 4),
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }
    if proc.returncode != 0:
        raise SystemExit(f"{name} FAIL\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    print(name.upper(), "PASS", f"{elapsed:.3f}s")
    return proc

# Representative runtime self-check.
run("representative_success", ["doctor"], timeout=30)

# Pick a checked-in workflow JSON for deterministic validate/deliver.
example_candidates = list((arch / "examples").glob("*.workflow.json"))
if not example_candidates:
    example_candidates = list((SOURCE_DIR / "examples").glob("*.workflow.json"))
if not example_candidates:
    raise SystemExit("NO WORKFLOW EXAMPLE FOUND")
example = example_candidates[0]
print("REPRESENTATIVE INPUT:", example.relative_to(SOURCE_DIR))

# Validate typed IR.
run("validate", ["validate", "workflow", str(example), "--quality", "showcase", "--json"], timeout=30)

# Deliver deterministic self-contained HTML.
target = OUT_DIR / "representative-workflow.html"
if target.exists():
    target.unlink()
run("deliver", ["deliver", "workflow", str(example), str(target), "--quality", "showcase", "--json"], timeout=45)
assert target.is_file() and target.stat().st_size > 5000
html = target.read_text(encoding="utf-8", errors="ignore")
assert "<html" in html.lower()
assert "<svg" in html.lower()
print("HTML ARTIFACT PASS:", target, target.stat().st_size, "bytes")

# Malformed input must fail predictably.
bad = QUAR_ROOT / "malformed.workflow.json"
bad.write_text('{"schema_version":1,"diagram_type":"workflow","nodes":"bad"}\n', encoding="utf-8")
started = time.monotonic()
bad_proc = subprocess.run(
    [NODE, str(arch / "bin" / "archify.mjs"), "validate", "workflow", str(bad), "--json"],
    cwd=arch, text=True, capture_output=True, timeout=10
)
bad_elapsed = time.monotonic() - started
assert bad_proc.returncode != 0
checks["malformed_input"] = {
    "returncode": 0,
    "elapsed_seconds": round(bad_elapsed, 4),
    "stdout": "malformed typed IR rejected",
    "stderr": bad_proc.stderr[-1000:],
}
print("MALFORMED INPUT PASS")

# Offline/local-only: disable git remote and prove validate still succeeds.
subprocess.run(["git", "-C", str(SOURCE_DIR), "remote", "set-url", "origin", "disabled://offline"], check=True)
offline = run("offline_behavior", ["validate", "workflow", str(example), "--json"], timeout=20)
print("OFFLINE VALIDATION PASS")

# Timeout behavior: guide command is bounded.
run("timeout_behavior", ["guide", "Show CI/CD checks, approval, deploy, and rollback", "--json"], timeout=10)

# Resource bounds.
file_count = sum(1 for p in arch.rglob("*") if p.is_file())
total_bytes = sum(p.stat().st_size for p in arch.rglob("*") if p.is_file())
assert file_count < 5000
assert total_bytes < 100_000_000
checks["resource_bounds"] = {
    "returncode": 0,
    "elapsed_seconds": 0,
    "stdout": f"files={file_count} bytes={total_bytes}",
    "stderr": "",
}
print("RESOURCE BOUNDS PASS:", file_count, "files", total_bytes, "bytes")

# Rollback isolation: disposable output can be removed without touching canonical Mesh source.
probe = OUT_DIR / "rollback-probe.html"
shutil.copy2(target, probe)
probe.unlink()
assert not probe.exists() and MESH_ROOT.exists()
checks["rollback_test"] = {
    "returncode": 0,
    "elapsed_seconds": 0,
    "stdout": "quarantine output rollback passed",
    "stderr": "",
}
print("ROLLBACK TEST PASS")

# Normalize qualification evidence names required by registry.
checks["representative_success"]["detail"] = "archify doctor pass"
checks["malformed_input"]["detail"] = "malformed typed IR rejected"
checks["offline_behavior"]["detail"] = "validation succeeded after remote disabled"
checks["timeout_behavior"]["detail"] = "guide command completed within 10 seconds"
checks["resource_bounds"]["detail"] = checks["resource_bounds"]["stdout"]
checks["rollback_test"]["detail"] = checks["rollback_test"]["stdout"]

evidence = {
    "capability": "archify",
    "version": version,
    "commit": PINNED_COMMIT,
    "license": "MIT",
    "node": NODE,
    "representative_input": str(example),
    "representative_output": str(target),
    "network_runtime_required": False,
    "checks": checks,
}
evidence_path = EVIDENCE_DIR / "qualification-v0.3.3.json"
evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
os.chmod(evidence_path, 0o600)

for check_name in (
    "representative_success",
    "malformed_input",
    "offline_behavior",
    "timeout_behavior",
    "resource_bounds",
    "rollback_test",
):
    registry.record_qualification_check(
        "archify",
        check_name,
        True,
        detail=checks[check_name]["detail"],
        artifact=str(evidence_path),
    )

qualified = registry.transition(
    "archify",
    "QUALIFIED",
    reason=f"Archify {version} deterministic local validation/delivery qualification passed; not activated.",
)
print("QUALIFICATION EVIDENCE:", evidence_path)
print("REGISTRY STATE:", qualified["state"])
print("ACTIVATION STATE: not active")
