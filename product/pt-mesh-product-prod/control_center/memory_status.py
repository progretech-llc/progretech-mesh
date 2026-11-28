"""Bounded receipt metadata, not another role's memory content."""
import json
import time
from pathlib import Path
_CACHE={}

def memory_status(home, role):
    key=str(home);now=time.monotonic()
    if key not in _CACHE or now-_CACHE[key][0]>5:
        latest={};verified={}
        path=Path(home)/'.local/state/rend/hindsight/completion-audit.jsonl'
        try:
            with path.open('rb') as stream:
                stream.seek(0,2);size=stream.tell();stream.seek(max(0,size-1048576));data=stream.read(1048576).decode('utf-8',errors='replace')
            for line in data.splitlines():
                try:r=json.loads(line)
                except ValueError:continue
                agent=r.get('agent')
                if not isinstance(agent,str):continue
                latest[agent]={k:r.get(k) for k in ('status','at','project','activity_memory_id','activity_recall_verified','activity_kind')}
                if r.get('activity_memory_id') and r.get('activity_recall_verified') is True:verified[agent]=latest[agent]
        except OSError:pass
        _CACHE[key]=(now,latest,verified)
    _,latest,verified=_CACHE[key];row=latest.get(role,{})
    return {'latest_status':row.get('status','not_observed'),'at':row.get('at'),'activity_kind':row.get('activity_kind'),'project':row.get('project'),'memory_id':row.get('activity_memory_id'),'recall_verified':row.get('activity_recall_verified') is True,'last_verified':verified.get(role)}
