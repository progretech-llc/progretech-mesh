#!/usr/bin/env bash
set -u

URL="${1:-http://127.0.0.1:8080/healthz}"
MAX_ATTEMPTS="${2:-25}"

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  if curl -fsS --max-time 2 "$URL" >/tmp/pt044-mesh-health-$$.json 2>/tmp/pt044-mesh-health-$$.err; then
    echo "MESH READY AFTER ATTEMPT: $attempt"
    python3 -m json.tool /tmp/pt044-mesh-health-$$.json 2>/dev/null || cat /tmp/pt044-mesh-health-$$.json
    rm -f /tmp/pt044-mesh-health-$$.json /tmp/pt044-mesh-health-$$.err
    exit 0
  fi
  sleep 1
done

echo "MESH READINESS TIMEOUT"
cat /tmp/pt044-mesh-health-$$.err 2>/dev/null || true
rm -f /tmp/pt044-mesh-health-$$.json /tmp/pt044-mesh-health-$$.err
exit 1
