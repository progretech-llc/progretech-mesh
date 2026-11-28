#!/usr/bin/env bash
set -euo pipefail

OPENCLAW="${OPENCLAW:-$HOME/.openclaw/bin/openclaw}"
PLUGIN_DIR="${1:-$(pwd)/openclaw-plugin-progretech-mesh}"

echo "=== ProgreTech Mesh OpenClaw plugin validation ==="
"$OPENCLAW" --version
node --check "$PLUGIN_DIR/index.js"
python3 -m py_compile gateway/runtime_adapters/openclaw_bridge.py gateway/observation_adapters/openclaw_hooks.py gateway/mesh_gateway.py

echo
echo "Static validation passed."
echo "No OpenClaw configuration or service changes were made."
