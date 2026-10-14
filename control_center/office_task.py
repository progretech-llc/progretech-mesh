"""Bounded native mission tool. Run capability is issued by host orchestration."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from control_center.office import engine


def update(home, office, task, actor, run, payload):
    if not isinstance(payload, dict) or payload.get('action') not in {'comment','question','delegate'}:
        raise ValueError('invalid_mission_update')
    expected = {'action','text','to'} if payload['action']=='delegate' else {'action','text'}
    if set(payload)!=expected or not isinstance(payload['text'],str) or not 1<=len(payload['text'].strip())<=6000:
        raise ValueError('invalid_mission_update')
    if 'to' in payload and (not isinstance(payload['to'],str) or len(payload['to'])>80):
        raise ValueError('invalid_mission_update')
    result=engine(home,office,'mission.update',{'id':task,'actor':actor,'runId':run,**payload})
    return result['result']


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('home','office','task','actor','run'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    try:
        raw=sys.stdin.read(8193)
        if len(raw)>8192:raise ValueError('invalid_mission_update')
        print(json.dumps(update(args.home,args.office,args.task,args.actor,args.run,json.loads(raw))))
    except (ValueError,OSError) as exc:
        print(json.dumps({'ok':False,'error':str(exc) if isinstance(exc,ValueError) else 'mission_update_failed'}))
        sys.exit(1)
