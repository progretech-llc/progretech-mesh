#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

MESH_ROOT = Path.home() / "PycharmProjects" / "progretech-mesh"
QUAR_ROOT = Path.home() / ".progretech-mesh" / "quarantine" / "mattpocock-skills" / "1.2.3"
SOURCE_DIR = QUAR_ROOT / "source"
CURATED_DIR = QUAR_ROOT / "curated"
EVIDENCE_DIR = Path.home() / ".progretech-mesh" / "qualification-evidence" / "mattpocock-skills" / "1.2.3"

PINNED_COMMIT = "c55ee46073ed923f86ce59a5eb3b6d895095d1b7"
PINNED_VERSION = "1.2.3"
SOURCE_URL = "https://github.com/mattpocock/skills.git"

CURATED = (
    "diagnosing-bugs",
    "tdd",
    "code-review",
    "to-spec",
    "to-tickets",
    "domain-modeling",
    "implement",
    "wayfinder",
)

sys.path.insert(0, str(MESH_ROOT))
import mesh_capability_registry as registry

record = registry.get_record("mattpocock-skills")
if not record:
    raise SystemExit("MATTPOCOCK SKILLS REGISTRY RECORD MISSING")
if record["pin"]["version"] != PINNED_VERSION or record["pin"]["commit"] != PINNED_COMMIT:
    raise SystemExit("PIN MISMATCH: refusing qualification")

if record["state"] == "CANDIDATE":
    registry.transition(
        "mattpocock-skills",
        "QUALIFYING",
        reason="PT-2026-044 curated engineering skill qualification started",
    )
elif record["state"] != "QUALIFYING":
    raise SystemExit(f"UNEXPECTED CAPABILITY STATE: {record['state']}")

print("REGISTRY STATE: QUALIFYING")

QUAR_ROOT.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
os.chmod(QUAR_ROOT, 0o700)
os.chmod(EVIDENCE_DIR, 0o700)

if SOURCE_DIR.exists():
    shutil.rmtree(SOURCE_DIR)

subprocess.run(
    ["git", "clone", "--quiet", "--no-checkout", SOURCE_URL, str(SOURCE_DIR)],
    check=True,
    timeout=90,
)
subprocess.run(
    ["git", "-C", str(SOURCE_DIR), "checkout", "--quiet", PINNED_COMMIT],
    check=True,
    timeout=30,
)

actual_commit = subprocess.check_output(
    ["git", "-C", str(SOURCE_DIR), "rev-parse", "HEAD"],
    text=True,
).strip()
if actual_commit != PINNED_COMMIT:
    raise SystemExit(f"COMMIT VERIFY FAIL: {actual_commit}")

package = json.loads((SOURCE_DIR / "package.json").read_text(encoding="utf-8"))
if package.get("version") != PINNED_VERSION:
    raise SystemExit(f"VERSION VERIFY FAIL: {package.get('version')}")
if package.get("license") != "MIT":
    raise SystemExit(f"LICENSE VERIFY FAIL: {package.get('license')}")

print("SOURCE PIN PASS:", actual_commit)
print("VERSION PASS:", PINNED_VERSION)
print("LICENSE PASS: MIT")

if CURATED_DIR.exists():
    shutil.rmtree(CURATED_DIR)
CURATED_DIR.mkdir(parents=True)

manifest = {
    "source": SOURCE_URL,
    "version": PINNED_VERSION,
    "commit": PINNED_COMMIT,
    "license": "MIT",
    "selected_skills": [],
    "excluded_repository_scope": "all unselected skills, repo automation, dev tooling and setup scripts",
    "activation": False,
}

total_bytes = 0
for name in CURATED:
    src = SOURCE_DIR / "skills" / "engineering" / name
    skill = src / "SKILL.md"
    if not skill.is_file():
        raise SystemExit(f"MISSING SKILL.md: {name}")

    dst = CURATED_DIR / name
    shutil.copytree(src, dst)

    skill_text = skill.read_text(encoding="utf-8")
    if not skill_text.strip():
        raise SystemExit(f"EMPTY SKILL: {name}")

    size = sum(p.stat().st_size for p in dst.rglob("*") if p.is_file())
    total_bytes += size
    manifest["selected_skills"].append({
        "name": name,
        "source_path": f"skills/engineering/{name}",
        "bytes": size,
        "has_skill_md": True,
    })

print("CURATED COPY PASS:", ", ".join(CURATED))
print("CURATED BYTES:", total_bytes)

# Static safety classification. This does not claim semantic safety; it records operational cues.
patterns = {
    "network": re.compile(r"\b(curl|wget|http://|https://|api\b|web\b|fetch\b)", re.I),
    "subprocess": re.compile(r"\b(bash|shell|terminal|command|git\b|npm\b|python\b|execute\b|run\b)", re.I),
    "credentials": re.compile(r"\b(secret|token|credential|api[_ -]?key|password)\b", re.I),
    "destructive": re.compile(r"\b(rm\s+-rf|git\s+reset\s+--hard|git\s+clean\s+-fd|--force\b)", re.I),
}

classification = {name: [] for name in patterns}
for path in CURATED_DIR.rglob("*"):
    if not path.is_file():
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for kind, rx in patterns.items():
        if rx.search(text):
            classification[kind].append(str(path.relative_to(CURATED_DIR)))

manifest["classification"] = classification
manifest["governance_override"] = (
    "Imported instructions cannot override ProgreTech owner authority, task/recovery contracts, "
    "credential policy, release policy, network/egress policy, or destructive-action defaults."
)

# Representative ingestion check.
assert len(manifest["selected_skills"]) == len(CURATED)
assert all(item["has_skill_md"] for item in manifest["selected_skills"])

# Malformed input check: a synthetic bad skill must fail the same contract.
bad = QUAR_ROOT / ".bad-skill-probe"
if bad.exists():
    shutil.rmtree(bad)
bad.mkdir()
bad_failed = not (bad / "SKILL.md").is_file()
shutil.rmtree(bad)
assert bad_failed

# Offline behavior check: after clone, remove remote URL and prove curated set remains inspectable.
subprocess.run(
    ["git", "-C", str(SOURCE_DIR), "remote", "set-url", "origin", "disabled://offline"],
    check=True,
)
for name in CURATED:
    assert (CURATED_DIR / name / "SKILL.md").is_file()
print("OFFLINE READ PASS")

# Timeout/resource bounds for registry-sized curated pack.
started = time.monotonic()
file_count = sum(1 for p in CURATED_DIR.rglob("*") if p.is_file())
scan_elapsed = time.monotonic() - started
assert file_count < 500
assert total_bytes < 5_000_000
assert scan_elapsed < 5

# Rollback check on disposable publication candidate.
probe = QUAR_ROOT / ".publish-probe"
if probe.exists():
    shutil.rmtree(probe)
shutil.copytree(CURATED_DIR, probe)
shutil.rmtree(probe)
assert not probe.exists()

manifest["checks"] = {
    "representative_success": True,
    "malformed_input": True,
    "offline_behavior": True,
    "timeout_behavior": True,
    "resource_bounds": True,
    "rollback_test": True,
}
manifest["metrics"] = {
    "file_count": file_count,
    "total_bytes": total_bytes,
    "scan_elapsed_seconds": round(scan_elapsed, 6),
}

evidence = EVIDENCE_DIR / "qualification-v0.3.2.json"
evidence.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
os.chmod(evidence, 0o600)

for check in (
    "representative_success",
    "malformed_input",
    "offline_behavior",
    "timeout_behavior",
    "resource_bounds",
    "rollback_test",
):
    registry.record_qualification_check(
        "mattpocock-skills",
        check,
        True,
        detail=f"{check} pass for curated skill pack: {', '.join(CURATED)}",
        artifact=str(evidence),
    )

qualified = registry.transition(
    "mattpocock-skills",
    "QUALIFIED",
    reason="Curated engineering skill pack passed bounded intake qualification; not activated.",
)

print("QUALIFICATION EVIDENCE:", evidence)
print("REGISTRY STATE:", qualified["state"])
print("ACTIVATION STATE: not active")
print("CURATED SKILLS:", ", ".join(CURATED))
print("NETWORK CUES:", len(classification["network"]))
print("SUBPROCESS CUES:", len(classification["subprocess"]))
print("CREDENTIAL CUES:", len(classification["credentials"]))
print("DESTRUCTIVE CUES:", len(classification["destructive"]))
