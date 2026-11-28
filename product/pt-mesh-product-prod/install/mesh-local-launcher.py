#!/usr/bin/env python3
"""Open the installed local Mesh in its own browser app window."""
import os
import shutil
import subprocess
import time
from urllib.request import urlopen
subprocess.run(['systemctl','--user','start','progretech-mesh-local.service'],check=True)
for attempt in range(30):
    try:
        with urlopen('http://127.0.0.1:8080/healthz',timeout=2) as response:
            if response.status==200:break
    except OSError:time.sleep(.3)
else:raise SystemExit('Local Mesh did not become ready; check the user service.')
for name in ['google-chrome','chromium','chromium-browser']:
    browser=shutil.which(name)
    if browser:os.execv(browser,[browser,'--app=http://127.0.0.1:8080/','--class=ProgreTechMeshLocal'])
os.execvp('xdg-open',['xdg-open','http://127.0.0.1:8080/'])
