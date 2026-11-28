#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${ROOT_DIR}/.mesh-venv"

python3 -m venv "${VENV}"
"${VENV}/bin/pip" install --upgrade pip
"${VENV}/bin/pip" install -r "${ROOT_DIR}/requirements.txt"

mkdir -p "${HOME}/.config/progretech-mesh"

echo "Mesh customer gateway dependencies installed."
echo
echo "Next: generate an activation code in Mesh and run the bootstrap command shown there."
