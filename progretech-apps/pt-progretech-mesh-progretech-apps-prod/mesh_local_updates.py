"""Authenticated local-only update control; Git source and channel are host-owned."""
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import urlsplit
from flask import jsonify, request

STATE = Path.home()/'.local/state/progretech-mesh/installation'
LOCK = threading.Lock()


def read(path, fallback=None):
    try:return json.loads(Path(path).read_text())
    except (OSError,ValueError):return fallback


def write(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)


def git(repo, *args):
    result=subprocess.run(['git','-c','core.hooksPath=/dev/null','-C',str(repo),*args],capture_output=True,text=True,timeout=35)
    if result.returncode:raise ValueError('git_operation_failed')
    return result.stdout.strip()


class LocalUpdates:
    def __init__(self, state=STATE):self.state=Path(state)
    def config(self):
        cfg=read(self.state/'config.json')
        if not isinstance(cfg,dict):raise ValueError('updates_not_configured')
        if cfg.get('channel')!='releases/mesh-local' or cfg.get('remote')!='origin':raise ValueError('invalid_update_channel')
        return cfg
    def installation(self):
        data=read(self.state/'installed.json')
        if not isinstance(data,dict):raise ValueError('installation_not_configured')
        # Older manual installs recorded abbreviated object IDs. Resolve only
        # bounded hexadecimal commit IDs; a different HEAD still fails closed.
        commit=data.get('commit','')
        if not isinstance(commit,str) or not re.fullmatch('[a-f0-9]{7,40}',commit):raise ValueError('invalid_installed_revision')
        if len(commit)<40:
            data=dict(data,commit=git(data['source'],'rev-parse','--verify',commit+'^{commit}'))
        return data
    def status(self):
        installed=self.installation();offer=read(self.state/'offer.json',{})
        return {'ok':True,'local':True,'installed':installed['commit'][:12],
                'version':installed['version'],'channel':self.config()['channel'],
                'offer':offer,'job':read(self.state/'job.json',{'phase':'idle'})}
    def check(self):
        cfg=self.config();installed=self.installation();source=Path(installed['source'])
        if git(source,'status','--porcelain'):raise ValueError('local_changes_preserved_update_blocked')
        current=git(source,'rev-parse','HEAD')
        if current!=installed['commit']:raise ValueError('installation_source_changed')
        repo=Path(cfg['repository']);ref='refs/remotes/origin/'+cfg['channel']
        git(repo,'fetch','--no-tags','origin','refs/heads/'+cfg['channel']+':'+ref)
        target=git(repo,'rev-parse',ref)
        if not re.fullmatch('[a-f0-9]{40}',target):raise ValueError('invalid_update_revision')
        available=target!=current
        if available:
            result=subprocess.run(['git','-C',str(repo),'merge-base','--is-ancestor',current,target],capture_output=True,timeout=10)
            if result.returncode:raise ValueError('update_channel_diverged_no_downgrade')
        offer={'current':current,'target':target,'available':available,
               'commits':git(repo,'log','--max-count=12','--format=%h %s',current+'..'+target).splitlines() if available else []}
        write(self.state/'offer.json',offer);return self.status()
    def apply(self,target):
        if not isinstance(target,str) or not re.fullmatch('[a-f0-9]{40}',target):raise ValueError('invalid_update_revision')
        self.config();installed=self.installation();offer=read(self.state/'offer.json',{})
        if offer.get('target')!=target or not offer.get('available') or offer.get('current')!=installed['commit']:raise ValueError('check_for_updates_first')
        if read(self.state/'job.json',{}).get('phase') in {'queued','preparing','installing','waiting_for_idle','restarting'}:raise ValueError('update_already_running')
        if git(installed['source'],'status','--porcelain'):raise ValueError('local_changes_preserved_update_blocked')
        if git(installed['source'],'rev-parse','HEAD')!=installed['commit']:raise ValueError('installation_source_changed')
        helper=Path(__file__).resolve().parent/'install/update-local-mesh.py'
        write(self.state/'job.json',{'phase':'queued','target':target})
        result=subprocess.run(['systemd-run','--user','--collect','--unit=mesh-local-update-'+target[:12],
            sys.executable,str(helper),'--state',str(self.state),'--target',target],capture_output=True,text=True,timeout=15)
        if result.returncode:
            write(self.state/'job.json',{'phase':'failed','error':'update_worker_start_failed'})
            raise ValueError('update_worker_start_failed')
        return self.status()


def register_local_updates(app, require_session, updater=None):
    if os.environ.get('MESH_LOCAL_CONTROL_CENTER')!='1' or os.environ.get('MESH_UPDATE_ENABLED')!='1':return
    updater=updater or LocalUpdates()
    @app.context_processor
    def local_update_context():return {'local_updates_enabled':True}
    def guard():
        if request.remote_addr not in {'127.0.0.1','::1'}:raise ValueError('loopback_required')
        origin=request.headers.get('Origin','')
        if request.method=='POST' and (not origin or urlsplit(origin).netloc!=request.host or urlsplit(origin).scheme!=request.scheme):raise ValueError('same_origin_required')
        if request.headers.get('Sec-Fetch-Site')=='cross-site':raise ValueError('same_origin_required')
    @app.route('/api/local-updates',methods=['GET','POST'])
    @require_session
    def local_updates():
        try:
            guard()
            if request.method=='GET':return jsonify(updater.status())
            body=request.get_json(silent=True)
            if not isinstance(body,dict) or body.get('action') not in {'check','install'}:raise ValueError('invalid_update_request')
            with LOCK:
                if body['action']=='check':
                    if set(body)!={'action'}:raise ValueError('invalid_update_request')
                    result=updater.check()
                else:
                    if set(body)!={'action','target'}:raise ValueError('invalid_update_request')
                    result=updater.apply(body['target'])
            return jsonify(result)
        except (ValueError,OSError,subprocess.TimeoutExpired) as error:
            message=str(error) if isinstance(error,ValueError) else 'update_check_unavailable'
            return jsonify(ok=False,error=message),400
