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
if (!hive.registry().godId) await hire("Director", "Orchestrator", "Delegate, coordinate dependencies and deliver the owner\u2019s mission.", true);
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
        initial.godId==='orchestrator' && initial.agents.orchestrator.name==='Director' &&
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
    hive.patchTask(args.id, { status: "todo", humanQA: [...(task.humanQA || []).map((qa) => qa.a ? qa : { ...qa, a: args.answer, answeredAt: (/* @__PURE__ */ new Date()).toISOString() })] });
    log({ kind: "approval", taskId: args.id, decision: "approved" });
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
  case "begin": {
    if (settings.paused) throw Error("office_paused");
    const tasks = hive.tasks().tasks;
    const task = tasks.find((t) => t.id === args.id);
    if (!task || task.status !== "todo" || task.dependsOn.some((id) => !tasks.some((t) => t.id === id && t.status === "done"))) throw Error("task_not_ready");
    hive.patchTask(args.id, { status: "doing" });
    log({ kind: "mission.start", taskId: args.id });
    result = { task, agents: roster().map((a) => ({
      id: a.id,
      name: a.name,
      role: a.role,
      goal: settings.goals[a.id],
      isDirector: hive.isGod(a.id),
      runtime_id: settings.runtimeBindings[a.id] || null,
      memory: hive.memory(a.id).slice(-4e3),
      ...inboxContext(a.id)
    })), maxIterations: settings.maxIterations };
    // Claim the pending context atomically with begin; delivered items stay reviewable.
    for(const a of result.agents) {
      const inbox=join(hive.agentDir(a.id),'inbox'),done=join(inbox,'.done');mkdirSync(done,{recursive:true,mode:448});
      for(const m of hive.inbox(a.id).filter(m=>a.mailboxIds.includes(m.id))) {
        if(/^[A-Za-z0-9_-]{1,160}$/.test(m.id))renameSync(join(inbox,m.id+'.json'),join(done,m.id+'.json'));
      }
      delete a.mailboxIds;
    }
    break;
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
    runtime_id: settings.runtimeBindings[a.id] || null,
    state: settings.paused ? "paused" : events.slice().reverse().find((e) => e.agentId === a.id && ["agent.start", "agent.complete", "agent.error"].includes(e.kind))?.kind === "agent.start" ? "working" : "idle",
    pendingMessages: hive.inboxBacklog(a.id),
    breaker: breaker.levelFor(a.id)
  })),
  orchestratorId: hive.registry().godId,
  archivedAgents: Object.values(hive.registry().agents).filter(a=>a.archived).map(a=>({id:a.id,name:a.name,runtime_id:settings.runtimeBindings[a.id] || null})),
  tasks: hive.tasks().tasks,
  messages: hive.voiceMessages({ limit: 30 }),
  events,
  paused: settings.paused,
  maxIterations: settings.maxIterations,
  components: { coordination: "Munder Difflin HiveManager", execution: "CrewAI hierarchical crews" }
};
process.stdout.write(JSON.stringify({ ok: true, result, snapshot }) + "\n");
