"""Agent-owned Specklet JSON; task tracking never writes to Hindsight."""
import copy
import json
import os
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from control_center.file_lock import lock, unlock

ACTIONS = {'specklet.get', 'specklet.toggle', 'specklet.import', 'specklet.task'}
MAX_BYTES = 524288
FIELDS = ('projects', 'groups', 'tasks', 'datasets', 'charts', 'views')
STATES = {'open', 'doing', 'blocked', 'done', 'cancelled'}


def now(): return datetime.now(timezone.utc).isoformat()


def validate(action, args):
    expected = {'specklet.get': set(), 'specklet.toggle': {'enabled'},
                'specklet.import': {'workspace', 'revision'}, 'specklet.task': {'task', 'revision'}}
    if action not in expected or not isinstance(args, dict) or set(args) != expected[action]:
        raise ValueError('invalid_specklet_args')
    if len(json.dumps(args).encode()) > MAX_BYTES: raise ValueError('specklet_too_large')
    if action == 'specklet.toggle' and type(args['enabled']) is not bool: raise ValueError('invalid_specklet_toggle')
    if 'revision' in args and (type(args['revision']) is not int or args['revision'] < 0): raise ValueError('invalid_specklet_revision')
    if action == 'specklet.import': workspace(args['workspace'])
    if action == 'specklet.task': task(args['task'])


def task(value):
    if not isinstance(value, dict) or set(value) - {'id', 'title', 'notes', 'status', 'meshStatus', 'priority', 'position', 'projectId'}:
        raise ValueError('invalid_specklet_task')
    for key, v in value.items():
        if key == 'position':
            if type(v) is not int or not 0 <= v <= 100000: raise ValueError('invalid_specklet_position')
        elif not isinstance(v, str) or '\x00' in v or len(v) > (6000 if key == 'notes' else 240):
            raise ValueError('invalid_specklet_task')
    if 'id' in value and not value['id']: raise ValueError('invalid_specklet_task_id')
    if 'title' in value and not value['title'].strip(): raise ValueError('invalid_specklet_title')
    if value.get('meshStatus', value.get('status', 'open')) not in STATES: raise ValueError('invalid_specklet_status')
    if value.get('priority', 'medium') not in {'low','medium','high'}: raise ValueError('invalid_specklet_priority')


def workspace(value):
    if not isinstance(value, dict) or value.get('format') != 'specklet-browser-workspace' or value.get('formatVersion') != 2:
        raise ValueError('invalid_specklet_workspace')
    if value.get('schema') != 2 or any(not isinstance(value.get(k), list) for k in FIELDS): raise ValueError('invalid_specklet_workspace')
    if len(json.dumps(value).encode()) > MAX_BYTES - 2048: raise ValueError('specklet_too_large')
    if len(value['tasks']) > 500 or not value['projects']: raise ValueError('invalid_specklet_workspace')
    for key in FIELDS:
        ids = [v.get('id') if isinstance(v, dict) else None for v in value[key]]
        if any(not isinstance(i,str) or not i or len(i)>240 for i in ids) or len(set(ids))!=len(ids): raise ValueError('invalid_specklet_ids')
    projects={p['id'] for p in value['projects']}
    for p in value['projects']:
        if not isinstance(p.get('name'),str) or not p['name'].strip():raise ValueError('invalid_specklet_project')
    for t in value['tasks']:
        task({k:t[k] for k in ('id','title','notes','status','priority','position','projectId') if k in t})
        if not t.get('title') or t.get('projectId') not in projects:raise ValueError('invalid_specklet_task')
        if t.get('status') not in {'open','done','cancelled'}:raise ValueError('invalid_specklet_status')
    return copy.deepcopy(value)


class Board:
    def __init__(self, provider, agent):
        self.provider, self.agent = provider, agent
        self.path = provider._path(agent).with_suffix('.specklet.json')

    @contextmanager
    def guarded(self):
        with self.provider.lock:
            self.provider._path(self.agent)
            self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with self.path.with_suffix('.specklet.lock').open('a+') as guard:
                os.chmod(guard.name,0o600);lock(guard)
                try: yield
                finally: unlock(guard)

    def empty(self):
        project='mesh-'+self.agent
        at=now()
        return {'enabled':False,'revision':0,'history':[], 'workspace':{
            'schema':2,'format':'specklet-browser-workspace','formatVersion':2,'updatedAt':at,
            'projects':[{'id':project,'name':self.provider.bindings[self.agent]+' Task Board','description':'Mesh agent task tracking','status':'active','favorite':False,'nextProjectId':'','createdAt':at,'updatedAt':at}],
            'groups':[],'tasks':[],'datasets':[],'charts':[],'views':[]}}

    def read(self):
        if not self.path.exists():return self.empty()
        w=json.loads(self.path.read_text());meta=w.pop('mesh',{})
        return {'enabled':meta.get('enabled',False),'revision':meta.get('revision',0),'history':meta.get('history',[]),'workspace':w}

    def save(self, data, event):
        data['revision']+=1
        data['workspace']['updatedAt']=now()
        data['history'].append({'at':now(),**event})
        data['history']=data['history'][-250:]
        tmp=self.path.with_name(self.path.name+'.'+secrets.token_hex(8)+'.tmp')
        try:
            fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as stream:
                json.dump(self.response(data)['workspace'],stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
            tmp.replace(self.path)
        finally:
            if tmp.exists():tmp.unlink()

    def response(self,data):
        w=copy.deepcopy(data['workspace']);w['exportedAt']=now()
        # Owner history is portable but never trusted to change host permissions.
        w['mesh']={'agentId':self.agent,'enabled':data['enabled'],'revision':data['revision'],'history':copy.deepcopy(data['history'])}
        return {'enabled':data['enabled'],'revision':data['revision'],'workspace':w,'localFile':str(self.path),'history':data['history'][-50:]}

    def dispatch(self,action,args,agent_write=False):
        validate(action,args)
        with self.guarded():
            data=self.read()
            if agent_write and not data['enabled']:raise ValueError('specklet_disabled')
            if 'revision' in args and args['revision'] != data['revision']:raise ValueError('specklet_revision_conflict')
            if action=='specklet.toggle':
                if data['enabled']!=args['enabled']:
                    data['enabled']=args['enabled'];self.save(data,{'kind':'toggle','enabled':data['enabled']})
            elif action=='specklet.import':
                incoming=workspace(args['workspace']);incoming.pop('mesh',None)
                # Specklet can edit open/done/cancelled; preserve richer runtime
                # phase only while its compatible status has not changed.
                for t in incoming['tasks']:
                    phase=t.get('meshStatus')
                    if phase not in STATES or compatible(phase)!=t['status']:t['meshStatus']=t['status']
                data['workspace']=incoming
                self.save(data,{'kind':'owner.import','tasks':len(incoming['tasks'])})
            elif action=='specklet.task':
                self.upsert(data,args['task'],'agent' if agent_write else 'owner')
            return self.response(data)

    def upsert(self,data,patch,author,observed=None):
        task(patch)
        ident=patch.get('id') or secrets.token_hex(16)
        rows=data['workspace']['tasks'];existing=next((t for t in rows if t['id']==ident),None)
        before=copy.deepcopy(existing)
        if existing is None:
            if len(rows)>=500:raise ValueError('specklet_task_capacity')
            if not patch.get('title'):raise ValueError('specklet_title_required')
            existing={'id':ident,'projectId':data['workspace']['projects'][0]['id'],'groupId':'','parentTaskId':'','title':patch['title'],
                'notes':'','status':'open','meshStatus':'open','bulletKind':'task','priority':'medium','dueDate':'','position':len(rows),'source':{'type':'mesh'},'migrationHistory':[],'createdAt':now()}
            rows.append(existing)
        if patch.get('projectId',existing['projectId']) not in {p['id'] for p in data['workspace']['projects']}:raise ValueError('invalid_specklet_project')
        existing.update(patch)
        if observed is not None:existing['meshObservedStatus']=observed
        phase=patch.get('meshStatus',patch.get('status',existing.get('meshStatus','open')))
        existing.update(meshStatus=phase,status=compatible(phase),updatedAt=now())
        # Bound full workspace so every generated export remains uploadable.
        if len(json.dumps(data['workspace']).encode())>MAX_BYTES//2:raise ValueError('specklet_too_large')
        self.save(data,{'kind':author+'.task','id':ident,'before':before.get('meshStatus',before.get('status')) if before else None,'after':phase})
        return existing

    def observe(self, ident, title, phase):
        with self.guarded():
            data=self.read()
            if not data['enabled']:return
            t=next((t for t in data['workspace']['tasks'] if t['id']==ident),None)
            if t and t.get('meshObservedStatus')==phase:return
            patch={'id':ident,'meshStatus':phase}
            if not t:patch['title']=title
            self.upsert(data,patch,'runtime',observed=phase)


def compatible(phase):return phase if phase in {'done','cancelled'} else 'open'


def dispatch(provider,agent,action,args):return Board(provider,agent).dispatch(action,args)


def observe_office(provider,home,office_role,snapshot):
    from control_center.office import namespace
    with provider.lock: ids=list(provider.bindings.items())
    for agent,runtime in ids:
        if namespace(runtime,agent)!=office_role:continue
        for row in snapshot.get('tasks',[]):
            phase={'todo':'open','doing':'doing','blocked':'blocked','done':'done'}.get(row.get('status'))
            if phase:Board(provider,agent).observe('office-'+row['id'],row.get('title','Factory mission')[:240],phase)


def start_observer(provider,home):
    """Observe published native ledger changes without running agents or models."""
    import threading
    from control_center.management import preferences
    from control_center.mesh_runtime import ROLE_NAMES
    home=Path(home)
    def tick():
        path=home/'.local/state/progretech-workday/activity.json'
        if not path.is_file():return
        payload=json.loads(path.read_text())
        with provider.lock: ids=list(provider.bindings.items())
        for agent,runtime in ids:
            if not preferences(provider,agent)['enabled']:continue
            board=Board(provider,agent)
            with board.guarded():enabled=board.read()['enabled']
            if not enabled:continue
            role=ROLE_NAMES.get(runtime,runtime)
            for t in payload.get('tasks',[])[-100:]:
                if t.get('role')!=role or not isinstance(t.get('id'),str):continue
                phase={'queued':'open','running':'doing','completed':'done','done':'done','failed':'blocked','uncertain':'blocked','review':'blocked','interrupted':'blocked','blocked':'blocked','missed':'cancelled','cancelled':'cancelled','skipped':'cancelled'}.get(t.get('state'))
                if phase:board.observe('workday-'+t['id'],'Factory '+str(t.get('phase','task'))[:200],phase)
    def run():
        while True:
            try:tick();provider.specklet_observer_error=None
            except (ValueError,KeyError,OSError):provider.specklet_observer_error='specklet_factory_sync_failed'
            threading.Event().wait(2)
    provider.specklet_tick=tick
    threading.Thread(target=run,daemon=True,name='mesh-specklet-observer').start()
