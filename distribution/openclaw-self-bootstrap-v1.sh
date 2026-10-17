#!/usr/bin/env bash
set -euo pipefail

# ProgreTech Mesh OpenClaw self-bootstrap helper
# Intended to be fetched/executed by the agent itself from a PTM1-directed enrollment flow.
# It never grants privileges. The declared managed plugin install is hot-safe for enrollment and never performs an automatic OpenClaw restart.

OPENCLAW="${OPENCLAW:-$(command -v openclaw || true)}"
PACKAGE_URL="${MESH_PLUGIN_PACKAGE_URL:-}"
EXPECTED_SHA256="${MESH_PLUGIN_SHA256:?MESH_PLUGIN_SHA256 from the enrollment plan is required}"
EXPECTED_VERSION="0.10.5-portable-host.1"
WORK="${MESH_BOOTSTRAP_WORK_DIR:-${XDG_RUNTIME_DIR:-/tmp}/progretech-mesh-enroll}"
ARCHIVE="$WORK/progretech-mesh-openclaw.tgz"
PTM1="${MESH_ENROLLMENT_PAYLOAD:-}"
STATE="${PROGRETECH_MESH_STATE_DIR:-$HOME/.progretech-mesh}"
PENDING="$STATE/pending-enrollment.json"

fail() {
  printf 'Mesh enrollment bootstrap: %s\n' "$*" >&2
  exit 1
}

[ -n "$OPENCLAW" ] || fail "OpenClaw executable not found"
[ -n "$PACKAGE_URL" ] || fail "MESH_PLUGIN_PACKAGE_URL is required"
[ -n "$PTM1" ] || fail "MESH_ENROLLMENT_PAYLOAD is required"

mkdir -p "$WORK"
chmod 700 "$WORK" 2>/dev/null || true

case "$PACKAGE_URL" in
  https://*) ;;
  http://127.*|http://localhost:*|http://10.*|http://192.168.*|http://172.1[6-9].*|http://172.2[0-9].*|http://172.3[0-1].*) ;;
  http://*) fail "HTTP package URLs are allowed only for loopback/private-LAN Mesh hosts" ;;
  *) fail "Mesh package URL must use HTTP or HTTPS" ;;
esac

"$OPENCLAW" --version

mkdir -p "$STATE"
chmod 700 "$STATE" 2>/dev/null || true
python3 - "$PTM1" "$PENDING" <<'PY'
import base64, json, os, pathlib, sys
raw=sys.argv[1]
target=pathlib.Path(sys.argv[2])
if not raw.startswith("PTM1:"):
    raise SystemExit("invalid Mesh enrollment payload")
token=raw[5:].strip()
token += "=" * ((4-len(token)%4)%4)
try:
    payload=json.loads(base64.urlsafe_b64decode(token))
except Exception as exc:
    raise SystemExit("invalid PTM1 payload") from exc
if payload.get("type") != "PROGRETECH_MESH_CONNECT_OR_ENROLL":
    raise SystemExit("unexpected Mesh enrollment type")
if payload.get("mode") != "plug-and-monitor" or payload.get("observation") != "read-only":
    raise SystemExit("unsafe Mesh enrollment mode")
if payload.get("conversation_scope") != "mesh-independent":
    raise SystemExit("Mesh conversation isolation missing")
minimum={
    "type": payload.get("type"),
    "version": payload.get("version"),
    "mesh": payload.get("mesh"),
    "agent_id": payload.get("agent_id"),
    "activation_code": payload.get("activation_code"),
    "activation_signature": payload.get("activation_signature"),
    "issued_at": payload.get("issued_at"),
    "activation_lifecycle": payload.get("activation_lifecycle", "until_cancelled_or_redeemed"),
    "mode": payload.get("mode"),
    "observation": payload.get("observation"),
    "conversation_scope": payload.get("conversation_scope"),
}
tmp=target.with_suffix(".tmp")
tmp.write_text(json.dumps(minimum, indent=2), encoding="utf-8")
os.chmod(tmp, 0o600)
tmp.replace(target)
PY

python3 - "$PACKAGE_URL" "$ARCHIVE" <<'PY'
import sys
from urllib.request import Request, urlopen
url, out = sys.argv[1], sys.argv[2]
req = Request(url, headers={"User-Agent":"ProgreTech-Mesh-Agent/1","Accept":"application/gzip"})
with urlopen(req, timeout=30) as r:
    data = r.read(8*1024*1024 + 1)
if len(data) > 8*1024*1024:
    raise SystemExit("package exceeds 8 MiB limit")
open(out, "wb").write(data)
PY
chmod 600 "$ARCHIVE" 2>/dev/null || true

ACTUAL="$(python3 - "$ARCHIVE" <<'PY'
import hashlib, sys
h=hashlib.sha256()
with open(sys.argv[1],"rb") as f:
    for b in iter(lambda:f.read(1024*1024), b""):
        h.update(b)
print(h.hexdigest())
PY
)"
[ "$ACTUAL" = "$EXPECTED_SHA256" ] || fail "SHA-256 mismatch; refusing installation"

# Validate archive shape before handing it to OpenClaw.
python3 - "$ARCHIVE" "$EXPECTED_VERSION" <<'PYARCHIVE'
import tarfile, sys, json
from pathlib import Path
with tarfile.open(sys.argv[1], "r:gz") as tf:
    members=tf.getmembers()
    for m in members:
        q=Path(m.name)
        if q.is_absolute() or ".." in q.parts or m.issym() or m.islnk() or m.isdev():
            raise SystemExit("unsafe archive member")
    names={m.name for m in members}
    required={"package/openclaw.plugin.json", "package/package.json", "package/index.js"}
    if not required.issubset(names):
        raise SystemExit("required plugin files missing")
    pkg=json.load(tf.extractfile("package/package.json"))
    if pkg.get("name") != "@progretech/openclaw-mesh" or pkg.get("version") != sys.argv[2]:
        raise SystemExit("unexpected Mesh plugin identity/version")
PYARCHIVE

printf 'Package downloaded and verified. Proceeding with declared hot-safe managed installation; no generic idle wait and no automatic runtime restart.\n'

# Supported managed archive installation.
INSTALLED_VERSION="$("$OPENCLAW" plugins inspect progretech-mesh --json 2>/dev/null | python3 -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception: raise SystemExit(0)
v=d.get("version") or d.get("plugin",{}).get("version") or ""
print(v)
' 2>/dev/null || true)"

python3 - "$INSTALLED_VERSION" "${EXPECTED_VERSION}" <<'PY'
import re,sys
old,new=sys.argv[1],sys.argv[2]
def parts(v):
    m=re.match(r"^(\d+)\.(\d+)\.(\d+)", v or "")
    return tuple(map(int,m.groups())) if m else None
o,n=parts(old),parts(new)
if o and n and o > n:
    raise SystemExit("refusing Mesh adapter downgrade")
PY

if [ "$INSTALLED_VERSION" = "${EXPECTED_VERSION}" ]; then
  printf 'Mesh OpenClaw adapter ${EXPECTED_VERSION} already installed; skipping reinstall.\n'
else
  BACKUP_DIR="$STATE/adapter-backups"
  mkdir -p "$BACKUP_DIR"
  chmod 700 "$BACKUP_DIR" 2>/dev/null || true

  # Managed installer remains authoritative. Keep the verified archive as rollback input;
  # never touch OpenClaw internals directly.
  cp "$ARCHIVE" "$BACKUP_DIR/progretech-mesh-openclaw-${EXPECTED_VERSION}.tgz"
  chmod 600 "$BACKUP_DIR/progretech-mesh-openclaw-${EXPECTED_VERSION}.tgz" 2>/dev/null || true

  if ! "$OPENCLAW" plugins install "$ARCHIVE" --force --accept-capabilities; then
    fail "managed plugin installation failed; existing agent/runtime left untouched"
  fi
fi

"$OPENCLAW" plugins inspect progretech-mesh --runtime --json
"$OPENCLAW" channels status --probe

printf 'Mesh OpenClaw adapter installed and existing channels probed. No runtime restart was requested by this helper. Activation handoff is runtime-managed from ~/.progretech-mesh/pending-enrollment.json; do not connect to the local OpenClaw gateway or invent another transport path.\n'
