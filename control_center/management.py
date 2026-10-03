"""Host-local persisted communication preferences and explicit Mesh opt-out."""
import json
import os
import re

ACTIONS = {'communication.get', 'communication.save', 'communication.chat', 'enrollment.remove', 'factory.providers', 'factory.run', 'factory.job', 'factory.office'}
ACTIONS |= {'communication.start', 'communication.job', 'runtime.status', 'runtime.wake', 'runtime.sleep', 'runtime.context', 'runtime.recover', 'runtime.snapshot'}
ACTIONS |= {'communication.new','context.read'}
ACTIONS |= {'memory.status', 'memory.share', 'memory.search'}
ACTIONS |= {'specklet.get', 'specklet.toggle', 'specklet.import', 'specklet.task'}
ACTIONS |= {'chatter.configure','chatter.history','chatter.pair','chatter.group','chatter.topic','handoff.create','handoff.list','handoff.control'}
ACTIONS |= {'files.begin','files.chunk','files.finish','files.cancel','files.list','files.read','files.reference'}


def validate_management(action, args):
    if isinstance(action,str) and action.startswith("specklet."):
        from control_center.specklet import validate
        return validate(action,args)
    if isinstance(action,str) and action.startswith("memory."):
        from control_center.memory_search import validate
        return validate(action,args)
    if action.startswith('handoff.') or action in {'chatter.configure','chatter.history','chatter.pair','chatter.group','chatter.topic'}:
        from control_center.handoffs import validate
        return validate(action,args)
    if action.startswith('files.'):
        from control_center.artifacts import validate
        return validate(action,args)
    if action == 'factory.office':
        from control_center.office import validate_office
        return validate_office(args)
    if not isinstance(args, dict) or len(json.dumps(args)) > 8192:
        raise ValueError('invalid_args')
    fields = {'communication.save': {'role', 'model'}, 'communication.chat': {'text'}, 'communication.start': {'text'}, 'communication.job': {'job_id'}, 'runtime.context': {'text'}, 'runtime.snapshot': {'kind'}, 'factory.run': {'provider', 'task'}, 'factory.job': {'job_id'}}.get(action, set())
    if set(args) != fields or any(not isinstance(v, str) or not v.strip() or '\x00' in v for v in args.values()):
        raise ValueError('invalid_args')
    for key, value in args.items():
        if len(value) > (4000 if key in {'text', 'task'} else 160):
            raise ValueError('invalid_args')
    if action == 'factory.run' and args['provider'] not in {'crewai', 'openhands'}:
        raise ValueError('invalid_provider')
    if action == 'factory.job' and not re.fullmatch('[a-f0-9]{32}', args['job_id']):
        raise ValueError('invalid_job_id')
    if action == 'communication.job' and not re.fullmatch('[a-f0-9]{32}', args['job_id']):
        raise ValueError('invalid_job_id')
    if action == 'runtime.snapshot' and args['kind'] not in {'task','terminal'}:
        raise ValueError('invalid_snapshot_kind')


def save_preferences(provider, agent_id, changes):
    with provider.lock:
        current=preferences(provider,agent_id)
        current.update(changes)
        provider.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        path=provider._path(agent_id).with_suffix('.communication.json')
        import secrets
        temporary=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
        try:
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as stream:
                json.dump(current,stream);stream.flush();os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            if temporary.exists():temporary.unlink()


def preferences(provider, agent_id):
    path = provider._path(agent_id).with_suffix('.communication.json')
    return json.loads(path.read_text()) if path.exists() else {'role': provider.bindings[agent_id], 'model': 'default', 'enabled': True}


def dispatch(provider, agent_id, action, args):
    validate_management(action, args)
    with provider.lock:
        provider._path(agent_id)
        runtime = provider.bindings[agent_id]
        current = preferences(provider, agent_id)
        if not current['enabled']:
            raise ValueError('mesh_enrollment_removed')
        runtime_control=getattr(provider,'mesh_runtime',None)
        if action in {'communication.chat','communication.start'} and runtime_control:
            try:asleep=runtime_control.sleeping(agent_id)
            except (ValueError,KeyError,OSError):asleep=False
            if asleep:raise ValueError('mesh_agent_sleeping')
        inventory = provider.discover(runtime)
        if action == 'communication.get':
            from control_center.conversation_sync import history
            conversation=history(getattr(provider,'home',__import__('pathlib').Path.home()),runtime)
            return {'conversation':conversation,'settings': current, 'roles': inventory.get('communication_roles', [runtime]), 'models': ['default', *inventory.get('communication_models', inventory.get('models', []))], 'runtime_id': runtime}
        if action in {'communication.save', 'enrollment.remove'}:
            if action == 'communication.save':
                if args['role'] not in inventory.get('communication_roles', [runtime]) or args['model'] not in ['default', *inventory.get('communication_models', inventory.get('models', []))]:
                    raise ValueError('communication_selection_unavailable')
                current.update(args)
            else:
                current['enabled'] = False
            provider.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = provider._path(agent_id).with_suffix('.communication.json')
            fd = os.open(path.with_suffix('.tmp'), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as stream: json.dump(current, stream)
            path.with_suffix('.tmp').replace(path)
            return {'saved': True, 'settings': current, 'scope': 'agent-local'}
    # Never hold the profile lock during a model call or a factory job.
    return provider.execute(runtime, action, args, {'communication': current, 'agent_id': agent_id})
