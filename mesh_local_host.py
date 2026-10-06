"""Explicit loopback-only transport to the installed authenticated host.

Local web Mesh uses the exact same UI/actions as cloud Mesh. No gateway login or
cloud credential is copied; the host token stays in this process.
"""
import json
import threading
import time
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


class LocalHost:
    def __init__(self, home=None):
        self.home=Path(home or Path.home())
        self.lock=threading.Lock()
        self.last=0
        self.ids=set()
        self.records=[]

    def call(self, path, body=None):
        credential=json.loads((self.home/'.progretech-mesh/local-access.json').read_text())
        token=credential.get('token')
        if not isinstance(token,str) or not token: raise ValueError('local_auth_missing')
        req=Request('http://127.0.0.1:8787'+path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type':'application/json','X-ProgreTech-Mesh-Local-Token':token})
        with build_opener(NoRedirect).open(req,timeout=325 if body and body.get('action')=='communication.chat' else 40) as response:
            data=json.loads(response.read(1048576))
        if not data.get('ok'): raise ValueError('local_host_action_failed')
        return data

    def refresh(self, registry, gateways):
        with self.lock:
            if time.monotonic()-self.last<3: return
            self.last=time.monotonic()
            try:
                rows=self.call('/api/mesh/control-center/agents?gateway_id=rend')['agents']
                if not isinstance(rows,list) or len(rows)>256: raise ValueError('invalid_roster')
            except Exception:
                gateways.pop('rend',None)
                for aid in self.ids:
                    if aid in registry: registry[aid]['transport']='not-connected'
                return
            import re
            rows=[r for r in rows if isinstance(r,dict) and isinstance(r.get('id'),str)
                and re.fullmatch(r'rend(?:--[A-Za-z0-9_-]+)?',r['id'])]
            current={r['id'] for r in rows}
            for aid in self.ids-current: registry.pop(aid,None)
            self.ids=current
            self.records=rows
            gateways['rend']=self
            for r in rows:
                aid=r['id'];runtime=r.get('mesh_runtime',{})
                observed=(r.get('activity') or {}).get('state',r.get('state','unknown'))
                state={'active':'working','working':'working','idle':'idle','paused':'paused','stopped':'paused','sleeping':'paused','blocked':'blocked'}.get(observed,'unknown')
                registry[aid]={'id':aid,'name':r.get('name',aid),'role':r.get('role',''),
                    'office_archived':r.get('office_archived') is True, 'office_agent_id':r.get('office_agent_id'), 'is_orchestrator':r.get('is_orchestrator') is True, 'office_worker':r.get('office_worker') is True, 'runtime_id':r.get('runtime_id'),
                    'owner_id':'local-edwin','trust_state':'verified','trust_valid':True,
                    'trust_reason':'authenticated-local-host-binding','local_host_binding':True,
                    'state':'paused' if runtime.get('sleeping') is True else state,'transport':'connected',
                    'task':'Local host connected','phase':'Authenticated local host',
                    'runtime':'OpenClaw','model':runtime.get('model','Unknown'),'mesh_runtime':runtime,
                    'identified_agents':[{'id':x['id'],'name':x.get('name',x['id']),'role':x.get('role','')} for x in rows if x['id']!='rend'] if aid=='rend' else [],
                    **({'control_center_gateway':'rend','runtime_id':aid.split('--',1)[1]} if aid!='rend' else {})}

    def send(self, agent_id, message=None):
        if message is None: raise RuntimeError("local_control_only")
        if agent_id!='rend' or message.get('type') not in {'control_center_request','factory_control_request'}:
            return False,'local_control_only'
        if message['type']=='factory_control_request':
            from mesh_factory_control import factory_relay
            payload=message.get('payload',{})
            try:
                data=self.call('/api/factory/control',{'action':payload.get('action'),'args':payload.get('args',{})})
            except Exception:
                data={'ok':False,'error':'local_host_action_failed'}
            factory_relay.resolve('rend',{'type':'factory_control_response','request_id':message['request_id'],'payload':data})
            return True,None
        from mesh_control_center import control_relay
        payload=message.get('payload',{})
        target=payload.get('agent_id')
        if target not in self.ids: return False,'agent_binding_required'
        try:
            data=self.call('/api/mesh/control-center',{'agent_id':target,'action':payload.get('action'),'args':payload.get('args',{})})
        except Exception:
            data={'ok':False,'error':'local_host_action_failed'}
        if data.get('ok') and payload.get('action')=='factory.office':self.last=0
        control_relay.resolve('rend',{'type':'control_center_response','request_id':message['request_id'],'payload':data})
        return True,None

    def close(self): pass
