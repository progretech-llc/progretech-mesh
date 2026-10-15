/** Mesh coordination adapter. Keep the generated bundle in sync with this source. */
import {readFileSync, writeFileSync, mkdirSync, renameSync, unlinkSync} from 'node:fs';
import {join, isAbsolute} from 'node:path';
import {randomUUID} from 'node:crypto';
import {HiveManager, redactSecrets} from '../vendor/munder-difflin/src/main/hive';
import {CircuitBreaker} from '../vendor/munder-difflin/src/main/breaker';
import {ControlRegistry} from '../vendor/munder-difflin/src/main/control';
var body = JSON.parse(readFileSync(0, "utf8"));
var home = body.home;
if (typeof home !== "string" || !isAbsolute(home)) throw Error("office_path_invalid");
var hive = new HiveManager(() => home);
var controls = new ControlRegistry();
hive.ensureHive();
var settingsPath = join(home, "mesh-office.json");
var settings;
try {
  settings = JSON.parse(readFileSync(settingsPath, "utf8"));
} catch {
  settings = { paused: false, maxIterations: 8, events: [], goals: {} };
}
var save = () => hive.atomicWriteJson(settingsPath, settings);
settings.runtimeBindings ||= {};
var roster = () => Object.values(hive.registry().agents).filter((a) => !a.archived);
var agent = (id) => {
  if (!/^[A-Za-z0-9_-]{1,80}$/.test(id) || !hive.registry().agents[id] || hive.registry().agents[id].archived) throw Error("office_agent_not_found");
  return hive.registry().agents[id];
};
function inboxContext(id) {
  const pending=hive.inbox(id).sort((a,b)=>(b.priority||0)-(a.priority||0)||String(a.created_at).localeCompare(String(b.created_at)));
  const selected=[];let text='';
  for(const m of pending.slice(0,8)) {const next=(text?'\n':'')+m.body;if(text.length+next.length>4000)break;text+=next;selected.push(m.id);}
  return {messages:text,mailboxIds:selected};
}
var log = (event) => hive.appendLog({ ...event, ts: (/* @__PURE__ */ new Date()).toISOString() });
async function hire(name, role, goal, god = false) {
  if (roster().length >= 12) throw Error("office_capacity");
  if (roster().some((a) => a.role === role)) throw Error("office_role_already_exists");
  const id = god ? "orchestrator" : "worker-" + randomUUID().replaceAll("-", "").slice(0, 12);
  await hive.ensureAgent({ id, name, role, provider: "mesh", cwd: home, isGod: god }, { semanticMemory: false, knowledgeGraph: false, mcpDefaults: {} });
  settings.goals[id] = goal;
  save();
  return id;
}
if (!hive.registry().godId) await hire("Scrum Master", "Scrum Master", "Delegate, coordinate dependencies and deliver the owner\u2019s mission.", true);
function completeHandoff() {
  if (!settings.handoff) return;
  const {previous, next} = settings.handoff;
  const reg = hive.registry();
  if (!reg.agents[next] || reg.agents[next].archived) throw Error('office_agent_not_found');
  for (const task of hive.tasks().tasks) {
    if (task.assignee === previous && task.status !== 'done') hive.patchTask(task.id, {assignee:next});
  }
  // Move pending coordination mail; leave archived mail and specialist memory in place.
  for (const message of hive.inbox(previous)) {
    const source = join(hive.agentDir(previous), 'inbox', message.id + '.json');
    const destination = join(hive.agentDir(next), 'inbox', message.id + '.json');
    hive.atomicWriteJson(source, {...message, to:next});
    renameSync(source, destination);
  }
  for (const entry of Object.values(reg.agents)) entry.isGod = entry.id === next;
  reg.godId = next;
  hive.atomicWriteJson(join(hive.root(), 'registry.json'), reg);
  log({kind:'orchestrator.changed', from:previous, to:next});
  delete settings.handoff; save();
}
completeHandoff();
const stages = ['intake','ready','working','blocked','review','done'];
const statusFor = {intake:'todo',ready:'todo',working:'doing',blocked:'blocked',review:'todo',done:'done'};
const stageOf = t => stages.includes(t.stage) ? t.stage : ({todo:'ready',doing:'working',blocked:'blocked',done:'done'}[t.status] || 'intake');
const now = () => new Date().toISOString();
const getTask = id => { const t = hive.tasks().tasks.find(t=>t.id===id); if(!t)throw Error('task_not_found'); return t; };
const running = t => !!t.runId || t.status==='doing';
const editable = t => {if(running(t))throw Error('task_running');};
function dependencies(id, deps) {
  const tasks=hive.tasks().tasks;
  if(new Set(deps).size!==deps.length)throw Error('invalid_dependency');
  const visit=(key,seen=new Set())=>{if(key===id)throw Error('dependency_cycle');if(seen.has(key))return;seen.add(key);const t=tasks.find(t=>t.id===key);if(!t)throw Error('dependency_not_found');for(const d of t.dependsOn||[])visit(d,seen);};
  for(const dep of deps)visit(dep);
}
function comment(t,text,author,kind='comment',source='host') {
  const entry={id:randomUUID(),author,text:text.slice(0,6000),kind,source,createdAt:now()};
  hive.patchTask(t.id,{comments:[...(t.comments||[]),entry].slice(-200),updatedAt:now()});
  log({kind:'task.'+kind,taskId:t.id,agentId:author,source,commentId:entry.id,summary:text.slice(0,1000)});
}
// Additive migration: preserve legacy IDs, assignments and unknown ledger fields.
for(const t of hive.tasks().tasks)if(!t.stage)hive.patchTask(t.id,{stage:stageOf(t),order:t.order??0,comments:t.comments||[]});
const registry=hive.registry();
if(registry.agents.orchestrator?.name==='Director' && !settings.runtimeBindings.orchestrator){registry.agents.orchestrator.name='Scrum Master';hive.atomicWriteJson(join(hive.root(),'registry.json'),registry);}
var args = body.args || {};
var result = {};
switch (body.operation) {
  case "runtime.sync": {
    // Inventory and migration bindings come only from the authenticated local host.
    for (const [id, runtime] of Object.entries(args.bindings || {})) {
      if (!settings.runtimeBindings[id] && hive.registry().agents[id] && args.agents.some(a => a.runtime_id === runtime)) {
        settings.runtimeBindings[id] = runtime;
        const row=args.agents.find(a=>a.runtime_id===runtime), reg=hive.registry();
        reg.agents[id].role=row.role || row.name;
        reg.agents[id].name=row.name;
        hive.atomicWriteJson(join(hive.root(),'registry.json'),reg);
      }
    }
    // A brand-new office starts with a reserved placeholder, not a second agent.
    // Adopt the explicitly bound host runtime only while that placeholder is pristine.
    const initial=hive.registry(), candidate=args.agents.find(a=>a.runtime_id===args.host_runtime);
    if (candidate && !Object.keys(settings.runtimeBindings).length && Object.keys(initial.agents).length===1 &&
        initial.godId==='orchestrator' && ['Director','Scrum Master'].includes(initial.agents.orchestrator.name) &&
        !hive.tasks().tasks.length && !hive.inboxBacklog('orchestrator')) {
      settings.runtimeBindings.orchestrator=args.host_runtime;
      initial.agents.orchestrator.name=candidate.name;
      initial.agents.orchestrator.role=candidate.role || candidate.name;
      hive.atomicWriteJson(join(hive.root(),'registry.json'),initial);
    }
    for (const row of args.agents) {
      let id = Object.keys(settings.runtimeBindings).find(id => settings.runtimeBindings[id] === row.runtime_id);
      if (!id) {
        id = 'runtime-' + row.runtime_id;
        if (!/^[A-Za-z0-9_-]{1,80}$/.test(id)) throw Error('invalid_runtime_id');
        await hive.ensureAgent({id, name: row.name, role: row.role || row.name, provider: 'mesh', cwd: home, isGod: false}, {semanticMemory:false, knowledgeGraph:false, mcpDefaults:{}});
        settings.runtimeBindings[id] = row.runtime_id;
        settings.goals[id] = row.role || row.name;
      }
      // The host identity is authoritative for a bound runtime's display role.
      // Refresh existing records too, without respawning or changing ownership.
      const current = hive.registry().agents[id];
      if (current && current.name !== row.name) {
        const renamed = hive.registry();
        renamed.agents[id].name = row.name;
        hive.atomicWriteJson(join(hive.root(), "registry.json"), renamed);
      }
      const role = row.role || row.name;
      if (current && current.role !== role) {
        const previousRole = current.role;
        const patched = hive.patchAgentRole(id, role);
        if (!patched.ok) throw Error('office_role_refresh_failed');
        if (settings.goals[id] === previousRole) settings.goals[id] = role;
      }
      // Archival is durable; discovery cannot silently rehire a removed worker.
    }
    save();
    break;
  }
  case "orchestrator.set": {
    const next = agent(args.id), reg = hive.registry(), previous = reg.godId;
    if (hive.tasks().tasks.some(t=>running(t) && (t.assignee===previous || t.coordinator===previous))) throw Error('task_running');
    if (previous === next.id) { result = {id:next.id, previous}; break; }
    // Journal first. Replaying this transaction completes an interrupted handoff.
    settings.handoff = {previous, next:next.id}; save();
    completeHandoff();
    result = {id:next.id, previous};
    break;
  }
  case "restore": {
    const entry = hive.registry().agents[args.id];
    if (!entry) throw Error('office_agent_not_found');
    hive.setArchived(args.id, false); break;
  }
  case "snapshot":
    break;
  case "hire": {
    const id = await hire(args.name, args.role, args.goal);
    result = { id };
    break;
  }
  case "archive": {
    agent(args.id);
    if (hive.isGod(args.id)) throw Error("director_required");
    if (hive.tasks().tasks.some((t) => t.assignee === args.id && t.status !== "done")) throw Error("agent_has_open_tasks");
    hive.setArchived(args.id, true);
    break;
  }
  case "chatter.promote": {
    // Internal host operation: public office validation never admits this action.
    const idea=args.idea;
    if(!/^task-[a-f0-9]{12}$/.test(args.id) || !idea || idea.reviews?.length!==5 || new Set(idea.reviews.map(r=>r.conversation_id)).size!==5 || idea.reviews.some(r=>!r.text?.trim()))throw Error('invalid_chatter_proposal');
    const existing=hive.tasks().tasks.find(t=>t.id===args.id);
    if(existing){if(existing.chatterIdeaId!==idea.id)throw Error('invalid_chatter_proposal');result={id:existing.id};break;}
    if(hive.tasks().tasks.filter(t=>t.status!=='done').length>=100)throw Error('task_capacity');
    const coordinator=hive.registry().godId;
    hive.addTask({id:args.id,title:idea.title,description:idea.context,assignee:coordinator,coordinator,
      status:'blocked',stage:'blocked',queued:false,order:hive.tasks().tasks.length,dependsOn:[],priority:1,createdAt:now(),
      chatterIdeaId:idea.id,chatterReviews:idea.reviews,scrumReviewRequired:true,
      humanQA:[{q:'Five completed agent reviews are attached to this chatter idea. Approve Scrum Master assessment and scoped work? No execution has been authorized.',askedAt:now()}],
      comments:idea.reviews.map(r=>({id:randomUUID(),author:r.agent,text:r.text,kind:'idea-review',source:'native-chatter',createdAt:new Date(r.at*1000).toISOString()}))});
    hive.send({to:coordinator,act:'inform',subject:'Chatter idea awaiting owner approval: '+idea.title,body:'Review the five completed agent comments on '+args.id+'. Do not execute this proposal before owner approval.'},'chatter');
    log({kind:'chatter.promoted',taskId:args.id,ideaId:idea.id});result={id:args.id};break;
  }
  case "task.create": {
    if (hive.tasks().tasks.filter((t) => t.status !== "done").length >= 100) throw Error("task_capacity");
    if (args.assignee) agent(args.assignee);
    const tasks = hive.tasks().tasks;
    if (args.dependsOn.some((id2) => !tasks.some((t) => t.id === id2))) throw Error("dependency_not_found");
    const id = "task-" + randomUUID().replaceAll("-", "").slice(0, 12);
    hive.addTask({
      id,
      title: args.title,
      description: args.description,
      assignee: args.assignee || hive.registry().godId,
      coordinator: hive.registry().godId,
      stage: args.needsApproval ? "blocked" : "intake",
      order: tasks.length,
      comments: [],
      status: args.needsApproval ? "blocked" : "todo",
      dependsOn: args.dependsOn,
      priority: 1,
      createdAt: (/* @__PURE__ */ new Date()).toISOString(),
      ...args.needsApproval ? { humanQA: [{ q: "Approve this mission before execution?", askedAt: (/* @__PURE__ */ new Date()).toISOString() }] } : {}
    });
    hive.send({ to: args.assignee || "god", act: "request", subject: args.title, body: args.description || args.title }, "owner");
    result = { id };
    break;
  }
  case "task.update": {
    const t=getTask(args.id);editable(t);agent(args.assignee || hive.registry().godId);dependencies(t.id,args.dependsOn);
    hive.patchTask(t.id,{title:args.title,description:args.description,assignee:args.assignee||hive.registry().godId,dependsOn:args.dependsOn,priority:args.priority,updatedAt:now()});
    log({kind:'task.updated',taskId:t.id});result={id:t.id};break;
  }
  case "task.delete": {
    const t=getTask(args.id);editable(t);
    if(hive.tasks().tasks.some(other=>(other.dependsOn||[]).includes(t.id)))throw Error('task_has_dependents');
    hive.deleteTask(t.id);log({kind:'task.deleted',taskId:t.id});result={deleted:true};break;
  }
  case "task.move": {
    const t=getTask(args.id);editable(t);
    if(!stages.includes(args.stage) || args.stage==='working')throw Error('task_run_required');
    if(args.stage==='done' && (t.dependsOn||[]).some(id=>getTask(id).status!=='done'))throw Error('task_not_ready');
    if((t.humanQA||[]).some(q=>!q.a) && args.stage!=='blocked')throw Error('approval_not_pending');
    const tasks=hive.tasks().tasks, peers=tasks.filter(x=>x.id!==t.id && stageOf(x)===args.stage).sort((a,b)=>(a.order||0)-(b.order||0));
    peers.splice(Math.min(args.index,peers.length),0,{...t,stage:args.stage,status:statusFor[args.stage],queued:args.stage==='done'?false:t.queued,updatedAt:now()});
    const patches=new Map(peers.map((x,i)=>[x.id,{...x,order:i}]));
    hive.writeTasks(tasks.map(x=>patches.get(x.id)||x));log({kind:'task.moved',taskId:t.id,stage:args.stage});result={id:t.id};break;
  }
  case "task.comment": {
    comment(getTask(args.id),args.text,'owner');result={saved:true};break;
  }
  case "task.question": {
    const t=getTask(args.id);editable(t);
    hive.patchTask(t.id,{status:'blocked',stage:'blocked',humanQA:[...(t.humanQA||[]),{q:args.text,askedAt:now()}],updatedAt:now()});
    comment(getTask(t.id),args.text,'owner','question');result={saved:true};break;
  }
  case "task.priority": {
    const task=hive.tasks().tasks.find(t=>t.id===args.id);
    if(!task || task.status!=="todo")throw Error("task_not_ready");
    hive.patchTask(args.id,{priority:args.priority});
    log({kind:"task.priority",taskId:args.id,priority:args.priority});
    result={saved:true};break;
  }
  case "task.approve": {
    const task = hive.tasks().tasks.find((t) => t.id === args.id);
    if (!task || task.status !== "blocked") throw Error("approval_not_pending");
    editable(task);
    hive.patchTask(args.id, { status: "todo", stage:"ready", updatedAt:now(), humanQA: [...(task.humanQA || []).map((qa) => qa.a ? qa : { ...qa, a: args.answer, answeredAt: (/* @__PURE__ */ new Date()).toISOString() })] });
    comment(getTask(args.id),args.answer,"owner","answer");
    log({ kind: "approval", taskId: args.id, decision: "answered" });
    break;
  }
  case "mailbox.list": {
    agent(args.agent);
    result = {pending: hive.inbox(args.agent).sort((a,b)=>(b.priority||0)-(a.priority||0)||String(a.created_at).localeCompare(String(b.created_at))).map(m=>({...m,subject:redactSecrets(m.subject),body:redactSecrets(m.body)})), history:hive.voiceMessages({agentId:args.agent,limit:20}).filter(m=>m.archived)};
    break;
  }
  case "mailbox.edit":
  case "mailbox.remove":
  case "mailbox.priority": {
    agent(args.agent);
    const m=hive.inbox(args.agent).find(m=>m.id===args.id);
    if(!m || !/^[A-Za-z0-9_-]{1,160}$/.test(m.id))throw Error('mailbox_item_not_pending');
    const file=join(hive.agentDir(args.agent),'inbox',m.id+'.json');
    if(body.operation==='mailbox.remove')unlinkSync(file);
    else {if(body.operation==='mailbox.edit')m.body=args.text;else m.priority=args.priority;hive.atomicWriteJson(file,m);}
    log({kind:body.operation,agentId:args.agent,id:m.id});
    result={saved:true};
    break;
  }
  case "message": {
    agent(args.to);
    result = hive.send({ to: args.to, subject: "Owner message", body: args.text, act: "inform" }, "owner");
    break;
  }
  case "pause":
    controls.pause("office", args.paused);
    settings.paused = controls.snapshot("office").paused;
    log({ kind: "office.pause", paused: settings.paused });
    save();
    break;
  case "settings":
    settings.maxIterations = args.maxIterations;
    save();
    break;
  case "memory":
    agent(args.id);
    result = { text: hive.memory(args.id) };
    break;
  case "memory.save":
    agent(args.id);
    writeFileSync(join(hive.root(), "agents", args.id, "memory.md"), args.text, { mode: 384 });
    hive.commit("mesh: reviewed office memory");
    break;
  case "mission.queue": {
    if(settings.paused)throw Error('office_paused');
    const t=getTask(args.id);editable(t);if(t.status!=='todo')throw Error('task_not_ready');
    hive.patchTask(t.id,{queued:true,updatedAt:now()});log({kind:'mission.queued',taskId:t.id});break;
  }
  case "begin": {
    if (settings.paused) throw Error("office_paused");
    const tasks = hive.tasks().tasks;
    const task = tasks.find((t) => t.id === args.id);
    if (!task || task.status !== "todo" || (task.dependsOn || task.deps || []).some((id) => !tasks.some((t) => t.id === id && t.status === "done"))) throw Error("task_not_ready");
    const runId=randomUUID();
    hive.patchTask(args.id, { status: "doing", stage:"working", queued:false, runId, activeAgent:args.native ? hive.registry().godId : task.assignee, coordinator:hive.registry().godId, updatedAt:now() });
    log({ kind: "mission.start", taskId: args.id });
    result = { task:getTask(task.id), agents: roster().map((a) => ({
      id: a.id,
      name: a.name,
      role: a.role,
      goal: settings.goals[a.id],
      isDirector: hive.isGod(a.id),
      isScrumMaster: hive.isGod(a.id),
      runtime_id: settings.runtimeBindings[a.id] || null,
      memory: hive.memory(a.id).slice(-4e3),
      ...inboxContext(a.id)
    })), maxIterations: settings.maxIterations };
    // Claim the pending context atomically with begin; delivered items stay reviewable.
    for(const a of args.native ? [] : result.agents) {
      const inbox=join(hive.agentDir(a.id),'inbox'),done=join(inbox,'.done');mkdirSync(done,{recursive:true,mode:448});
      for(const m of hive.inbox(a.id).filter(m=>a.mailboxIds.includes(m.id))) {
        if(/^[A-Za-z0-9_-]{1,160}$/.test(m.id))renameSync(join(inbox,m.id+'.json'),join(done,m.id+'.json'));
      }
      delete a.mailboxIds;
    }
    break;
  }
  case "mission.context": {
    const t=getTask(args.id);if(t.runId!==args.runId || t.activeAgent!==args.actor)throw Error('mission_lease_invalid');
    const context=inboxContext(args.actor),inbox=join(hive.agentDir(args.actor),'inbox'),done=join(inbox,'.done');mkdirSync(done,{recursive:true,mode:448});
    for(const id of context.mailboxIds)if(/^[A-Za-z0-9_-]{1,160}$/.test(id))renameSync(join(inbox,id+'.json'),join(done,id+'.json'));
    result={task:t,memory:hive.memory(args.actor).slice(-4000),messages:context.messages};break;
  }
  case "mission.inspect": {
    const t=getTask(args.id);if(t.runId!==args.runId)throw Error('mission_lease_invalid');result={task:t};break;
  }
  case "mission.uncertain": {
    const t=getTask(args.id);if(t.runId!==args.runId)throw Error('mission_lease_invalid');
    hive.patchTask(t.id,{stage:'blocked',status:'blocked',result:args.text,updatedAt:now()});
    comment(getTask(t.id),args.text,'system','runtime');break;
  }
  case "mission.admit": {
    const t=getTask(args.id);if(t.runId!==args.runId || t.jobId)throw Error('mission_lease_invalid');
    hive.patchTask(t.id,{jobId:'admitting',activeAgent:args.agentId,updatedAt:now()});break;
  }
  case "mission.bind": {
    const t=getTask(args.id);if(t.runId!==args.runId)throw Error('mission_lease_invalid');
    hive.patchTask(t.id,{jobId:args.jobId,activeAgent:args.agentId,updatedAt:now()});
    log({kind:'agent.start',taskId:t.id,agentId:args.agentId});break;
  }
  case "mission.release": {
    const t=getTask(args.id);if(t.runId!==args.runId)throw Error('mission_lease_invalid');
    log({kind:args.error?'agent.error':'agent.complete',taskId:t.id,agentId:t.activeAgent});
    hive.patchTask(t.id,{jobId:null,updatedAt:now()});break;
  }
  case "mission.update": {
    const t=getTask(args.id);
    if(!args.runId || t.runId!==args.runId || t.activeAgent!==args.actor)throw Error('mission_lease_invalid');
    // Internal callers supply origin; public schemas and model decisions reject it.
    const source=args.source || 'native-reply';
    if(!['native-tool','native-reply'].includes(source))throw Error('invalid_mission_update');
    if(args.action==='comment')comment(t,args.text,args.actor,'comment',source);
    else if(args.action==='question') {
      hive.patchTask(t.id,{pendingDecision:{action:'question',text:args.text,actor:args.actor},updatedAt:now()});
      comment(t,args.text,args.actor,'question',source);
    } else if(args.action==='delegate') {
      if(args.actor!==t.coordinator)throw Error('scrum_master_required');agent(args.to);
      hive.patchTask(t.id,{pendingDecision:{action:'delegate',to:args.to,text:args.text},updatedAt:now()});
      comment(t,args.text,args.actor,'assignment',source);
    } else throw Error('invalid_mission_update');
    result={saved:true};break;
  }
  case "mission.transition": {
    const t=getTask(args.id);if(t.runId!==args.runId || t.jobId)throw Error('mission_lease_invalid');
    agent(args.to);
    hive.patchTask(t.id,{activeAgent:args.to,assignee:args.to,pendingDecision:null,updatedAt:now()});
    if(args.from!==args.to){hive.send({to:args.to,subject:t.title,body:args.text,act:'request'},args.from);log({kind:'delegation',taskId:t.id,agentId:args.from,to:args.to,summary:args.text.slice(0,1000)});}
    break;
  }
  case "mission.resolve": {
    const t=getTask(args.id);if(t.runId!==args.runId || t.jobId)throw Error('mission_lease_invalid');
    const stage=args.stage;
    if(!['review','blocked','done','ready'].includes(stage))throw Error('invalid_mission_resolution');
    hive.patchTask(t.id,{stage,status:statusFor[stage],runId:null,activeAgent:null,pendingDecision:null,result:args.text,updatedAt:now(),...(stage==='blocked'?{humanQA:[...(t.humanQA||[]),{q:args.text,askedAt:now()}]}:{})});
    comment(getTask(t.id),args.text,t.coordinator,stage==='done'?'completion':stage==='blocked'?'question':'review');
    log({kind:'mission.finish',taskId:t.id,ok:stage==='done'});break;
  }
  case "event": {
    if (args.agentId) agent(args.agentId);
    log({ kind: args.kind, agentId: args.agentId, to: args.to, taskId: args.taskId, summary: args.summary?.slice(0, 1e3) });
    if (args.to && args.agentId) {
      agent(args.to);
      hive.send({ to: args.to, subject: "Delegation", body: args.summary || "Task delegated", act: "request" }, args.agentId);
    }
    break;
  }
  case "finish": {
    const task = hive.tasks().tasks.find((t) => t.id === args.id);
    if (!task || task.status !== "doing") throw Error("task_not_running");
    hive.patchTask(args.id, {
      status: args.ok ? "done" : "blocked",
      stage: args.ok ? "done" : "blocked", runId:null,activeAgent:null,jobId:null,updatedAt:now(),
      result: args.result?.slice(0, 6e3),
      ...!args.ok ? { humanQA: [{ q: "Mission stopped. Review the failure and approve a retry.", askedAt: (/* @__PURE__ */ new Date()).toISOString() }] } : {}
    });
    hive.send({ to: "god", act: args.ok ? "done" : "refuse", subject: task.title, body: args.result || "Mission stopped" }, "system");
    log({ kind: "mission.finish", taskId: args.id, ok: args.ok });
    break;
  }
  default:
    throw Error("unknown_office_operation");
}
var events = hive.logTail(80);
var breaker = new CircuitBreaker(() => ({ enabled: true, hardStop: true, errorStormLimit: 5 }));
for (const event of events.filter((e) => Date.now() - (typeof e.ts === "number" ? e.ts : Date.parse(e.ts || "")) < 6e4)) {
  if (event.kind === "agent.error" && event.agentId) breaker.recordError(event.agentId);
}
var decisions = breaker.tick(roster().map((a) => ({ agentId: a.id, sample: null, progressing: true })));
if (decisions.some((d) => d.action === "stop")) {
  settings.paused = true;
  save();
}
var snapshot = {
  agents: roster().map((a) => ({
    id: a.id,
    name: a.name,
    role: a.role,
    goal: settings.goals[a.id],
    isDirector: hive.isGod(a.id),
      isScrumMaster: hive.isGod(a.id),
    runtime_id: settings.runtimeBindings[a.id] || null,
    state: settings.paused ? "paused" : events.slice().reverse().find((e) => e.agentId === a.id && ["agent.start", "agent.complete", "agent.error"].includes(e.kind))?.kind === "agent.start" ? "working" : "idle",
    pendingMessages: hive.inboxBacklog(a.id),
    breaker: breaker.levelFor(a.id)
  })),
  orchestratorId: hive.registry().godId,
  archivedAgents: Object.values(hive.registry().agents).filter(a=>a.archived).map(a=>({id:a.id,name:a.name,runtime_id:settings.runtimeBindings[a.id] || null})),
  stages,
  tasks: hive.tasks().tasks.map(({runId,pendingDecision,...t})=>({...t,running:!!runId || t.status==='doing'})),
  messages: hive.voiceMessages({ limit: 30 }),
  events,
  paused: settings.paused,
  maxIterations: settings.maxIterations,
  components: { coordination: "Munder Difflin HiveManager, CircuitBreaker, ControlRegistry", execution: "OpenClaw native runtime; optional CrewAI", taskAuthority:"host-local HiveManager ledger" }
};
process.stdout.write(JSON.stringify({ ok: true, result, snapshot }) + "\n");
