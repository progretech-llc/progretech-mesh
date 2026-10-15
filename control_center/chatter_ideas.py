"""Host-owned floor encounters and evidence-bearing idea review, never browser votes."""
import copy
import hashlib
import json
import math
import time

from control_center.artifacts import ROLES

LIVE = {'queued', 'approaching', 'dispatching', 'first', 'second', 'third', 'reply_wait'}


def validate_encounter(args):
    if not isinstance(args, dict) or set(args) != {'tab_id', 'participants', 'positions', 'idea_id'}:
        raise ValueError('invalid_chatter_encounter')
    people, points = args['participants'], args['positions']
    if (not isinstance(args['tab_id'], str) or len(args['tab_id']) != 32 or
            not isinstance(args['idea_id'], str) or len(args['idea_id']) > 32 or
            not isinstance(people, list) or not 1 <= len(people) <= 3 or
            any(not isinstance(a, str) or len(a) > 200 for a in people) or
            len(set(people)) != len(people) or not isinstance(points, list) or len(points) != len(people)):
        raise ValueError('invalid_chatter_encounter')
    for p in points:
        if not isinstance(p, dict) or set(p) != {'x', 'y'} or any(type(v) not in {int, float} or not math.isfinite(v) for v in p.values()) or not 0 <= p['x'] <= 1000 or not 0 <= p['y'] <= 700:
            raise ValueError('invalid_chatter_position')
    if any(math.dist((points[0]['x'], points[0]['y']), (p['x'], p['y'])) > 160 for p in points[1:]):
        raise ValueError('chatter_not_nearby')


class IdeaChatter:
    def encounter(self, agent, args):
        state = self.data['chatter']
        if not state['enabled'] or not self.chatter_session or self.chatter_session['agent'] != agent or self.chatter_session['tab_id'] != args['tab_id']:
            raise ValueError('chatter_tab_expired')
        parent = agent.split('--')[0]
        people = args['participants']
        if any(a not in self.provider.bindings or a.split('--')[0] != parent or self.provider.bindings[a] not in ROLES for a in people):
            raise ValueError('invalid_chatter_pair')
        runtimes = [self.provider.bindings[a] for a in people]
        if len(set(runtimes)) != len(runtimes):raise ValueError('invalid_chatter_pair')
        live = [c for c in state['conversations'] if c['state'] in LIVE]
        if any(set(self.provider.bindings.get(a) for a in self.participants(c)) & set(runtimes) for c in live) or len(live) >= state['max_conversations']:
            raise ValueError('chatter_capacity')
        idea = None
        if args['idea_id']:
            idea = next((i for i in state.get('ideas', []) if i['id'] == args['idea_id'] and i['host'] == parent and not i.get('task_id')), None)
            if not idea or len(people) != 1 or len(idea['reviews']) >= 5:raise ValueError('chatter_idea_unavailable')
            if idea['reviews'] and idea['reviews'][-1]['runtime'] == runtimes[0]:raise ValueError('chatter_already_reviewed')
            if any(c.get('idea_id') == idea['id'] for c in live):raise ValueError('chatter_capacity')
            p = args['positions'][0]
            if math.dist((p['x'], p['y']), (idea['x'], idea['y'])) > 160:raise ValueError('chatter_not_nearby')
        elif len(people) < 2 or (len(people) == 3 and not state['experimental_group_chat']):
            raise ValueError('invalid_chatter_pair')
        key = '|'.join(sorted(runtimes)) + ':' + args['idea_id']
        if any(c.get('encounter_key') == key and time.time() - c['created'] < 45 for c in state['conversations']):
            raise ValueError('chatter_cooldown')
        row = self.conversation(people[0], people[1] if len(people)>1 else people[0], c=people[2] if len(people) == 3 else None)
        row.update(host=parent, encounter_key=key, x=args['positions'][0]['x'], y=args['positions'][0]['y'])
        if idea:row.update(idea_id=idea['id'], topic='Review idea: '+idea['title'])
        allowed, note = self.admission(row)
        state['admission'] = note
        if not allowed:raise ValueError('chatter_unavailable')
        state['conversations'].append(row)
        self.save()
        return copy.deepcopy(row)

    def finish_idea(self, row):
        state = self.data['chatter']
        if row.get('idea_id'):
            idea = next((i for i in state.get('ideas', []) if i['id'] == row['idea_id']), None)
            if not idea or idea.get('task_id') or not row['messages']:return
            runtime = self.provider.bindings.get(row['a'])
            text = row['messages'][-1]['text'].strip()
            if text and runtime and not any(r['conversation_id'] == row['id'] for r in idea['reviews']) and len(idea['reviews']) < 5:
                idea['reviews'].append({'runtime':runtime, 'agent':row['messages'][-1]['agent'], 'text':text, 'conversation_id':row['id'], 'at':time.time()})
            return
        # Only an explicit, structured proposal from a completed native discussion
        # creates a node. Ordinary replies, failures and visits are not proposals.
        if not row['messages'] or len([i for i in state.get('ideas', []) if not i.get('task_id')]) >= 30:return
        try:
            raw=row['messages'][-1]['text'].strip()
            if raw.startswith('```'):raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
            proposal=json.loads(raw).get('idea')
            if not isinstance(proposal,dict):return
            title, context=proposal.get('title'),proposal.get('context')
            if not isinstance(title,str) or not title.strip() or not isinstance(context,str) or not context.strip():return
        except (ValueError, TypeError, AttributeError):return
        ideas=state.setdefault('ideas',[])
        if any(i['id']==row['id'] for i in ideas):return
        ideas.append({'id':row['id'], 'host':row.get('host',row['a'].split('--')[0]), 'title':title.strip()[:160], 'context':context.strip()[:3000], 'x':row.get('x',500), 'y':row.get('y',350), 'created':time.time(), 'authors':[m['agent'] for m in row['messages']], 'discussion':copy.deepcopy(row['messages']), 'reviews':[]})

    def promote_ideas(self):
        from control_center.office import engine, namespace
        for idea in self.data['chatter'].get('ideas', []):
            if idea.get('task_id') or len(idea['reviews']) < 5:continue
            host=idea['host']
            if host not in self.provider.bindings:continue
            # Stable ID and engine-side idempotence survive a crash between ledgers.
            task_id='task-'+hashlib.sha256(('chatter:'+idea['id']).encode()).hexdigest()[:12]
            try:
                result=engine(self.home, namespace(self.provider.bindings[host],host), 'chatter.promote', {'id':task_id, 'idea':idea})
                if result.get('result',{}).get('id') != task_id:raise ValueError('chatter_promotion_unconfirmed')
                idea.update(task_id=task_id, promoted_at=time.time())
                idea.pop('promotion_error',None)
            except (ValueError, OSError):
                idea['promotion_error']='Board handoff pending; five reviews are preserved.'
        ideas=self.data['chatter'].get('ideas',[])
        archived=[i for i in ideas if i.get('task_id')]
        for old in archived[:-100]:ideas.remove(old)
