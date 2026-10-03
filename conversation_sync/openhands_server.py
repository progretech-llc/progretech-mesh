"""Version-pinned Agent Server display projection; never calls run/send_message."""
import asyncio
import json
import shlex
import uuid
from pathlib import Path
from store import Store

BRIDGE=str(Path.home()/'software-factory-setup/openhands-20260928/integration/factory_acp.py')


def role_for(agent):
    command=getattr(agent,'acp_command',[])
    if isinstance(command,str):command=shlex.split(command)
    if BRIDGE not in command or '--role' not in command:return None
    index=command.index('--role')+1
    if index>=len(command):return None
    role={'rend':'main','lyra':'researcher','mak':'coder'}.get(command[index],command[index])
    config=json.loads(Path('/mnt/pt-context/agents/shared/conversation-sync/config.json').read_text())
    return role if role in config.get('agents',[]) else None


def project_events(conversation):
    from openhands.sdk.event import MessageEvent
    from openhands.sdk.llm import Message, TextContent
    role=role_for(conversation.agent)
    if role is None:return {'mirrored':0,'bound':False}
    db=Store();count=0
    try:
        target='openhands:'+str(conversation.id)
        sid=getattr(conversation.agent,'_session_id',None) or getattr(conversation.state,'agent_state',{}).get('acp_session_id')
        with conversation.state:
            # Never disturb a running turn, paused confirmation or goal loop.
            if str(conversation.state.execution_status).lower().split('.')[-1] in {'running','waiting_for_confirmation'}:
                return {'mirrored':0,'busy':True}
            for row in db.pending(role,target,limit=100):
                own=row['origin']=='openhands' and sid and row['session'].endswith(':'+sid)
                ident=str(uuid.uuid5(uuid.NAMESPACE_URL,'progretech-sync:'+str(conversation.id)+':'+str(row['seq'])))
                if not own and ident not in conversation.state.events:
                    label='You' if row['speaker']=='user' else role if row['speaker']=='assistant' else 'Task status'
                    event=MessageEvent(id=ident,source='agent',sender='conversation-sync',llm_message=Message(role='assistant',content=[TextContent(text=f"[{row['origin']} · {label} · #{row['seq']}]\n{row['text']}")]))
                    conversation._on_event(event)
                    count+=1
                db.claim(row['seq'],target,-1);db.receipt(row['seq'],target,-1,'sent',ident)
        return {'mirrored':count,'bound':True}
    finally:db.db.close()


async def sync(event_service):
    conversation=event_service._conversation
    if conversation is None:return {'mirrored':0,'inactive':True}
    return await asyncio.to_thread(project_events,conversation)
