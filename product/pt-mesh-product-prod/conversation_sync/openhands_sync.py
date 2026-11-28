"""ACP display-only mirror; incoming text never becomes a second prompt."""
import asyncio
import importlib.util
import uuid
from pathlib import Path


def connection():
    path=Path.home()/'.openclaw/extensions/progretech-conversation-sync/store.py'
    if not path.exists():return None
    spec=importlib.util.spec_from_file_location('chat_sync_store',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod.Store()


class ConversationSync:
    def sync_publish(self,sid,project,speaker,text,event_id):
        db=connection()
        if db is None:return
        try:
            role={'rend':'main','lyra':'researcher','mak':'coder'}.get(self.role,self.role)
            return db.append(event_key='openhands:'+event_id+':'+speaker,agent=role,origin='openhands',
                session=f'agent:{role}:factory-api:{project}:{sid}',project=project,speaker=speaker,text=text)
        finally:db.db.close()
