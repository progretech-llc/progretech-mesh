"""Host-owned progress jobs and shared agent availability through Factory controls."""
import copy
import json
import secrets
import subprocess
import threading
import time
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen


_CONTROL_CACHE = {}
_CONTROL_LOCK = threading.Lock()
ROLE_NAMES = {'main':'rend','researcher':'lyra','coder':'mak','progre':'progre','imagen':'imagen','codex':'codex','moxy':'moxy'}
SIGNAL_TTL_SECONDS = 900


def gateway_activity_idle(data):
    """Read both current and legacy OpenClaw activity counters strictly."""
    work = data.get('shutdownBudget', {}).get('activeWork')
    if not isinstance(work, dict) or not work or any(type(v) is not int or v < 0 for v in work.values()):
        raise ValueError('runtime_activity_unavailable')
    tasks = data.get('tasks')
    if tasks is None:
        active_tasks = 0  # OpenClaw 2026.9.8 removed the redundant tasks block.
    elif isinstance(tasks, dict) and type(tasks.get('active')) is int and tasks['active'] >= 0:
        active_tasks = tasks['active']
    else:
        raise ValueError('runtime_activity_unavailable')
    return not sum(work.values()) and active_tasks == 0


def sync_gateway_status_file(home):
    """Persist a bounded, credential-free OpenClaw status snapshot for Mesh."""
    try:
        result=subprocess.run(['openclaw','gateway','call','status','--json'],capture_output=True,text=True,timeout=12)
        if result.returncode:raise ValueError('gateway_status_unavailable')
        raw=json.loads(result.stdout)
        snapshot={'observed_at':time.time(),'runtimeVersion':raw.get('runtimeVersion'),
            'tasks':raw.get('tasks',{}),'taskAudit':raw.get('taskAudit',{}),
            'heartbeat':raw.get('heartbeat',{}),'sessions':raw.get('sessions',{}),
            'degradedSecretOwners':raw.get('degradedSecretOwners',[]),
            'degradedPlugins':raw.get('degradedPlugins',[])}
        path=Path(home)/'.progretech-mesh/gateway-status.json';path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        temporary=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
        import os
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(snapshot,stream);stream.flush();os.fsync(stream.fileno())
        temporary.replace(path)
        return snapshot
    except (OSError,ValueError,subprocess.SubprocessError,json.JSONDecodeError):
        return None


def role_controls(home, refresh=False):
    key=str(home)
    with _CONTROL_LOCK:
        saved=_CONTROL_CACHE.get(key)
        if saved and not refresh and time.monotonic()-saved[0]<1:return copy.deepcopy(saved[1])
        command=Path(home)/'Rend/bin/factory-workday'
        if not command.is_file():raise ValueError('runtime_controls_unavailable')
        result=subprocess.run([str(command),'status'],capture_output=True,text=True,timeout=10)
        if result.returncode:raise ValueError('runtime_controls_unavailable')
        data=json.loads(result.stdout)
        rows={row['role']:{k:row.get(k) for k in ('mode','until')} for row in data['controls'] if row.get('role') in ROLE_NAMES.values()}
        _CONTROL_CACHE[key]=(time.monotonic(),rows)
        return copy.deepcopy(rows)


def is_sleeping(row):
    return row['mode'] != 'running' and not (row['mode']=='sleeping' and row.get('until') is not None and row['until']<=time.time())


def provider_error(exc):
    if isinstance(exc,TimeoutError) or (isinstance(exc,URLError) and isinstance(exc.reason,TimeoutError)):
        return 'mesh_reply_timeout'
    if isinstance(exc,HTTPError):
        text=exc.read(8192).decode('utf-8',errors='replace').lower()
        if any(word in text for word in ('context overflow','context size','context length','exceed_context','prompt too large')):
            return 'mesh_context_limit'
        if exc.code==400:return 'mesh_provider_rejected'
        return 'mesh_provider_unavailable'
    if isinstance(exc,TimeoutError):return 'mesh_reply_timeout'
    return 'mesh_provider_unavailable'


def read_signals(home):
    try:data=json.loads((Path(home)/'.progretech-mesh/agent-signals.json').read_text())
    except (OSError,ValueError):data={}
    for role in ROLE_NAMES:
        try:
            row=json.loads((Path(home)/'.progretech-mesh/agent-signals'/f'{role}.json').read_text())
            if isinstance(row,dict) and isinstance(row.get('at'),(int,float)) and time.time()-row['at']>SIGNAL_TTL_SECONDS and row.get('severity')=='error':
                row={'severity':'unknown','code':'stale_signal','at':row['at'],'stale':True,'previous_severity':'error','previous_code':row.get('code')}
            data[role]=row
        except (OSError,ValueError):pass
    return data


class MeshRuntime:
    def __init__(self, provider, home, opener=urlopen):
        self.provider, self.home, self.open = provider, home, opener
        self.jobs = {}
        self.health_cache = {}
        self.lock = threading.RLock()
        self.inference = threading.Lock()
        self.gateway_status_checked = 0.0

    def sync_gateway_status(self):
        """Persist a bounded, credential-free OpenClaw status snapshot for Mesh."""
        now=time.time()
        if now-self.gateway_status_checked<10:return
        self.gateway_status_checked=now
        try:
            result=subprocess.run(['openclaw','gateway','call','status','--json'],capture_output=True,text=True,timeout=12)
            if result.returncode:raise ValueError('gateway_status_unavailable')
            raw=json.loads(result.stdout)
            snapshot={'observed_at':now,'runtimeVersion':raw.get('runtimeVersion'),
                'tasks':raw.get('tasks',{}),'taskAudit':raw.get('taskAudit',{}),
                'heartbeat':raw.get('heartbeat',{}),'sessions':raw.get('sessions',{}),
                'degradedSecretOwners':raw.get('degradedSecretOwners',[]),
                'degradedPlugins':raw.get('degradedPlugins',[])}
            path=self.home/'.progretech-mesh/gateway-status.json';path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            temporary=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
            import os
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as stream:json.dump(snapshot,stream);stream.flush();os.fsync(stream.fileno())
            temporary.replace(path)
        except (OSError,ValueError,subprocess.SubprocessError,json.JSONDecodeError):
            return

    def settings(self, agent):
        from control_center.management import preferences
        with self.provider.lock:
            self.provider._path(agent)
            return preferences(self.provider, agent)

    def config(self, agent):
        cfg = json.loads((self.home / '.openclaw/openclaw.json').read_text())
        role = self.provider.bindings[agent]
        chosen = self.settings(agent).get('model', 'default')
        model = cfg['agents']['entries'][role].get('model', cfg['agents'].get('defaults', {}).get('model', {}))
        chosen = chosen if chosen != 'default' else model if isinstance(model, str) else model.get('primary', '')
        return cfg, role, chosen

    def api(self, path, body=None, timeout=5):
        # Only the established local Ollama endpoint; no cloud-supplied URL.
        request = Request('http://127.0.0.1:11434/api/' + path,
                          data=None if body is None else json.dumps(body).encode(),
                          headers={'Content-Type':'application/json'})
        with self.open(request, timeout=timeout) as response:
            return json.loads(response.read(1048576))

    def model(self, agent):
        cfg, _, chosen = self.config(agent)
        provider = cfg.get('models', {}).get('providers', {}).get('ollama', {})
        if not chosen.startswith('ollama/') or provider.get('baseUrl', '').rstrip('/') != 'http://127.0.0.1:11434':
            raise ValueError('local_preload_unavailable')
        return chosen.split('/',1)[1]

    def health(self, agent):
        """Bounded read-only checks; no inference, replay, restart or signal writes."""
        now=time.time()
        try:
            cfg,role,chosen=self.config(agent)
            port=cfg.get('gateway',{}).get('port',18789)
            if type(port) is not int or not 1<=port<=65535:raise ValueError('runtime_port_invalid')
            if not isinstance(chosen,str):raise ValueError('model_not_configured')
            key=(role,chosen,port)
            with self.lock:
                cached=self.health_cache.get(key)
                if cached and now-cached['checked_at']<30:return copy.deepcopy(cached)
            result={'state':'unknown','checked_at':now,'gateway_reachable':False,'model_provider_reachable':None,'configured_model_installed':None}
            try:
                with self.open(Request(f'http://127.0.0.1:{port}/healthz'),timeout=2) as response:
                    data=json.loads(response.read(65536))
                result['gateway_reachable']=isinstance(data,dict) and data.get('ok') is True
            except (OSError,ValueError,URLError):pass
            if chosen.startswith('ollama/'):
                provider=cfg.get('models',{}).get('providers',{}).get('ollama',{})
                if provider.get('baseUrl','').rstrip('/')=='http://127.0.0.1:11434':
                    try:
                        models=self.api('tags',timeout=2).get('models',[])
                        result['model_provider_reachable']=True
                        result['configured_model_installed']=chosen.split('/',1)[1] in {m['name'] for m in models}
                    except (OSError,ValueError,URLError,KeyError,TypeError):result['model_provider_reachable']=False
            if not result['gateway_reachable'] or result['model_provider_reachable'] is False or result['configured_model_installed'] is False:result['state']='unavailable'
            elif result['model_provider_reachable'] and result['configured_model_installed']:result['state']='reachable'
            with self.lock:self.health_cache[key]=result
            return copy.deepcopy(result)
        except (OSError,ValueError,KeyError):return {'state':'unknown','checked_at':now}

    def status(self, agent):
        from control_center.memory_status import memory_status
        from control_center.specklet import Board
        board=Board(self.provider,agent)
        with board.guarded():specklet=board.read()['enabled']
        memory=memory_status(self.home,ROLE_NAMES.get(self.provider.bindings[agent],self.provider.bindings[agent]))
        signal=read_signals(self.home).get(self.provider.bindings[agent],{})
        health=self.health(agent) if signal.get('severity')=='error' else None
        try: configured_model = self.config(agent)[2]
        except (OSError, ValueError, KeyError): configured_model = ''
        try:asleep = self.sleeping(agent)
        except (ValueError,KeyError,OSError,subprocess.SubprocessError):
            return {'specklet_enabled':specklet,'specklet_error':getattr(self.provider,'specklet_observer_error',None),'memory':memory,'scope':'agent','sleeping':None,'model':configured_model,'resident':None,'preload_available':False,'controls_available':False,'last_result':signal,'health':health}
        try:
            model = self.model(agent)
            names = {m['name'] for m in self.api('ps').get('models',[])}
            resident = model in names
            return {'specklet_enabled':specklet,'specklet_error':getattr(self.provider,'specklet_observer_error',None),'memory':memory,'scope':'agent', 'sleeping':asleep, 'model':model, 'resident':resident, 'preload_available':True,'controls_available':True,'last_result':signal,'health':health}
        except (ValueError, KeyError, OSError, URLError):
            return {'specklet_enabled':specklet,'specklet_error':getattr(self.provider,'specklet_observer_error',None),'memory':memory,'scope':'agent', 'sleeping':asleep, 'model':configured_model, 'resident':None, 'preload_available':False,'controls_available':True,'last_result':signal,'health':health}

    def signal(self, agent, severity, code):
        with self.lock:
            role=self.provider.bindings[agent]
            if role not in ROLE_NAMES:return
            data={'severity':severity,'code':code,'at':time.time()}
            directory=self.home/'.progretech-mesh/agent-signals';directory.mkdir(parents=True,exist_ok=True,mode=0o700)
            path=directory/(role+'.json')
            temporary=path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
            import os
            try:
                fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as stream:
                    json.dump(data,stream);stream.flush();os.fsync(stream.fileno())
                temporary.replace(path)
            finally:
                if temporary.exists():temporary.unlink()

    def new_conversation(self, agent):
        with self.lock:
            if any(self.provider.bindings.get(v['agent_id'])==self.provider.bindings[agent] and not v['done'] for v in self.jobs.values()):raise ValueError('mesh_agent_busy')
            from control_center.management import save_preferences
            save_preferences(self.provider,agent,{'conversation_nonce':secrets.token_hex(12)})
        return {'started':True,'history_preserved':True}

    def sleeping(self, agent):
        role=ROLE_NAMES.get(self.provider.bindings[agent])
        rows=role_controls(self.home)
        if role not in rows:raise ValueError('runtime_controls_unavailable')
        return is_sleeping(rows[role])

    def chat_sleeping(self, agent):
        # Codex and Moxy are bound OpenClaw runtimes but are not managed by the
        # local-model workday scheduler. Missing scheduler controls do not
        # disable their owner chat or low-priority chatter.
        try:return self.sleeping(agent)
        except ValueError as exc:
            if self.provider.bindings.get(agent) in {'codex','moxy'} and str(exc)=='runtime_controls_unavailable':return False
            raise

    def control(self, agent, awake):
        role=ROLE_NAMES.get(self.provider.bindings[agent])
        if not role:raise ValueError('runtime_controls_unavailable')
        result=subprocess.run([str(self.home/'Rend/bin/factory-workday'),'resume' if awake else 'pause','--agent',role],capture_output=True,text=True,timeout=90)
        if result.returncode:raise ValueError('runtime_control_failed')
        rows=role_controls(self.home,refresh=True)
        if role not in rows or is_sleeping(rows[role])==awake:raise ValueError('runtime_control_not_confirmed')

    def idle(self):
        # Read only counts, never session transcripts or prompts.
        result = subprocess.run(['openclaw','gateway','call','status','--json'], capture_output=True, text=True, timeout=10)
        if result.returncode: raise ValueError('runtime_activity_unavailable')
        data = json.loads(result.stdout)
        return gateway_activity_idle(data)

    def mark(self, ident, phase, detail):
        with self.lock:
            job = self.jobs[ident]
            job.update(phase=phase, detail=detail, updated_at=time.time())
            if not job['milestones'] or job['milestones'][-1]['phase'] != phase:
                job['milestones'].append({'phase':phase,'detail':detail,'at':job['updated_at']})
                job['milestones'] = job['milestones'][-16:]
            if job.get('specklet'):
                from control_center.specklet import Board
                state='done' if phase=='complete' else 'blocked' if phase=='failed' else 'open' if phase=='queued' else 'doing'
                try:Board(self.provider,job['agent_id']).observe('request-'+ident,'Mesh request '+ident[:8],state)
                except (ValueError,OSError):job['specklet_error']='specklet_status_save_failed'

    def get(self, agent, ident):
        with self.lock:
            job=self.jobs.get(ident)
            if not job or job['agent_id'] != agent: raise ValueError('mesh_job_not_found')
            return copy.deepcopy(job)

    def start(self, agent, kind, worker, background=False, queue_timeout=600, capability=None, track=False):
        if kind=='chat' and self.chat_sleeping(agent):raise ValueError('mesh_agent_sleeping')
        with self.lock:
            now=time.time()
            self.jobs={k:v for k,v in self.jobs.items() if not v['done'] or now-v['updated_at']<1800}
            if any(self.provider.bindings.get(v['agent_id'])==self.provider.bindings[agent] and not v['done'] and (kind!='sleep' or v['kind']=='sleep') for v in self.jobs.values()):
                raise ValueError('mesh_agent_busy')
            if len(self.jobs)>=128: raise ValueError('mesh_jobs_full')
            ident=secrets.token_hex(16)
            self.jobs[ident]={'job_id':ident,'agent_id':agent,'kind':kind,'done':False,'phase':'queued',
                'detail':'Request accepted by your host','created_at':now,'updated_at':now,'milestones':[], 'specklet':track,'background':bool(background),'background_id':background if isinstance(background,str) else None}
            if capability:self.jobs[ident]['capability']=capability
        def run():
            try:
                self.mark(ident,'queued','Waiting for the shared model slot')
                deadline=time.monotonic()+queue_timeout
                while kind=='chat' and not self.inference.acquire(timeout=1):
                    if background:raise ValueError('mesh_chatter_deferred')
                    if time.monotonic()>deadline:raise ValueError('mesh_queue_timeout')
                try:
                    while kind == 'chat' and not self.idle():
                        if background:raise ValueError('mesh_chatter_deferred')
                        self.mark(ident,'queued','Waiting for other runtime work to finish')
                        if time.monotonic()>deadline:raise ValueError('mesh_queue_timeout')
                        time.sleep(2)
                    result=worker(ident)
                finally:
                    if kind=='chat':self.inference.release()
                if self.jobs[ident].get('cancelled'):raise ValueError('mesh_chatter_cancelled')
                self.mark(ident,'complete','Reply ready' if kind=='chat' else 'Recovery checks complete' if kind=='recovery' else 'Agent availability updated')
                if kind=='chat':
                    try:self.signal(agent,'success','reply_received')
                    except OSError:pass
                with self.lock:self.jobs[ident].update(done=True,result=result)
            except Exception as exc:
                # Do not return credential-bearing transport diagnostics.
                error=str(exc) if isinstance(exc,ValueError) and str(exc).startswith(('mesh_','local_','runtime_','model_')) else provider_error(exc) if isinstance(exc,(HTTPError,URLError,TimeoutError)) else 'mesh_runtime_request_failed'
                self.mark(ident,'failed',error)
                if kind=='chat' and error not in {'mesh_chatter_deferred','mesh_chatter_cancelled'}:
                    try:self.signal(agent,'error',error)
                    except OSError:pass
                with self.lock:self.jobs[ident].update(done=True,error=error)
        threading.Thread(target=run,daemon=True,name='mesh-'+kind).start()
        return self.get(agent,ident)

    def cancel_background(self, conversation):
        """Cancel only chatter for this conversation, preserving owner/native work."""
        with self.lock:
            jobs=[j for j in self.jobs.values() if not j['done'] and j.get('background_id')==conversation]
            for job in jobs:job['cancelled']=True
        def abort(job):
            role=self.provider.bindings.get(job['agent_id'])
            if not role:return
            session='agent:'+role+':mesh-chatter:'+conversation
            for _ in range(5):
                try:
                    result=subprocess.run(['openclaw','gateway','call','chat.abort','--params',json.dumps({'sessionKey':session}),'--json'],capture_output=True,text=True,timeout=10)
                    receipt=json.loads(result.stdout) if result.returncode==0 else {}
                    if receipt.get('aborted'):return
                except (OSError,ValueError,subprocess.SubprocessError):pass
                with self.lock:
                    if job['done']:return
                time.sleep(1)
        for job in jobs:threading.Thread(target=abort,args=(job,),daemon=True,name='mesh-chatter-cancel').start()

    def prepare(self, agent, ident, model=None):
        model=model or self.model(agent)
        resident={m['name'] for m in self.api('ps').get('models',[])}
        if model not in resident:
            tags=self.api('tags').get('models',[])
            installed=next((m for m in tags if m.get('name')==model),None)
            if not installed:raise ValueError('model_not_installed')
            memory={}
            for line in Path('/proc/meminfo').read_text().splitlines():
                if line.startswith('MemAvailable:'):memory['available']=int(line.split()[1])*1024
            # Reserve context/runtime/desktop headroom; never evict another model.
            if memory.get('available',0) < int(installed['size']*1.3)+8*1024**3:
                raise ValueError('model_memory_headroom_required')
        self.mark(ident,'warming','Waking up: loading the local model' if model not in resident else 'Refreshing the local model preload')
        self.api('generate',{'model':model,'stream':False,'keep_alive':'15m'},timeout=300)
        if model not in {m['name'] for m in self.api('ps').get('models',[])}:
            raise ValueError('model_preload_not_confirmed')
        self.mark(ident,'ready','Local model is loaded')
        return model

    def power(self, agent, awake):
        def worker(ident):
            if awake:
                self.mark(ident,'waking','Waking this agent in Mesh and Factory')
                self.control(agent,True)
                # Availability does not wait behind another role's inference.
                # Preload is optional and must never interrupt that work.
                if not self.inference.acquire(blocking=False):
                    return {**self.status(agent),'note':'Agent awake; model preload deferred while another Mesh request is active'}
                try:
                    if not self.idle():
                        return {**self.status(agent),'note':'Agent awake; model preload deferred while other runtime work is active'}
                    try:self.prepare(agent,ident)
                    except ValueError as exc:
                        if str(exc)=='local_preload_unavailable':return self.status(agent)
                        return {**self.status(agent),'note':'Agent awake; model preload unavailable','preload_error':str(exc)}
                    return self.status(agent)
                finally:self.inference.release()
            self.mark(ident,'sleeping','Putting this agent to sleep in Mesh and Factory')
            self.control(agent,False)
            try:model=self.model(agent)
            except ValueError:
                return {**self.status(agent),'note':'Agent asleep; model preload is unavailable on this provider'}
            shared=False
            for other in list(self.provider.bindings):
                if other==agent:continue
                try:
                    if self.sleeping(other):continue
                except ValueError:
                    shared=True;continue
                try:shared=shared or self.model(other)==model
                except ValueError:pass
            # Model release never interrupts another agent or a shared model user.
            if not shared and self.inference.acquire(blocking=False):
                try:
                    if self.idle():self.api('generate',{'model':model,'stream':False,'keep_alive':0},timeout=30)
                finally:self.inference.release()
            status=self.status(agent)
            status['note']='Model retained for other roles or channels' if status.get('resident') else 'Local model released'
            return status
        return self.start(agent,'wake' if awake else 'sleep',worker)

    def recover(self, agent):
        def worker(ident):
            before=self.status(agent);code=before.get('last_result',{}).get('code');steps=[]
            def add(name,state,detail):steps.append({'name':name,'state':state,'detail':detail});self.mark(ident,'checking',detail)
            if before.get('last_result',{}).get('severity')!='error':
                return {'outcome':'not_needed','steps':[],'note':'No recorded error needs recovery.'}
            add('availability','passed' if before.get('controls_available') else 'needs_attention','Shared availability controls are reachable' if before.get('controls_available') else 'Shared controls are unavailable; inspect the host service')
            try:
                cfg,role,_=self.config(agent)
                result=subprocess.run(['openclaw','gateway','call','status','--json'],capture_output=True,text=True,timeout=15)
                if result.returncode:raise ValueError('gateway_unavailable')
                data=json.loads(result.stdout);busy=not gateway_activity_idle(data)
                add('gateway','passed','Gateway is reachable; active work will be preserved')
            except (OSError,ValueError,subprocess.SubprocessError):
                return {'outcome':'needs_attention','steps':steps+[{'name':'gateway','state':'needs_attention','detail':'Gateway check failed. Inspect the local OpenClaw service; no restart was attempted.'}],'note':'Recovery needs host attention. No task was replayed.'}
            if busy or not self.inference.acquire(blocking=False):
                return {'outcome':'deferred','steps':steps,'note':'Other work is active. Model preparation and conversation changes were deferred; no task was interrupted.'}
            try:
                # Do not apply a repair to a superseded failure.
                current=self.status(agent).get('last_result',{})
                if current!=before.get('last_result',{}):return {'outcome':'deferred','steps':steps,'note':'The last result changed during checks. Refresh the status before trying recovery again.'}
                if code=='mesh_context_limit':
                    from control_center.management import save_preferences
                    save_preferences(self.provider,agent,{'conversation_nonce':secrets.token_hex(8)})
                    add('conversation','applied','A fresh Mesh conversation is ready; previous history is preserved')
                try:
                    model=self.model(agent)
                    installed={m['name'] for m in self.api('tags').get('models',[])}
                    if model not in installed:add('model','needs_attention','Configured model is not installed. Select an installed model in Control Center; no download was attempted.')
                    else:
                        add('model','passed','Configured local model is installed')
                        self.prepare(agent,ident);add('preload','passed','Local model preload confirmed')
                except (OSError,URLError,ValueError) as exc:
                    error=str(exc) if isinstance(exc,ValueError) else 'mesh_provider_unavailable'
                    add('preload','needs_attention',{'local_preload_unavailable':'This provider has no supported local preload check. Inspect its configuration.','model_memory_headroom_required':'Model preparation needs more free memory; other agents and models were left running.'}.get(error,'Local model preparation failed. Inspect provider availability and configuration.'))
                if code in {'mesh_provider_rejected','native_agent_failed'}:
                    add('provider_request','needs_attention','The previous failure has no confirmed request-level repair. Check provider format/context settings or send a new bounded request when ready.')
            finally:self.inference.release()
            outcome='needs_attention' if any(s['state']=='needs_attention' for s in steps) else 'checks_passed'
            return {'outcome':outcome,'steps':steps,'note':'Connectivity and model checks completed; the previous task was not replayed. Its failure remains in history. Current provider health and that earlier result are shown separately.'}
        return self.start(agent,'recovery',worker)

    def context(self, agent, text):
        """Owner instruction to an observed active session; no transcript reads."""
        if self.sleeping(agent):raise ValueError('mesh_agent_sleeping')
        runtime=self.provider.bindings[agent];role=ROLE_NAMES[runtime]
        file=self.home/'.local/state/progretech-workday/activity.json'
        try:
            data=json.loads(file.read_text());row=data['agents'][role]
            if time.time()-file.stat().st_mtime>90 or row['state']!='active':raise ValueError('mesh_no_active_work')
            session=row.get('session')
            if not session:
                task=next((t for t in data.get('tasks',[]) if t.get('id')==row.get('task_id') and t.get('role')==role and t.get('state')=='running'),{})
                session='agent:'+runtime+':workday:'+task.get('session','') if task.get('session') else None
        except (OSError,KeyError,StopIteration):raise ValueError('mesh_no_active_work')
        if not session or not session.startswith('agent:'+runtime+':') or len(session)>240:
            raise ValueError('mesh_active_session_unavailable')
        request={'sessionKey':session,'agentId':runtime,'message':text,'queueMode':'steer','suppressCommandInterpretation':True,'idempotencyKey':secrets.token_hex(16)}
        try:
            result=subprocess.run(['openclaw','gateway','call','chat.send','--params',json.dumps(request),'--json'],capture_output=True,text=True,timeout=30)
            if result.returncode:raise ValueError('mesh_context_delivery_unconfirmed')
            receipt=json.loads(result.stdout)
            if receipt.get('status') not in {'started','accepted','ok','queued'}:raise ValueError('mesh_context_delivery_unconfirmed')
        except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError):raise ValueError('mesh_context_delivery_unconfirmed')
        return {'scope':'agent','accepted':True,'delivery':receipt['status'],'note':'Runtime accepted this instruction for the observed work session. Processing or completion is not yet confirmed.'}

    def chat(self, agent, text, admission=None, background=None, image_paths=None, owner_text=None, response_timeout=300):
        if type(response_timeout) is not int or not 30 <= response_timeout <= 7200:
            raise ValueError('invalid_response_timeout')
        original_text=owner_text if owner_text is not None else text
        from control_center.artifacts import ROLES, safe, output_directory
        role=ROLES.get(self.provider.bindings[agent])
        from control_center.media_jobs import image_request
        media=not background and not image_paths and '\nAttached file ' not in text and '\nPublished artifact ' not in text and image_request(text)
        if role and not background and not media:
            output=safe(self.home,output_directory(self.home,self.provider.bindings[agent]))
            output.mkdir(parents=True,exist_ok=True,mode=0o700)
            text+='\nIf generating a deliverable for the owner, publish a non-secret copy under '+str(output)+'. Report the actual path; a reply alone is not a published file. Keep private memory and credentials out of shared artifacts.'
        def worker(ident):
            if admission:admission(ident)
            cfg,role,chosen=self.config(agent)
            if not self.settings(agent).get('enabled',True):raise ValueError('mesh_enrollment_removed')
            if self.chat_sleeping(agent):raise ValueError('mesh_agent_sleeping')
            if media:
                from control_center.media_jobs import generate
                return generate(self,agent,text,ident)
            if image_paths:
                from control_center.media_jobs import review
                return review(self,agent,text,ident,image_paths)
            elif chosen.startswith('ollama/'):self.prepare(agent,ident)
            if background:
                if self.jobs[ident].get('cancelled'):raise ValueError('mesh_chatter_cancelled')
                if admission:admission(ident)  # Recheck tab consent after a slow preload.
            port=cfg['gateway'].get('port',18789)
            if type(port) is not int or not 1<=port<=65535:raise ValueError('runtime_port_invalid')
            headers={'Content-Type':'application/json','Authorization':'Bearer '+cfg['gateway']['auth']['token'],
                'x-openclaw-agent-id':role,'x-openclaw-message-channel':'mesh',
                'x-openclaw-session-key':'agent:'+role+':mesh-chat:'+agent}
            if background:headers['x-openclaw-session-key']='agent:'+role+':mesh-chatter:'+background
            nonce=None if background else self.settings(agent).get('conversation_nonce')
            if nonce:headers['x-openclaw-session-key']+=':'+nonce
            if self.settings(agent).get('model','default')!='default':headers['x-openclaw-model']=chosen
            req=Request(f'http://127.0.0.1:{port}/v1/chat/completions',data=json.dumps({'model':'openclaw/'+role,'stream':False,
                'messages':[{'role':'user','content':text}],'user':'mesh-conversation-'+agent,**({'max_tokens':384} if background else {})}).encode(),headers=headers)
            self.mark(ident,'processing','Processing your request; waiting for reply text')
            # OpenClaw postprocessing can replace output after its token events.
            # Retrieve one final response; progress remains an asynchronous host job.
            with self.open(req,timeout=response_timeout) as response:
                raw=response.read(4194305)
            if len(raw)>4194304:raise ValueError('mesh_reply_too_large')
            payload=json.loads(raw)
            if payload.get('error'):raise ValueError('mesh_reply_failed')
            choices=payload.get('choices',[])
            if not choices:raise ValueError('mesh_reply_incomplete')
            answer=choices[0].get('message',{}).get('content')
            if isinstance(answer,list):answer=''.join(c.get('text','') for c in answer if isinstance(c,dict) and c.get('type')=='text')
            if not isinstance(answer,str) or not answer.strip():raise ValueError('mesh_reply_incomplete')
            if len(answer)>1048576:raise ValueError('mesh_reply_too_large')
            self.mark(ident,'writing','Reply generated; preparing delivery')
            if answer.lstrip().startswith(('⚠️ LLM request failed','LLM request failed:')):raise ValueError('mesh_provider_rejected')
            return {'reply':answer,'role':role,'model':chosen}
        def synchronized_worker(ident):
            if background:return worker(ident)
            from control_center.conversation_sync import publish
            runtime=self.provider.bindings[agent]
            session='agent:'+runtime+':mesh-chat:'+agent
            nonce=self.settings(agent).get('conversation_nonce')
            if nonce:session+=':'+nonce
            common={'agent':runtime,'origin':'mesh','session':session}
            publish(self.home,**common,event_key='mesh:'+ident+':user',speaker='user',text=original_text)
            try:
                result=worker(ident)
            except Exception:
                publish(self.home,**common,event_key='mesh:'+ident+':status',speaker='status',text='Request failed or completion is unconfirmed. Check Mesh task status before retrying.')
                raise
            result['sync_event_id']=publish(self.home,**common,event_key='mesh:'+ident+':assistant',speaker='assistant',text=result.get('reply',''))
            from control_center.artifacts import catalog, public
            result['attachments']=[public(row) for row in catalog(self.home) if row['path'] in result.get('reply','') and row['downloadable']]
            return result
        return self.start(agent,'chat',synchronized_worker,background=background,queue_timeout=1200 if media else 600,capability='image_generation' if media else None,track=not background)

    def snapshot(self, agent, kind):
        state=self.status(agent)
        with self.lock:
            jobs=[self.get(agent,k) for k,v in self.jobs.items() if v['agent_id']==agent][-8:]
        lines=[f'Agent availability: {"unknown" if state["sleeping"] is None else "asleep" if state["sleeping"] else "awake"}',
               f'Local model: {state["model"] or "unavailable"}',f'Model resident: {state["resident"]}']
        if kind=='task':
            try:
                data=json.loads((self.home/'.local/state/progretech-workday/activity.json').read_text())
                role=ROLE_NAMES.get(self.provider.bindings[agent])
                row=data.get('agents',{}).get(role,{})
                if row.get('task_id'):lines.append('Factory task: '+str(row['task_id']))
                lines += [f'Factory · {t["phase"]}: {t["state"]}' for t in data.get('tasks',[]) if t.get('role')==role and t.get('state') in {'running','queued','uncertain'}][-8:]
            except (OSError,ValueError,KeyError):pass
            lines += [f'{j["kind"]}: {j["detail"]}' for j in jobs if not j['done']]
            if not any(not j['done'] for j in jobs):lines.append('No active Mesh request for this role')
        else:
            lines += [f'{j["kind"]} · {m["detail"]}' for j in jobs for m in j['milestones']][-16:]
            lines.append('Scoped Mesh runtime snapshot; no arbitrary shell or other-role conversation data')
        return {'kind':kind,'agent_id':agent,'scope':'agent','lines':lines,'runtime':state}
