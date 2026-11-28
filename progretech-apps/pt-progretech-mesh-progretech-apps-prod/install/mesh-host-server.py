#!/usr/bin/env python3
"""Start the existing host bridge from the installed Mesh release."""
import json
import os
import sys
from pathlib import Path
installed=json.loads((Path.home()/'.local/state/progretech-mesh/installation/installed.json').read_text())
source=Path(installed['source']).resolve()
if not (source/'control_center/run_rend.py').is_file():raise SystemExit('Installed Mesh host adapter unavailable')
os.chdir(source)
os.execve(sys.executable,[sys.executable,'-m','control_center.run_rend'],os.environ.copy())
