#!/usr/bin/env python3
"""Stable systemd entry point for the selected local release."""
import json
import os
from pathlib import Path
state=Path.home()/'.local/state/progretech-mesh/installation/installed.json'
installed=json.loads(state.read_text());source=Path(installed['source']).resolve()
os.chdir(source)
environment=os.environ.copy()
environment.update(MESH_LOCAL_CONTROL_CENTER='1',MESH_UPDATE_ENABLED='1',DEV_SEED_AGENTS='0',TRUST_PROXY_HEADERS='0',MESH_VERSION=installed['version'],BUILD_ID=installed['commit'][:7])
os.execve(installed['python'],[installed['python'],str(source/'main.py')],environment)
