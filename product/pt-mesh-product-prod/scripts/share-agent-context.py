#!/usr/bin/env python3
"""Publish a reviewed handoff file to one host-bound logical agent (no transcripts)."""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from control_center.shared_context import context_path
p=argparse.ArgumentParser();p.add_argument('--gateway',required=True);p.add_argument('--runtime',required=True);p.add_argument('--author',required=True);p.add_argument('--file',required=True);a=p.parse_args()
source=Path(a.file).resolve();text=source.read_text()
if not 1<=len(text)<=12000:raise SystemExit('Reviewed handoff must be 1–12000 characters')
path=context_path(Path.home(),a.gateway,a.runtime);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
data={'author':a.author,'text':text,'source':source.name,'updated_at':datetime.now(timezone.utc).isoformat()}
temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data));temp.chmod(0o600);os.replace(temp,path)
print(json.dumps({'saved':True,'gateway':a.gateway,'runtime':a.runtime,'path':str(path)}))
