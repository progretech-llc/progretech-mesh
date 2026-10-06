"""Relationships from recorded work, never inferred from node proximity."""
import json
import time
from pathlib import Path
from itertools import combinations


def interactions(snapshot, home):
    output=[]
    tasks={t['id']:t for t in snapshot.get('tasks',[])}
    for e in snapshot.get('events',[]):
        if e.get('kind') != 'delegation' or tasks.get(e.get('taskId'),{}).get('status') != 'doing': continue
        if not e.get('to'): continue
        output.append({'id':'delegation-'+e['taskId']+'-'+e['agentId']+'-'+e['to'], 'kind':'instruction', 'from':e['agentId'], 'to':e['to'], 'title':e.get('summary') or 'Active delegation', 'task_id':e['taskId'], 'parts':{}, 'source':'active mission'})
    active={}
    for e in snapshot.get('events',[]):
        if e.get('kind')=='agent.start':active[e.get('agentId')]=e.get('taskId')
        elif e.get('kind') in {'agent.complete','agent.error'}:active.pop(e.get('agentId'),None)
    known={a['id']:a for a in snapshot.get('agents',[])}
    tasks={t['id']:t for t in snapshot.get('tasks',[])}
    groups={}
    for aid,task in active.items():
        if task and tasks.get(task,{}).get('status')=='doing':groups.setdefault(task,[]).append((aid,known.get(aid,{}).get('goal')))
    for a in snapshot.get('factoryAgents',[]):
        if a.get('state') in {'active','working'} and a.get('task_id'):
            groups.setdefault(a['task_id'],[]).append(('factory-'+a['id'],a.get('part')))
    for task,people in groups.items():
        for (a,parta),(b,partb) in combinations(people,2):
            output.append({'id':'task-'+task+'-'+a+'-'+b,'kind':'collaboration','from':a,'to':b,'task_id':task,'title':tasks.get(task,{}).get('title') or task,'parts':{a:parta,b:partb},'source':'active task assignment'})
    try:
        rows=json.loads((Path(home)/'.progretech-mesh/agent-interactions.json').read_text())
        for row in rows[-40:]:
            # Keep a recent handoff visible long enough for the owner to inspect it;
            # historical rows remain persisted but do not become permanent links.
            if 0<=time.time()-row['at']<900:
                # Older Mesh plugin releases called Codex's stable runtime
                # identity "odexi". Normalize it only at render time so the
                # historical event remains intact while links target the
                # current factory-codex floor node.
                aliases={'odexi':'codex'}
                output.append({**row,'from':'factory-'+aliases.get(row['from'],row['from']),'to':'factory-'+aliases.get(row['to'],row['to'])})
    except (OSError,ValueError,KeyError,TypeError):pass
    try:
        state=json.loads((Path(home)/'.progretech-mesh/artifact-handoffs.json').read_text())
        for r in state.get('rules',[])[-20:]:
            # Terminal receipts remain in handoff history, not on the live floor.
            if r['state']!='running':continue
            source='factory-'+r['source'];target='factory-'+r['target_role']
            output.append({'id':'artifact-'+r['id'],'kind':'instruction','from':source,'to':target,'title':'Artifact handoff: '+r.get('artifact',{}).get('name','unreported'),'task_id':None,'parts':{source:'Published '+r.get('artifact',{}).get('name','artifact'),target:r['text']},'source':'Owner-authorized conditional instruction · '+r['state']})
        for c in state.get('chatter',{}).get('conversations',[])[-10:]:
            if c['state'] not in {'queued','approaching','first','reply_wait','second','third'}:continue
            roles=[c['a_role'],c['b_role']]+([c['c_role']] if c.get('c_role') else [])
            for left,right in combinations(roles,2):
                a='factory-'+left;b='factory-'+right
                output.append({'id':'chatter-'+c['id']+'-'+left+'-'+right,'chatter_id':c['id'],'topic_editable':True,'kind':'conversation','from':a,'to':b,'title':c['topic'],'task_id':None,'parts':{a:'\n'.join(m['text'] for m in c['messages'] if m['agent']==left) or 'Reply pending',b:'\n'.join(m['text'] for m in c['messages'] if m['agent']==right) or 'Reply pending'},'source':('Experimental group chatter · ' if c.get('c_role') else 'Office chatter · ')+c['state']})
    except (OSError,ValueError,KeyError,TypeError):pass
    return output[-80:]
