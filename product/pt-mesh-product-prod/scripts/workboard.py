#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, secrets
from datetime import datetime, timezone
from pathlib import Path

STATUSES=("TODO","READY","IN_PROGRESS","BLOCKED","REVIEW","DONE","CANCELLED")
AGENTS=("rend","mak","lyra","unassigned")

def utcnow(): return datetime.now(timezone.utc).isoformat()
def state_path():
    v=os.environ.get("MESH_WORKBOARD_PATH","").strip()
    return Path(v).expanduser() if v else Path.home()/".progretech-mesh"/"workboard.json"
def default_state(): return {"schema_version":1,"updated_at":utcnow(),"items":[]}
def load_state():
    p=state_path()
    if not p.exists(): return default_state()
    d=json.loads(p.read_text())
    if d.get("schema_version")!=1 or not isinstance(d.get("items"),list):
        raise ValueError("invalid_workboard_state")
    return d
def write_state(d):
    p=state_path(); p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(".tmp")
    t.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n")
    os.chmod(t,0o600); t.replace(p); os.chmod(p,0o600)
def find_item(d,i):
    for x in d["items"]:
        if x["id"]==i: return x
    raise KeyError(i)
def create(a):
    if not a.title.strip(): raise ValueError("title_required")
    if a.assignee not in AGENTS: raise ValueError("invalid_assignee")
    d=load_state(); now=utcnow()
    x={"id":"WB-"+secrets.token_hex(4).upper(),"title":a.title.strip(),"description":a.description.strip(),"status":"TODO","assignee":a.assignee,"created_at":now,"updated_at":now,"blocked_reason":None,"evidence":[],"history":[{"at":now,"event":"created","by":"owner"}]}
    d["items"].append(x); d["updated_at"]=utcnow(); write_state(d); print(json.dumps(x,indent=2))
def list_items(a):
    xs=load_state()["items"]
    if a.status: xs=[x for x in xs if x["status"]==a.status]
    if a.assignee: xs=[x for x in xs if x["assignee"]==a.assignee]
    print(json.dumps(xs,indent=2))
def show(a): print(json.dumps(find_item(load_state(),a.id),indent=2))
def assign(a):
    if a.assignee not in AGENTS: raise ValueError("invalid_assignee")
    d=load_state(); x=find_item(d,a.id); old=x["assignee"]
    x["assignee"]=a.assignee; x["updated_at"]=utcnow()
    x["history"].append({"at":utcnow(),"event":"assigned","from":old,"to":a.assignee,"by":"owner"})
    d["updated_at"]=utcnow(); write_state(d); print(json.dumps(x,indent=2))
def transition(a):
    target=a.status.upper()
    if target not in STATUSES: raise ValueError("invalid_status")
    d=load_state(); x=find_item(d,a.id); old=x["status"]
    if old in {"DONE","CANCELLED"} and target!=old: raise ValueError("terminal_status")
    if target=="BLOCKED" and not a.reason.strip(): raise ValueError("blocked_reason_required")
    x["status"]=target; x["blocked_reason"]=a.reason.strip() if target=="BLOCKED" else None
    x["updated_at"]=utcnow()
    x["history"].append({"at":utcnow(),"event":"transition","from":old,"to":target,"reason":a.reason.strip() or None})
    d["updated_at"]=utcnow(); write_state(d); print(json.dumps(x,indent=2))
def evidence(a):
    if not a.text.strip(): raise ValueError("evidence_required")
    d=load_state(); x=find_item(d,a.id)
    x["evidence"].append({"at":utcnow(),"text":a.text.strip()}); x["updated_at"]=utcnow()
    x["history"].append({"at":utcnow(),"event":"evidence_added"})
    d["updated_at"]=utcnow(); write_state(d); print(json.dumps(x,indent=2))
def parser():
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest="cmd",required=True)
    c=s.add_parser("create"); c.add_argument("--title",required=True); c.add_argument("--description",default=""); c.add_argument("--assignee",default="unassigned"); c.set_defaults(fn=create)
    l=s.add_parser("list"); l.add_argument("--status",choices=STATUSES); l.add_argument("--assignee",choices=AGENTS); l.set_defaults(fn=list_items)
    q=s.add_parser("show"); q.add_argument("id"); q.set_defaults(fn=show)
    a=s.add_parser("assign"); a.add_argument("id"); a.add_argument("assignee"); a.set_defaults(fn=assign)
    t=s.add_parser("transition"); t.add_argument("id"); t.add_argument("status"); t.add_argument("--reason",default=""); t.set_defaults(fn=transition)
    e=s.add_parser("evidence"); e.add_argument("id"); e.add_argument("--text",required=True); e.set_defaults(fn=evidence)
    return p
def main():
    a=parser().parse_args()
    try: a.fn(a)
    except KeyError as exc: raise SystemExit(f"work_item_not_found:{exc.args[0]}")
    except (ValueError,json.JSONDecodeError) as exc: raise SystemExit(str(exc))
if __name__=="__main__": main()
