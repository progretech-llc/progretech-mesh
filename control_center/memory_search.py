"""Explicit host sharing of shared project records; no private scope or cloud copy."""
import json
from pathlib import Path
from control_center.artifacts import ROLES

ACTIONS = {'memory.status', 'memory.share', 'memory.search'}


def validate(action, args):
    fields = {'memory.status': set(), 'memory.share': {'enabled'}, 'memory.search': {'query', 'project'}}
    if not isinstance(args, dict) or action not in fields or set(args) != fields[action]:
        raise ValueError('invalid_memory_args')
    if action == 'memory.share' and type(args['enabled']) is not bool:
        raise ValueError('invalid_memory_args')
    if action == 'memory.search':
        if any(not isinstance(args[k], str) or not args[k].strip() or '\x00' in args[k] for k in args):
            raise ValueError('invalid_memory_args')
        if len(args['query']) > 200 or args['project'] not in {'ProgreTech', 'Local-Workstation'}:
            raise ValueError('invalid_memory_args')


def database(home):
    # Compatibility name for callers; returns the service configuration, not a DB.
    config = Path('/mnt/pt-context/factory-support/hindsight/config/client.json')
    return config if config.is_file() else None


def memory_store(home, role):
    import sys
    runtime = str(Path(home)/'.local/share/progretech/hindsight-runtime')
    if runtime not in sys.path: sys.path.insert(0,runtime)
    from factory_hindsight.store import HindsightStore
    return HindsightStore(database(home),'factory-worker',read_only=True)


def dispatch(provider, home, agent_id, action, args):
    from control_center.management import preferences, save_preferences
    validate(action, args)
    role = ROLES.get(provider.bindings[agent_id])
    path = database(home)
    available = role is not None and path is not None
    if action == 'memory.share':
        if args['enabled'] and not available: raise ValueError('hindsight_unavailable')
        save_preferences(provider, agent_id, {'memory_shared': args['enabled']})
    shared = preferences(provider, agent_id).get('memory_shared', False) is True
    status = {'available': available, 'shared': shared, 'author': role,
              'scope': 'shared-project', 'projects': ['ProgreTech', 'Local-Workstation'],
              'retention': 'host-only; ephemeral relay', 'private_included': False, 'provider': 'hindsight'}
    if action != 'memory.search': return status
    if not shared: raise ValueError('memory_sharing_required')
    if not available: raise ValueError('hindsight_unavailable')
    try:
        store = memory_store(home, role)
        rows = store.search(args['query'],scope='project',project_id=args['project'],author_id=role,limit=10,semantic=True)
        result=[]
        for row in rows:
            if row.get('scope')!='project' or row.get('status')!='active' or row.get('author_id')!=role or row.get('author_type')!='agent':continue
            if str(row.get('project_id','')).casefold()!=args['project'].casefold():continue
            record={key:row.get(key) for key in ('memory_id','title','content','author_id','project_id','scope','provenance_type','provenance_ref','created_at','confidence')}
            for key in record:
                if isinstance(record[key],str):record[key]=record[key][:8000 if key=='content' else 500]
            record['truncated']=len(row['content'])>8000
            result.append(record)
        if preferences(provider,agent_id).get('memory_shared',False) is not True:raise ValueError('memory_sharing_required')
        return {**status,'records':result,'provider':'hindsight'}
    except Exception as exc:
        if isinstance(exc,ValueError) and str(exc)=='memory_sharing_required':raise
        raise ValueError('hindsight_search_unavailable') from None
