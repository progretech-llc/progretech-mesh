"""Install the reviewed local adapter; preserve current runtime settings and backups."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
HOME=Path.home()


def write(path,text):
    temp=path.with_name(path.name+'.sync-tmp');temp.write_text(text);temp.chmod(0o600);temp.replace(path)


def backup(path,folder):
    dest=folder/(path.name+'.'+hashlib.sha256(str(path).encode()).hexdigest()[:8])
    if not dest.exists():shutil.copy2(path,dest);dest.chmod(0o600)


def install(evidence):
    if not os.path.ismount('/mnt/pt-context'):raise RuntimeError('PT_CONTEXT unavailable')
    evidence=Path(evidence).resolve()
    if not evidence.is_relative_to('/mnt/pt-context/job-artifacts'):raise ValueError('Evidence must be on PT_CONTEXT')
    private=evidence/'private-backup';private.mkdir(parents=True,exist_ok=True,mode=0o700);private.chmod(0o700)
    extension=HOME/'.openclaw/extensions/progretech-conversation-sync';extension.mkdir(parents=True,exist_ok=True)
    for name in ['index.js','hooks.js','client.js','store.py','openhands_sync.py','openhands_server.py','openclaw.plugin.json','package.json']:
        dest=extension/name
        if dest.exists():backup(dest,private)
        shutil.copy2(ROOT/name,dest)
    modules=extension/'node_modules';modules.mkdir(exist_ok=True)
    if not (modules/'openclaw').exists():(modules/'openclaw').symlink_to(HOME/'.openclaw/tools/node-v24.21.0/lib/node_modules/openclaw')
    binding_path=Path('/mnt/pt-context/agents/shared/conversation-sync/config.json');binding_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    runtime_path=HOME/'.openclaw/openclaw.json';runtime_before=runtime_path.read_bytes();runtime=json.loads(runtime_before)
    telegram=runtime.get('channels',{}).get('telegram',{});accounts=telegram.get('accounts',{})
    default_owners=accounts.get('default',{}).get('allowFrom',[])
    bindings=[]
    for row in runtime.get('bindings',[]):
        match=row.get('match',{});account=match.get('accountId')
        if match.get('channel')!='telegram' or account not in accounts:continue
        owners=accounts[account].get('allowFrom',default_owners)
        if len(owners)!=1 or not str(owners[0]).isdigit():raise ValueError('An unambiguous existing owner binding is required')
        bindings.append({'agent':row['agentId'],'account':account,'owner':str(owners[0])})
    if binding_path.exists():backup(binding_path,private)
    write(binding_path,json.dumps({'agents':list(runtime['agents']['entries']),'telegram':bindings,'openhands':True},indent=2)+'\n')
    # Apply the reviewed bridge diff to the current file, never replacing another task's edits.
    bridge=HOME/'software-factory-setup/openhands-20260928/integration/factory_acp.py'
    before=(evidence/'openhands-before.py').read_bytes();after=(evidence/'openhands-after.py').read_bytes()
    if bridge.read_bytes()!=after:
        if bridge.read_bytes()!=before:raise RuntimeError('OpenHands bridge changed; rebase the reviewed patch')
        backup(bridge,private);write(bridge,after.decode())
    sdk=HOME/'.local/share/uv/tools/openhands-agent-server/lib/python3.12/site-packages'
    if not (sdk/'openhands_sdk-1.49.6.dist-info').exists():raise RuntimeError('Revalidate OpenHands SDK version')
    router=sdk/'openhands/agent_server/event_router.py'
    before=(evidence/'event-router-before.py').read_bytes();after=(evidence/'event-router-after.py').read_bytes()
    if router.read_bytes()!=after:
        if router.read_bytes()!=before:raise RuntimeError('OpenHands event router changed; rebase the reviewed patch')
        backup(router,private);write(router,after.decode())
    backup(runtime_path,private)
    runtime.setdefault('plugins',{}).setdefault('entries',{})['progretech-conversation-sync']={'enabled':True}
    if runtime_path.read_bytes()!=runtime_before:raise RuntimeError('Runtime settings changed during installation; rebase configuration')
    write(runtime_path,json.dumps(runtime,indent=2)+'\n')
    print(json.dumps({'installed':True,'agents':len(runtime['agents']['entries']),'telegram_bindings':len(bindings),'backup':str(private)}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',required=True);install(parser.parse_args().evidence)
