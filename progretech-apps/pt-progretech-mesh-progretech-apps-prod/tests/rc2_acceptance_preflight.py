#!/usr/bin/env python3
from pathlib import Path
import base64, hashlib, json, re, sys, tarfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "distribution"

def fail(msg):
    print(f"FAIL: {msg}")
    raise SystemExit(1)

def ok(msg):
    print(f"PASS: {msg}")

manifest = json.loads((DIST/"rc2-acceptance-manifest.json").read_text())
catalog = json.loads((DIST/"agent-adapter-catalog-v1.json").read_text())
plan = json.loads((DIST/"openclaw-self-bootstrap-plan-v1.json").read_text())
protocol = json.loads((DIST/"universal-agent-enrollment-v1.json").read_text())

a = next(x for x in catalog["adapters"] if x["id"]=="openclaw")
version = a["package"]["version"]
expected_sha = a["package"]["sha256"]
pkg = DIST / f"progretech-mesh-openclaw-{version}.tgz"
if not pkg.is_file():
    fail(f"plugin archive missing: {pkg.name}")

actual = hashlib.sha256(pkg.read_bytes()).hexdigest()
if actual != expected_sha:
    fail("plugin SHA-256 mismatch")
ok("plugin archive hash matches catalog")

helper = DIST/"openclaw-self-bootstrap-v1.sh"
helper_sha = hashlib.sha256(helper.read_bytes()).hexdigest()
if helper_sha != a["self_bootstrap"]["helper_sha256"]:
    fail("bootstrap helper SHA-256 mismatch")
ok("bootstrap helper hash matches catalog")

with tarfile.open(pkg, "r:gz") as tf:
    names=set(tf.getnames())
    required={
        "progretech-mesh/openclaw.plugin.json",
        "progretech-mesh/package.json",
        "progretech-mesh/index.js",
    }
    if not required.issubset(names):
        fail("plugin archive missing required files")
    package=json.load(tf.extractfile("progretech-mesh/package.json"))
    if package.get("version") != version:
        fail("archive version does not match catalog")
ok("plugin archive identity/version matches")

if protocol["principles"]["preinstalled_progretech_component_required"]:
    fail("universal protocol incorrectly requires preinstalled ProgreTech component")
if protocol["principles"]["workstation_access_required"]:
    fail("universal protocol incorrectly requires workstation access")
ok("universal protocol remains hands-off")

if plan.get("package",{}).get("version") != version:
    fail("install plan package version mismatch")
if plan.get("package",{}).get("sha256") != expected_sha:
    fail("install plan package hash mismatch")
ok("OpenClaw plan is pinned to current package")

if manifest["artifact_pins"]["openclaw_adapter_sha256"] != expected_sha:
    fail("acceptance manifest package pin mismatch")
ok("acceptance manifest pins current package")

print("\nRC2 acceptance preflight complete.")
