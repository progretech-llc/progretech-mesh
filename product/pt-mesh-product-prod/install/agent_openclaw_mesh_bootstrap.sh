#!/usr/bin/env bash
set -euo pipefail

# ProgreTech Mesh — agent-operated OpenClaw bootstrap
#
# Intended to be run by the agent under its existing local authorization policy.
# It never requires the human user to log into the workstation.
#
# Non-interference rule:
# - stage/verify first
# - hot-safe enable may occur during the enrollment turn
# - never restart the OpenClaw Gateway/runtime automatically

OPENCLAW="${OPENCLAW:-$HOME/.openclaw/bin/openclaw}"
ROOT="${MESH_PACKAGE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PLUGIN_SRC="${MESH_PLUGIN_STAGED_DIR:-$ROOT/openclaw-plugin-progretech-mesh}"
EXT_ROOT="${OPENCLAW_EXTENSIONS_DIR:-$HOME/.openclaw/extensions}"
PLUGIN_DST="$EXT_ROOT/progretech-mesh"
STATE="${MESH_AGENT_STATE_DIR:-$HOME/.progretech-mesh}"
LOG_DIR="$STATE/logs"
STATUS_FILE="$STATE/openclaw-bootstrap-status.json"

mkdir -p "$LOG_DIR" "$EXT_ROOT"
chmod 700 "$STATE" "$LOG_DIR" 2>/dev/null || true

log() {
  printf '[%s] %s\n' "$(date -Is 2>/dev/null || date)" "$*" | tee -a "$LOG_DIR/openclaw-bootstrap.log"
}

write_status() {
  local state="$1"
  local detail="$2"
  python3 - "$STATUS_FILE" "$state" "$detail" <<'PY'
import json, pathlib, sys, datetime
p=pathlib.Path(sys.argv[1])
p.parent.mkdir(parents=True, exist_ok=True)
tmp=p.with_suffix(".tmp")
tmp.write_text(json.dumps({
    "state": sys.argv[2],
    "detail": sys.argv[3],
    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}, indent=2), encoding="utf-8")
tmp.replace(p)
try:
    p.chmod(0o600)
except OSError:
    pass
PY
}

if [ ! -x "$OPENCLAW" ]; then
  write_status "error" "OpenClaw executable not found"
  log "ERROR: OpenClaw executable not found: $OPENCLAW"
  exit 2
fi

if [ ! -f "$PLUGIN_SRC/openclaw.plugin.json" ] || [ ! -f "$PLUGIN_SRC/index.js" ]; then
  write_status "error" "Mesh OpenClaw plugin package is incomplete"
  log "ERROR: plugin package incomplete: $PLUGIN_SRC"
  exit 3
fi

VERSION="$("$OPENCLAW" --version 2>/dev/null | head -n1 || true)"
log "Detected: ${VERSION:-unknown OpenClaw version}"

# Stage atomically. This copies code only; it does not change the running Gateway.
STAGE="$EXT_ROOT/.progretech-mesh.stage.$$"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -a "$PLUGIN_SRC/." "$STAGE/"
rm -rf "$PLUGIN_DST.prev"
if [ -d "$PLUGIN_DST" ]; then
  mv "$PLUGIN_DST" "$PLUGIN_DST.prev"
fi
mv "$STAGE" "$PLUGIN_DST"
write_status "staged" "Mesh plugin staged; hot-safe activation may proceed without generic idle wait"
log "Mesh plugin staged at $PLUGIN_DST"
log "No Gateway restart has occurred."

# The universal enrollment contract permits this declared hot-safe activation step
# during the enrollment turn. It must never restart the OpenClaw Gateway/runtime.
write_status "activating" "Enabling Mesh integration with hot-safe no-restart policy"
log "Enabling Mesh integration without restarting OpenClaw."

"$OPENCLAW" plugins enable progretech-mesh --accept-capabilities >>"$LOG_DIR/openclaw-bootstrap.log" 2>&1 || {
  if ! "$OPENCLAW" plugins list --json 2>/dev/null | grep -q '"progretech-mesh"'; then
    write_status "error" "Could not enable/discover progretech-mesh"
    log "ERROR: plugin could not be enabled/discovered."
    exit 4
  fi
}

write_status "verifying" "Mesh plugin staged/enabled; verifying runtime and channels without restart"
"$OPENCLAW" plugins inspect progretech-mesh --runtime --json >"$LOG_DIR/progretech-mesh-runtime.json" 2>&1 || {
  write_status "activation_reload_required" "Plugin install/enable completed but runtime activation requires explicit reload/restart"
  log "Plugin requires explicit reload/restart; enrollment will not restart OpenClaw automatically."
  exit 5
}
"$OPENCLAW" channels status --probe >"$LOG_DIR/channel-probe.txt" 2>&1 || true

if grep -qi 'telegram.*\(ok\|works\|connected\)' "$LOG_DIR/channel-probe.txt"; then
  telegram="healthy"
else
  telegram="check-required"
fi

write_status "ready" "Mesh OpenClaw plugin active without runtime restart; Telegram status: $telegram"
log "Mesh OpenClaw hot-safe bootstrap complete. Telegram: $telegram"
log "Status file: $STATUS_FILE"
