#!/usr/bin/env python3
"""Stage an immutable local release, switch atomically, and verify or roll back."""
import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mesh_local_updates import LocalUpdates,read,write,git


def host_idle():
    credential=read(Path.home()/'.progretech-mesh/local-access.json',{})
    if not credential.get('token'):return False
    headers={'Content-Type':'application/json','X-ProgreTech-Mesh-Local-Token':credential['token']}
    def call(path,body=None):
        with urlopen(Request('http://127.0.0.1:8787'+path,headers=headers,data=None if body is None else json.dumps(body).encode()),timeout=20) as r:return json.load(r)
    try:
        agents=call('/api/mesh/control-center/agents?gateway_id=rend')['agents']
        for agent in agents:
            snapshot=call('/api/mesh/control-center',{'agent_id':agent['id'],'action':'runtime.snapshot','args':{'kind':'task'}})['result']
            if 'No active Mesh request for this role' not in snapshot['lines']:return False
        return True
    except (OSError,KeyError,ValueError):return False


def health(commit):
    for _ in range(40):
        try:
            with urlopen('http://127.0.0.1:8080/healthz',timeout=3) as r:result=json.load(r)
            if result.get('ok') and result.get('build')==commit[:7]:return True
        except (OSError,ValueError):pass
        time.sleep(.5)
    return False


def install(state,target):
    updater=LocalUpdates(state);cfg=updater.config();previous=updater.installation()
    offer=read(state/'offer.json',{})
    if offer.get('target')!=target or offer.get('current')!=previous['commit']:raise ValueError('update_offer_changed')
    if git(previous['source'],'status','--porcelain'):raise ValueError('local_changes_preserved_update_blocked')
    if git(previous['source'],'rev-parse','HEAD')!=previous['commit']:raise ValueError('installation_source_changed')
    repo=Path(cfg['repository']);ref='refs/remotes/origin/'+cfg['channel']
    if git(repo,'rev-parse',ref)!=target:raise ValueError('update_offer_changed')
    update_dir=Path(cfg['release_root'])/target
    if update_dir.exists():
        if git(update_dir,'rev-parse','HEAD')!=target or git(update_dir,'status','--porcelain'):raise ValueError('release_directory_changed')
    else:
        update_dir.parent.mkdir(parents=True,exist_ok=True)
        git(repo,'worktree','add','--detach',str(update_dir),target)
    metadata=read(update_dir/'mesh-release.json',{})
    version=metadata.get('version','')
    if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}',version):raise ValueError('invalid_release_metadata')
    write(state/'job.json',{'phase':'preparing','target':target})
    # Each release owns its interpreter; a failed dependency install cannot damage
    # the running version. No remote shell scripts or Git hooks are executed.
    venv=state/'venvs'/target
    subprocess.run([sys.executable,'-m','venv',str(venv)],check=True,stdout=subprocess.DEVNULL)
    interpreter=venv/'bin/python'
    write(state/'job.json',{'phase':'installing','target':target})
    subprocess.run([str(interpreter),'-m','pip','install','-r',str(update_dir/'requirements.txt')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=600)
    subprocess.run([str(interpreter),'-m','compileall','-q',str(update_dir)],check=True,stdout=subprocess.DEVNULL,timeout=60)
    write(state/'job.json',{'phase':'waiting_for_idle','target':target})
    deadline=time.monotonic()+180
    while not host_idle():
        if time.monotonic()>=deadline:raise ValueError('active_mesh_work_update_deferred')
        time.sleep(2)
    if git(previous['source'],'status','--porcelain'):raise ValueError('local_changes_preserved_update_blocked')
    if git(previous['source'],'rev-parse','HEAD')!=previous['commit']:raise ValueError('installation_source_changed')
    next_install={'source':str(update_dir),'python':str(interpreter),'commit':target,'version':version}
    write(state/'previous.json',previous)
    write(state/'installed.json',next_install)
    write(state/'job.json',{'phase':'restarting','target':target})
    try:
        subprocess.run(['systemctl','--user','restart','progretech-mesh-local.service','rend-control-center.service'],check=True,timeout=30)
        if not health(target):raise ValueError('updated_service_health_failed')
    except (ValueError,subprocess.SubprocessError):
        write(state/'installed.json',previous)
        subprocess.run(['systemctl','--user','restart','progretech-mesh-local.service','rend-control-center.service'],check=True,timeout=30)
        if not health(previous['commit']):raise ValueError('previous_release_health_unconfirmed')
        raise ValueError('update_failed_previous_release_restored')
    write(state/'offer.json',{'current':target,'target':target,'available':False,'commits':[]})
    write(state/'job.json',{'phase':'complete','target':target,'version':version,'previous':previous['commit']})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--state',required=True);parser.add_argument('--target',required=True);args=parser.parse_args();state=Path(args.state)
    if not re.fullmatch('[a-f0-9]{40}',args.target):return 1
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (state/'update.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return 1
        try:install(state,args.target)
        except (ValueError,OSError,subprocess.SubprocessError) as error:
            write(state/'job.json',{'phase':'failed','target':args.target,'error':str(error) if isinstance(error,ValueError) else 'update_install_failed'})
            return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
