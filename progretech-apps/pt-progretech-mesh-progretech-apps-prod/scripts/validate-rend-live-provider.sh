#!/usr/bin/env bash
set -u

MESH_BASE="${MESH_BASE:-http://127.0.0.1:8080}"
CONTROL_BASE="${CONTROL_BASE:-http://127.0.0.1:8787}"
STATE_DIR="${STATE_DIR:-$HOME/.progretech-mesh}"
COOKIE="/tmp/pt044-live-provider-cookie-$$.txt"

cleanup() {
  rm -f "$COOKIE" /tmp/pt044-live-provider-$$.json
}
trap cleanup EXIT

echo "---- SERVICES ----"
for unit in progretech-mesh-local.service rend-control-center.service openclaw-gateway.service; do
  if systemctl --user is-active --quiet "$unit"; then
    echo "$unit PASS"
  else
    echo "$unit FAIL"
    exit 10
  fi
done

echo
echo "---- LOCAL MESH ----"
curl -fsS --max-time 3 "$MESH_BASE/healthz" | python3 -m json.tool
echo "LOCAL MESH HTTP PASS"

echo
echo "---- CONTROL CENTER PROVIDER ----"
curl -fsS --max-time 3 "$CONTROL_BASE/api/mesh/provider/health" | python3 -m json.tool
echo "CONTROL CENTER PROVIDER PASS"

echo
echo "---- MESH DEVICE STATE ----"
python3 - "$STATE_DIR" <<'PY'
import json, sys
from pathlib import Path

state = Path(sys.argv[1])
cred = state / "device-credential.json"
conn = state / "connection-status.json"
life = state / "lifecycle-state.json"

assert cred.is_file(), "device credential missing"
assert conn.is_file(), "connection status missing"

connection = json.loads(conn.read_text())
assert connection.get("state") == "connected", connection

print("DEVICE CREDENTIAL PASS")
print("MESH CONNECTION PASS")
print("CONNECTION:", json.dumps({
    "state": connection.get("state"),
    "agent_id": connection.get("agent_id"),
    "device_id": connection.get("device_id"),
    "updated_at": connection.get("updated_at"),
}, indent=2))

if life.is_file():
    lifecycle = json.loads(life.read_text())
    print("ADAPTER VERSION:", lifecycle.get("adapter_version"))
    assert lifecycle.get("adapter_version") == "0.7.8", lifecycle
PY

echo
echo "---- LIVE PROVIDER IN MESH ----"
curl -fsS --max-time 3 -c "$COOKIE" -b "$COOKIE" -X POST "$MESH_BASE/login/dev" -o /dev/null
curl -fsS --max-time 3 -b "$COOKIE" "$MESH_BASE/api/agents/rend/capability-provider" \
  -o /tmp/pt044-live-provider-$$.json

python3 - /tmp/pt044-live-provider-$$.json <<'PY'
import json, sys
from pathlib import Path

body = json.loads(Path(sys.argv[1]).read_text())
assert body.get("ok") is True, body
assert body.get("connected") is True, body

provider = body.get("capability_provider") or {}
assert provider.get("provider_id") == "rend-host-control", provider
assert provider.get("scope") == "agent-local", provider

health = provider.get("health") or {}
assert health.get("healthy") is True, health
caps = health.get("capabilities") or []
assert len(caps) == 8, caps
assert all(item.get("available") is True for item in caps), caps

print("LIVE PROVIDER IN MESH PASS")
print("AGENT:", body.get("agent_name"))
print("PROVIDER:", provider.get("name"))
print("PROVIDER VERSION:", provider.get("provider_version"))
print("CAPABILITIES AVAILABLE: 8/8")
PY

echo
echo "RUNTIME ACCEPTANCE PASS"
