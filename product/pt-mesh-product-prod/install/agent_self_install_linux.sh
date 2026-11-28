#!/usr/bin/env bash
set -euo pipefail

# This script is intended to be invoked by the local agent under its own approved
# tooling/policy, not manually by an end user.

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STATE="${MESH_AGENT_STATE_DIR:-$HOME/.progretech-mesh}"

mkdir -p "$STATE"/{credentials,logs}
chmod 700 "$STATE" 2>/dev/null || true
chmod 700 "$STATE/credentials" 2>/dev/null || true

echo "ProgreTech Mesh local components are available."
echo "Root:  $ROOT"
echo "State: $STATE"
echo "No running agent process was restarted or modified."
