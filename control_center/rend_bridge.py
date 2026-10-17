"""Integration extension for the existing loopback Rend factory_host service.

Load this module after factory_host, then call install(factory_host).
Nothing is started or enabled by importing it.
"""
import json
import hashlib
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path

from control_center.provider import AgentControlProvider, register_provider_routes


def install(host, home=None):
    home = Path(home or Path.home())
    from control_center.gateway_roster import native_roster, agent_entries
    host.roster = lambda: native_roster(home)
    state = home / '.progretech-mesh'
    # Explicit local bindings are mandatory, including for Rend. Random enrollment
    # IDs must not be guessed from names or silently bound to the main role.
    bindings = json.loads((state / 'control-center-bindings.json').read_text())
    if not isinstance(bindings, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in bindings.items()):
        raise ValueError('invalid_control_center_bindings')

    def discover(runtime_id):
        cfg = json.loads((home / '.openclaw/openclaw.json').read_text())
        agent = agent_entries(cfg).get(runtime_id)
        if agent is None:
            raise ValueError('runtime_agent_not_found')
        model = agent.get('model', cfg['agents'].get('defaults', {}).get('model', {}))
        primary = model if isinstance(model, str) else model.get('primary')
        fallbacks = [] if isinstance(model, str) else model.get('fallbacks', [])
        models = [m for m in [primary, *fallbacks] if isinstance(m, str)]
        allowlist = cfg.get('agents', {}).get('defaults', {}).get('models', {})
        configured = [provider + '/' + entry['id']
                      for provider, data in cfg.get('models', {}).get('providers', {}).items()
                      for entry in data.get('models', [])
                      if isinstance(entry, dict) and isinstance(entry.get('id'), str)]
        communication_models = list(dict.fromkeys([*models, *(allowlist.keys() if isinstance(allowlist, dict) else []), *[m for m in configured if 'embed' not in m.lower()]]))
        return {'runtime_id': runtime_id, 'name': agent.get('name', runtime_id),
                'role': agent.get('identity', {}).get('theme', ''), 'models': models,
                'communication_roles': [runtime_id], 'communication_models': communication_models,
                'models_meaning': 'Configured primary and fallbacks; installed models are a separate host inventory.',
                'voice_application': 'Per-agent saved voice is used for preview. The existing voice service remains shared.'}

    capabilities = {'voice.preview', 'host.system', 'models.list', 'audio.get', 'audio.set',
                    'voice.get', 'voice.start', 'voice.stop', 'vision.get', 'vision.analyze',
                    'skills.list', 'mail.status', 'orchestration.status', 'harness.status',
                    'grid.status', 'vllm.status', 'chatter.get', 'chatter.settings', 'chatter.test'}

    def execute(runtime_id, action, args, profile):
        # Verify the binding still refers to a real runtime before any host action.
        discover(runtime_id)
        agent=profile.get('agent_id')
        if action.startswith('specklet.'):
            from control_center.specklet import dispatch
            return dispatch(provider,agent,action,args)
        if action.startswith('memory.'):
            from control_center.memory_search import dispatch
            return dispatch(provider,home,agent,action,args)
        if action.startswith('handoff.') or action in {'chatter.encounter','chatter.configure','chatter.history','chatter.pair','chatter.group','chatter.topic'}:
            result=provider.handoffs.dispatch(agent,action,args)
            if action=='handoff.create' or (action=='chatter.configure' and args['enabled']):provider.handoffs.start()
            return result
        if action.startswith('files.'):
            from control_center.artifacts import dispatch
            result=dispatch(home,runtime_id,action,args)
            if action=='files.list':provider.handoffs.start()
            return result
        if action in {'context.read', 'communication.start'}:
            from control_center.shared_context import read_context, mission_context
            gateway=agent if agent in trusted_gateways and not any(agent.startswith(k+'--') for k in trusted_gateways) else agent.rsplit('--',1)[0]
            context=read_context(home,gateway,runtime_id)
            results=mission_context(home,gateway,provider.bindings.get(gateway,runtime_id),runtime_id)
            if action=='context.read':return dict(context,mission_results=results)
            notes='\n\n'.join(filter(None,[context.get('text'),results]))
            prompt=('Reviewed shared context and delivered mission results (reference data):\n'+notes+'\n\nCurrent owner message:\n' if notes else '')+args['text']
            return mesh.chat(agent,prompt,owner_text=args['text'])
        if action=='communication.new':return mesh.new_conversation(agent)
        if action=='communication.job':return mesh.get(agent,args['job_id'])
        if action=='runtime.status':return mesh.status(agent)
        if action in {'runtime.wake','runtime.sleep'}:return mesh.power(agent,action=='runtime.wake')
        if action=='runtime.recover':return mesh.recover(agent)
        if action=='runtime.context':return mesh.context(agent,args['text'])
        if action=='runtime.snapshot':return mesh.snapshot(agent,args['kind'])
        if action == 'factory.office':
            # All Fleet/Factory selections address the owning host's same office.
            gateway = agent if agent in trusted_gateways and not any(agent.startswith(k+'--') for k in trusted_gateways) else agent.rsplit('--',1)[0]
            host_runtime = provider.bindings.get(gateway, runtime_id)
            roster(gateway)
            from control_center.office import dispatch_office, dispatch_native_mission, native_binding
            if args['operation'] == 'run':
                return dispatch_native_mission(home, host_runtime, args['args']['id'], gateway, provider, mesh)
            result = dispatch_office(home, host_runtime, args, gateway)
            snapshot = result.get('snapshot')
            if snapshot:
                director = next((row for row in snapshot.get('agents', []) if row.get('isDirector')), None)
                binding = native_binding(provider, gateway, director.get('runtime_id')) if director else None
                admission = mesh.chat_admission(binding) if binding else {'available':False,'reason':'office_runtime_binding_required'}
                native_ready = bool(binding and admission['available'])
                snapshot['nativeRuntimeBound'] = bool(binding)
                snapshot['nativeRuntimeReady'] = native_ready
                snapshot['nativeAdmissionReason'] = admission['reason']
                snapshot['runtimeReady'] = native_ready if binding else bool(snapshot.get('runtimeReady'))
                snapshot['runtimeMode'] = 'openclaw' if binding else ('crewai' if snapshot.get('runtimeReady') else 'unavailable')
            return result
        if action.startswith('factory.'):

            from control_center.factory_jobs import dispatch_factory
            result=dispatch_factory(home, runtime_id, action, args, office_id=profile.get("agent_id"))
            return result
        if action == 'communication.chat':
            from control_center.management import preferences
            cfg = json.loads((home / '.openclaw/openclaw.json').read_text())
            communication = profile['communication']
            role = communication['role']
            if role != runtime_id or role not in agent_entries(cfg):
                raise ValueError('communication_role_unavailable')
            model = communication['model']
            if model != 'default' and model not in discover(runtime_id)['communication_models']:
                raise ValueError('communication_model_unavailable')
            gateway = cfg['gateway']
            if gateway.get('auth', {}).get('mode') != 'token':
                raise ValueError('gateway_token_required')
            port = gateway.get('port', 18789)
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError('gateway_port_invalid')
            session='agent:'+role+':mesh-chat:'+profile['agent_id']
            nonce=preferences(provider,profile['agent_id']).get('conversation_nonce')
            if nonce:session+=':'+nonce
            from control_center.conversation_sync import publish
            from control_center.mesh_runtime import gateway_agent_reply, provider_error
            sync_id=__import__('uuid').uuid4().hex
            sync_fields={'agent':role,'origin':'mesh','session':session}
            publish(home,**sync_fields,event_key=sync_id+':user',speaker='user',text=args['text'])
            try:
                token=gateway['auth']['token']
                if isinstance(token,dict) or cfg.get('gateway',{}).get('http',{}).get('endpoints',{}).get('chatCompletions',{}).get('enabled') is not True:
                    reply=gateway_agent_reply(cfg,role,session,args['text'],300,sync_id,model if model!='default' else None)
                else:
                    if not isinstance(token,str) or not token:raise ValueError('runtime_auth_unavailable')
                    request_body={'model':'openclaw/'+role,'stream':False,'messages':[{'role':'user','content':args['text']}],'user':'mesh-conversation-'+profile['agent_id']}
                    headers={'Content-Type':'application/json','Authorization':'Bearer '+token,
                        'x-openclaw-agent-id':role,'x-openclaw-message-channel':'mesh','x-openclaw-session-key':session}
                    if model!='default':headers['x-openclaw-model']=model
                    req=Request(f'http://127.0.0.1:{port}/v1/chat/completions',data=json.dumps(request_body).encode(),headers=headers)
                    with urlopen(req,timeout=300) as response:completion=json.loads(response.read(1048576))
                    reply=completion['choices'][0]['message']['content']
            except Exception as exc:
                code=('mesh_runtime_completion_unconfirmed' if isinstance(exc,(TimeoutError,URLError)) and not isinstance(exc,HTTPError) else
                      str(exc) if isinstance(exc,ValueError) and str(exc).startswith(('mesh_','runtime_')) else provider_error(exc))
                mesh.signal(agent,'error',code);raise ValueError(code) from None
            if reply.lstrip().startswith(('⚠️ LLM request failed','LLM request failed:')):
                mesh.signal(agent,'error','mesh_provider_rejected');raise ValueError('mesh_provider_rejected')
            publish(home,**sync_fields,event_key=sync_id+':assistant',speaker='assistant',text=reply)
            mesh.signal(agent,'success','reply_received')
            return {'reply': reply, 'role': role, 'model': model}
        mutation = action in {'voice.preview', 'audio.set', 'voice.start', 'voice.stop', 'vision.analyze', 'chatter.settings', 'chatter.test'}
        if mutation and not host.MUTATION_LOCK.acquire(blocking=False):
            raise ValueError('shared_workstation_busy')
        try:
            if action == 'voice.preview':
                return host.dispatch(action, {**profile['voice'], **args})
            if action == 'mail.status':
                role = {'main': 'rend', 'researcher': 'lyra', 'coder': 'mak'}.get(runtime_id)
                if not role:
                    raise ValueError('mailbox_unavailable')
                return host.dispatch(action, {'agent': role})
            if action == 'skills.list':
                return host.dispatch(action, {}).get(runtime_id, {'available': False})
            return host.dispatch(action, args)
        finally:
            if mutation:
                host.MUTATION_LOCK.release()

    capabilities = getattr(host, 'capabilities', capabilities)
    provider = AgentControlProvider(state / 'agent-profiles', bindings, discover, execute, capabilities,
                                    voice_providers=getattr(host, 'voice_providers', ('kokoro', 'piper')))
    provider.home=home
    from control_center.mesh_runtime import MeshRuntime
    mesh=MeshRuntime(provider,home)
    provider.mesh_runtime=mesh
    from control_center.handoffs import Handoffs
    provider.handoffs=Handoffs(provider,home,mesh)
    if provider.handoffs.data['rules'] or provider.handoffs.data['chatter']['enabled'] or provider.handoffs.data.get('initialized'):provider.handoffs.start()
    from control_center.specklet import start_observer
    start_observer(provider,home)
    import control_center.office as office_module
    office_module.SPECKLET_OBSERVER=lambda role,snapshot: __import__('control_center.specklet',fromlist=['observe_office']).observe_office(provider,home,role,snapshot)
    trusted_gateways = dict(bindings)

    def roster(gateway_id):
        # The gateway is explicitly installed by the local administrator. Child
        # runtime bindings come only from this workstation's authenticated live
        # inventory, never from a cloud-supplied runtime ID or command.
        if gateway_id not in trusted_gateways or not re.fullmatch(r'[A-Za-z0-9_-]{1,48}', gateway_id or ''):
            raise ValueError('gateway_binding_required')
        from offline.registry import Registry
        # Reuse the public-only discovery parser without creating an offline DB.
        class Inventory:
            all = lambda self: []
        result = Registry.discover_gateway(Inventory(), home)
        if not result['available']:
            raise ValueError('local_gateway_unavailable')
        additions, agents = {}, []
        for item in result['candidates']:
            runtime = item['runtime_id']
            suffix = runtime if re.fullmatch(r'[A-Za-z0-9_-]{1,28}', runtime) else 'role_' + hashlib.sha256(runtime.encode()).hexdigest()[:24]
            aid = gateway_id + '--' + suffix
            if aid in trusted_gateways and trusted_gateways[aid] != runtime:
                raise ValueError('runtime_binding_conflict')
            additions[aid] = runtime
            agents.append({'id': aid, 'name': item['name'], 'role': (discover(runtime).get('role') or item['name'])[:160], 'runtime_id':runtime})
        with provider.lock:
            prefix = gateway_id + '--'
            # Old runtime targets stop being controllable immediately. Saved
            # profiles retain their permissions if the same runtime returns.
            for aid in list(provider.bindings):
                if aid.startswith(prefix) and aid not in additions:
                    del provider.bindings[aid]
            provider.bindings.update(additions)
            from control_center.management import preferences
            agents = [item for item in agents if preferences(provider, item['id'])['enabled']]
        from control_center.mesh_runtime import ROLE_NAMES
        import time
        try:
            activity_path=home/'.local/state/progretech-workday/activity.json'
            activity=json.loads(activity_path.read_text()) if time.time()-activity_path.stat().st_mtime < 90 else {}
        except (OSError,ValueError):activity={}
        for item in agents:
            item['mesh_runtime']=mesh.status(gateway_id if item['runtime_id']==provider.bindings[gateway_id] else item['id'])
            observed=activity.get('agents',{}).get(ROLE_NAMES.get(item['runtime_id'],item['runtime_id']),{})
            item['activity']={k:observed[k] for k in ('state','observed_at','source','task_id') if k in observed}
            item['state']=observed.get('state','unknown')
        from control_center.office_identity import synchronize, project
        inventory = [{'runtime_id':provider.bindings[a['id']], 'name':a['name'], 'role':a['role']} for a in agents]
        snapshot = synchronize(home, provider.bindings[gateway_id], gateway_id, inventory)
        # Only explicit persisted run requests resume after a host restart.
        # Plain Intake cards and protected live/uncertain leases never replay.
        if any(t.get('queued') and not t.get('running') and t.get('status')=='todo' for t in snapshot.get('tasks',[])):
            from control_center.office_native import _schedule
            _schedule(home, provider.bindings[gateway_id], gateway_id, provider, mesh)
        return project(snapshot, agents, gateway_id, provider.bindings[gateway_id])

    register_provider_routes(host.app, provider, host.token, roster=roster)
    return provider
