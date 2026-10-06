"""Host-local Mesh office; upstream HiveManager is the coordination authority."""
import os
import hashlib
import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from control_center.file_lock import lock, unlock

SPECKLET_OBSERVER=None

PUBLIC_OPERATIONS = {'orchestrator.set', 'restore', 'snapshot', 'hire', 'archive', 'task.priority', 'task.create', 'task.approve', 'message', 'pause', 'settings', 'memory', 'memory.save', 'run', 'workday.control', 'mailbox.list', 'mailbox.edit', 'mailbox.remove', 'mailbox.priority'}


def validate_office(args):
    if not isinstance(args, dict) or set(args) != {'operation', 'args'} or args['operation'] not in PUBLIC_OPERATIONS:
        raise ValueError('invalid_office_operation')
    op, body = args['operation'], args['args']
    fields = {'orchestrator.set': {'id'}, 'restore': {'id'}, 'task.priority': {'id','priority'}, 'hire': {'name', 'role', 'goal'}, 'archive': {'id'}, 'task.create': {'title', 'description', 'assignee', 'dependsOn', 'needsApproval'},
        'task.approve': {'id', 'answer'}, 'message': {'to', 'text'}, 'pause': {'paused'}, 'settings': {'maxIterations'},
        'memory': {'id'}, 'memory.save': {'id', 'text'}, 'run': {'id'}, 'workday.control': {'action','role','duration'}, 'mailbox.list': {'agent'}, 'mailbox.edit': {'agent','id','text'}, 'mailbox.remove': {'agent','id'}, 'mailbox.priority': {'agent','id','priority'}}.get(op, set())
    if not isinstance(body, dict) or set(body) != fields:
        raise ValueError('invalid_office_args')
    for key, value in body.items():
        if key == 'priority':
            if type(value) is not int or not -100 <= value <= 100: raise ValueError('invalid_mailbox_priority')
        elif key in {'paused', 'needsApproval'}:
            if type(value) is not bool: raise ValueError('invalid_office_args')
        elif key == 'maxIterations':
            if type(value) is not int or not 2 <= value <= 20: raise ValueError('invalid_office_args')
        elif key == 'dependsOn':
            if not isinstance(value, list) or len(value) > 20 or any(not isinstance(x, str) or not re.fullmatch('task-[a-f0-9]{12}', x) for x in value):
                raise ValueError('invalid_dependency')
        elif not isinstance(value, str) or '\x00' in value or len(value) > (6000 if key == 'text' else 4000 if key in {'description', 'goal'} else 160):
            raise ValueError('invalid_office_args')
        elif key not in {'assignee', 'description'} and not value.strip():
            raise ValueError('invalid_office_args')
    if len(json.dumps(args)) > 16384: raise ValueError('invalid_office_args')
    if op == 'workday.control':
        if body['action'] not in {'stop','pause','resume','sleep'} or body['role'] not in {'all','rend','lyra','mak','imagen','progre'}:
            raise ValueError('invalid_workday_control')
        if not re.fullmatch(r'\d+(s|m|h|d)',body['duration']): raise ValueError('invalid_workday_duration')


def office_root(home, role):
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}', role): raise ValueError('invalid_office_role')
    return Path(home) / '.progretech-mesh/factory-offices' / role


def engine(home, role, operation, args=None):
    root = office_root(home, role)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    node = os.environ.get('MESH_OFFICE_NODE') or shutil.which('node')
    if not node: raise ValueError('office_node_runtime_required')
    script = Path(__file__).resolve().parent.parent / 'office/engine.mjs'
    with (root / 'mesh-engine.lock').open('a+') as guard:
        lock(guard)
        try:
            result = subprocess.run([node, str(script)], input=json.dumps({'home': str(root), 'operation': operation, 'args': args or {}}),
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        finally:
            unlock(guard)
    if result.returncode:
        # Only known machine codes cross the relay; full runtime diagnostics stay local.
        for code in ('task_not_ready', 'office_paused', 'office_capacity', 'agent_has_open_tasks', 'director_required', 'office_agent_not_found', 'dependency_not_found', 'approval_not_pending', 'office_role_already_exists', 'mailbox_item_not_pending', 'mailbox_busy'):
            if code in result.stderr: raise ValueError(code)
        raise ValueError('office_coordination_failed')
    payload=json.loads(result.stdout)
    from control_center.conversation_sync import tasks
    try:tasks(home,role,payload.get('snapshot',{}),payload.get('result',{}).get('id') if operation=='task.create' else None)
    except (ValueError,OSError):payload['conversation_sync_error']='task_sync_unavailable'
    if SPECKLET_OBSERVER:
        try:SPECKLET_OBSERVER(role,payload.get('snapshot',{}))
        except (ValueError,OSError):payload['specklet_error']='specklet_office_sync_failed'
    return payload


def namespace(role, agent_id=None):
    return role if not agent_id else role + "--" + hashlib.sha256(agent_id.encode()).hexdigest()[:16]


def native_binding(provider, gateway, runtime_id):
    """Resolve an office runtime only inside its enrolled gateway namespace."""
    if provider.bindings.get(gateway) == runtime_id:
        return gateway
    prefix = gateway + '--'
    return next((agent for agent, runtime in provider.bindings.items()
                 if agent.startswith(prefix) and runtime == runtime_id), None)


def dispatch_native_mission(home, role, task_id, gateway, provider, mesh):
    """Run a Factory mission through its real bound OpenClaw role.

    CrewAI remains available when explicitly configured, but the connected
    native roster must not leave the Start mission control inert.
    """
    office_role = namespace(role, gateway)
    mission = engine(home, office_role, 'begin', {'id': task_id})['result']
    task = mission['task']
    target = next((row for row in mission['agents'] if row['id'] == task['assignee']), None)
    binding = native_binding(provider, gateway, target.get('runtime_id') if target else None)
    if not binding:
        engine(home, office_role, 'finish', {'id': task_id, 'ok': False,
            'result': 'The assigned office role has no connected native runtime binding.'})
        raise ValueError('office_runtime_binding_required')
    prompt = (
        'Owner-authorized Mesh Factory mission. Use your current role, tools, '
        'approval gates, and repository/task ledgers. Coordinate or delegate when '
        'that is your role; do not claim completion without evidence.\n\n'
        'Mission: ' + task['title'] + '\n\n' + (task.get('description') or task['title'])
    )
    try:
        job = mesh.chat(binding, prompt, owner_text=task.get('description') or task['title'])
    except Exception:
        engine(home, office_role, 'finish', {'id': task_id, 'ok': False,
            'result': 'The native runtime did not accept the mission. Review host status before retrying.'})
        raise

    def monitor():
        deadline = time.monotonic() + 7200
        try:
            while time.monotonic() < deadline:
                result = mesh.get(binding, job['job_id'])
                if result.get('done'):
                    error = result.get('error')
                    reply = result.get('result', {}).get('reply', '')
                    engine(home, office_role, 'finish', {'id': task_id, 'ok': not error,
                        'result': (error or reply or 'Mission completed without a text result.')[:6000]})
                    return
                time.sleep(2)
            engine(home, office_role, 'finish', {'id': task_id, 'ok': False,
                'result': 'Mission completion was not confirmed within two hours.'})
        except Exception:
            try:
                engine(home, office_role, 'finish', {'id': task_id, 'ok': False,
                    'result': 'Mission status became unavailable; inspect the native runtime before retrying.'})
            except Exception:
                pass

    threading.Thread(target=monitor, daemon=True, name='mesh-office-mission').start()
    return {'job_id': job['job_id'], 'state': 'queued', 'provider': 'openclaw'}


def dispatch_office(home, role, args, agent_id=None):
    validate_office(args)
    if args['operation'] == 'workday.control':
        body=args['args']; command=[str(Path(home)/'Rend/bin/factory-workday'),body['action'],'--agent',body['role']]
        if body['action']=='sleep': command += ['--for',body['duration']]
        result=subprocess.run(command,capture_output=True,text=True,timeout=90,check=False)
        if result.returncode: raise ValueError('workday_control_failed')
        snapshot=dispatch_office(home,role,{'operation':'snapshot','args':{}},agent_id)
        snapshot['workday']=json.loads(result.stdout)
        return snapshot
    if args['operation'] == 'run':
        from control_center.factory_jobs import dispatch_factory
        return dispatch_factory(home, role, 'factory.run', {'provider': 'crewai', 'task': '', 'office_task': args['args']['id']}, office_id=agent_id)
    result = engine(home, namespace(role, agent_id), args['operation'], args['args'])
    activity=Path(home)/'.local/state/progretech-workday/activity.json'
    try:
        payload=json.loads(activity.read_text())
        import time
        fresh=time.time()-activity.stat().st_mtime<90
        result['snapshot']['factoryAgents']=[dict(v,id=k,state=v.get('state','unknown') if fresh else 'unknown') for k,v in payload.get('agents',{}).items()]
        result['snapshot']['factoryObservedAt']=payload.get('updated_at')
        result['snapshot']['workdayTasks']=[{k:t.get(k) for k in ('id','role','phase','state','day','slot','started','finished')} for t in payload.get('tasks',[])][:30]
    except (OSError,ValueError): result['snapshot']['factoryAgents']=[]
    try:
        entries=json.loads((Path(home)/'.openclaw/openclaw.json').read_text())['agents']['entries']
        for runtime in entries:
            role_id={'main':'rend','researcher':'lyra','coder':'mak'}.get(runtime,runtime)
            if not any(a.get('runtime_id')==runtime or a['id']==role_id for a in result['snapshot']['factoryAgents']):
                row={'id':role_id,'runtime_id':runtime,'state':'unknown','role':'Configured OpenClaw role'}
                if runtime=='imagen':row.update(role='Image generation specialist',capability='image_generation')
                result['snapshot']['factoryAgents'].append(row)
    except (OSError,ValueError,KeyError,TypeError):pass
    from control_center.mesh_runtime import role_controls, is_sleeping, read_signals
    try: controls=role_controls(home)
    except (ValueError,OSError,subprocess.SubprocessError): controls={}
    signals=read_signals(home)
    for row in result['snapshot']['factoryAgents']:
        ctrl=controls.get(row['id'])
        row['sleeping']=is_sleeping(ctrl) if ctrl else None
        row['last_result']=signals.get(row.get('runtime_id'),{})
        from control_center.memory_status import memory_status
        row['memory']=memory_status(home,row['id'])
        if row['sleeping']:row['state']='sleeping'
    from control_center.office_relations import interactions
    result['snapshot']['interactions']=interactions(result['snapshot'],home)
    from control_center.mesh_runtime import sync_gateway_status_file
    sync_gateway_status_file(home)
    try:
        gateway_status=json.loads((Path(home)/'.progretech-mesh/gateway-status.json').read_text())
        result['snapshot']['gatewayStatus']=gateway_status
    except (OSError,ValueError):
        result['snapshot']['gatewayStatus']={'state':'unavailable','note':'Gateway status snapshot not yet available.'}
    from control_center.factory_jobs import _config
    settings = _config(home).get('crewai', {})
    result['snapshot']['runtimeReady'] = bool(settings.get('enabled') and role in settings.get('roles', []) and Path(settings.get('python', '')).is_file())
    return result
