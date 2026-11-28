"""Owner-authorized chat replication. Separate from memory and task authority."""
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

DEFAULT = Path('/mnt/pt-context/agents/shared/conversation-sync/events.sqlite3')
ALIASES = {'rend':'main', 'lyra':'researcher', 'mak':'coder', 'odexi':'codex'}

class Store:
    def __init__(self, path=DEFAULT):
        self.path = Path(path)
        if self.path == DEFAULT and not os.path.ismount('/mnt/pt-context'):
            raise RuntimeError('PT_CONTEXT is unavailable')
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(self.path, timeout=10)
        self.path.chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS events (
          seq INTEGER PRIMARY KEY, event_key TEXT UNIQUE NOT NULL,
          agent TEXT NOT NULL, project TEXT NOT NULL, origin TEXT NOT NULL,
          session TEXT NOT NULL, speaker TEXT NOT NULL, text TEXT NOT NULL,
          created REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS agent_seq ON events(agent,seq);
        CREATE TABLE IF NOT EXISTS task_revisions (office TEXT NOT NULL, task TEXT NOT NULL, revision TEXT NOT NULL, PRIMARY KEY(office,task));
        CREATE TABLE IF NOT EXISTS deliveries (
          seq INTEGER NOT NULL, target TEXT NOT NULL, part INTEGER NOT NULL,
          state TEXT NOT NULL, updated REAL NOT NULL, receipt TEXT,
          PRIMARY KEY(seq,target,part));
        ''')

    def append(self, event_key, agent, origin, session, speaker, text, project='ProgreTech'):
        agent = ALIASES.get(agent,agent)
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',agent): raise ValueError('invalid agent')
        if origin not in {'mesh','telegram','openclaw','openhands','factory-api'}: raise ValueError('invalid origin')
        if speaker not in {'user','assistant','status'}: raise ValueError('invalid speaker')
        if not isinstance(text,str) or len(text)>1048576 or '\x00' in text: raise ValueError('invalid text')
        if not text.strip(): return None
        text=re.sub(r'(?m)^MEDIA:\s*([^\n]+)',r'File: \1',text)
        text=re.sub(r'!\[([^\]]*)\]\(([^)]+)\)',r'Image: \1 — File: \2',text)
        # Binary attachments never enter this feed. Paths remain ordinary text.
        if 'data:image/' in text: raise ValueError('inline image bytes are not chat text')
        if not event_key or len(event_key)>512 or len(session)>512: raise ValueError('invalid identity')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO events(event_key,agent,project,origin,session,speaker,text,created) VALUES(?,?,?,?,?,?,?,?)',
                (event_key,agent,project,origin,session,speaker,text,time.time()))
        return self.db.execute('SELECT seq FROM events WHERE event_key=?',(event_key,)).fetchone()['seq']

    def history(self, agent, after=0, limit=100, latest=True):
        agent=ALIASES.get(agent,agent)
        limit=max(1,min(int(limit),200)); after=int(after)
        rows=self.db.execute('SELECT * FROM events WHERE agent=? AND seq>? ORDER BY seq '+('DESC' if latest else 'ASC')+' LIMIT ?', (agent,after,limit)).fetchall()
        return [dict(row) for row in (reversed(rows) if latest else rows)]

    def context(self, agent, session, project='ProgreTech'):
        rows=[r for r in self.history(agent,limit=30) if r['session']!=session and r['project'].casefold()==project.casefold()]
        text='\n\n'.join(f"[{r['origin']} / {r['speaker']} / event {r['seq']}]\n{r['text']}" for r in rows)
        return text[-12000:]

    def observe_tasks(self, office, snapshot, new_task=None):
        agents={r.get('id'):r.get('runtime_id') for r in snapshot.get('agents',[]) if r.get('runtime_id')}
        count=0
        for task in snapshot.get('tasks',[]):
            role=agents.get(task.get('assignee'))
            if not role:continue
            data={k:task.get(k) for k in ('id','title','description','status','result','humanQA','assignee')}
            revision=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
            previous=self.db.execute('SELECT revision FROM task_revisions WHERE office=? AND task=?',(office,task['id'])).fetchone()
            if previous and previous['revision']==revision:continue
            if previous or task['id']==new_task:
                text='Task '+task['id']+' · '+str(task.get('status','unknown'))+'\n'+str(task.get('title',''))
                if task.get('description'):text+='\n'+task['description']
                if task.get('result'):text+='\nResult: '+str(task['result'])
                for question in task.get('humanQA',[]):
                    if question.get('q'):text+='\nOwner input: '+question['q']
                    if question.get('a'):text+='\nOwner response: '+question['a']
                self.append('task:'+office+':'+task['id']+':'+revision,role,'mesh','task:'+task['id'],'status',text)
                count+=1
            with self.db:self.db.execute('INSERT OR REPLACE INTO task_revisions VALUES(?,?,?)',(office,task['id'],revision))
        return count

    def pending(self, agent, target, exclude_origin='', exclude_session='', limit=20):
        return [dict(r) for r in self.db.execute('SELECT e.* FROM events e WHERE agent=? AND origin!=? AND session!=? AND NOT EXISTS (SELECT 1 FROM deliveries d WHERE d.seq=e.seq AND d.target=? AND d.part=-1) ORDER BY seq LIMIT ?', (agent,exclude_origin,exclude_session,target,int(limit))).fetchall()]

    def claim(self, seq, target, part):
        # A crashed or timed-out send stays uncertain. Do not duplicate an external send.
        with self.db:
            cur=self.db.execute('INSERT OR IGNORE INTO deliveries VALUES(?,?,?,?,?,?)',(seq,target,part,'sending',time.time(),None))
        return cur.rowcount==1

    def receipt(self, seq, target, part, state, receipt=''):
        if state not in {'sent','uncertain','failed'}: raise ValueError('invalid delivery state')
        with self.db:
            self.db.execute('UPDATE deliveries SET state=?,updated=?,receipt=? WHERE seq=? AND target=? AND part=?',(state,time.time(),str(receipt)[:200],seq,target,part))
        return True


def main():
    data=json.load(sys.stdin)
    op=data.pop('op')
    if op not in {'append','history','context','pending','claim','receipt','observe_tasks'}: raise ValueError('invalid operation')
    store=Store()
    print(json.dumps(getattr(store,op)(**data),ensure_ascii=False))

if __name__=='__main__':
    main()
