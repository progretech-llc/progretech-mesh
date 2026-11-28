"""Reviewed cross-client handoff notes, explicitly published on the owner's host."""
import json
import re
from pathlib import Path


def context_path(home, gateway, runtime):
    if any(not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', s) for s in (gateway,runtime)):
        raise ValueError('invalid_context_identity')
    return Path(home)/'.progretech-mesh/shared-context'/gateway/(runtime+'.json')


def read_context(home, gateway, runtime):
    try:
        data=json.loads(context_path(home,gateway,runtime).read_text())
        return {k:str(data.get(k,''))[:12000] for k in ('author','text','updated_at','source')}
    except FileNotFoundError:
        return {'text':'','source':'No reviewed cross-client handoff published'}


def mission_context(home, gateway, host_runtime, runtime):
    from control_center.office import office_root, namespace
    root=office_root(home,namespace(host_runtime,gateway))
    try:
        settings=json.loads((root/'mesh-office.json').read_text())
        registry=json.loads((root/'hive/registry.json').read_text())
        aid=next((k for k,v in settings.get('runtimeBindings',{}).items() if v==runtime),None)
        if not aid:return ''
        tasks=json.loads((root/'hive/tasks.json').read_text()).get('tasks',[])
        return '\n\n'.join(t.get('title','')+'\n'+t['result'] for t in tasks if t.get('result') and (aid==registry.get('godId') or t.get('assignee')==aid))[-12000:]
    except (FileNotFoundError,ValueError,KeyError):return ''
