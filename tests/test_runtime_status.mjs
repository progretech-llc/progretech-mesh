import {test} from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';import vm from 'node:vm';
const context={window:{},Date,setTimeout};vm.runInNewContext(readFileSync(new URL('../static/js/runtime-client.js',import.meta.url),'utf8'),context);const api=context.window.MeshRuntime;
test('fleet and Factory use identical state and last-event color',()=>{
 const fleet=[{id:'rend--coder',runtime_id:'coder',state:'idle',transport:'connected',mesh_runtime:{sleeping:false},last_event:{type:'heartbeat',payload:{}}}];
 const floor=api.factoryAgent({id:'mak',runtime_id:'coder',state:'unknown'},fleet,'rend');
 assert.equal(api.indicator(floor).state,api.indicator(fleet[0]).state);assert.equal(api.indicator(floor).state,'idle');
 assert.equal(api.terminalDirection(fleet[0].last_event).label,'SYS');
});
test('offline and asleep do not show misleading successful activity',()=>{
 assert.equal(api.indicator({state:'working',transport:'not-connected',last_event:{type:'message_response'}}).label,'Offline');
 assert.equal(api.indicator({state:'idle',mesh_runtime:{sleeping:true}}).state,'sleeping');
 assert.equal(api.indicator({state:'unknown'}).label,'Activity unknown');
});
test('terminal and lamp use the same direction classification',()=>{
 for(const [event,label,state] of [[{type:'heartbeat'},'SYS','idle'],[{type:'message_response'},'IN','idle'],[{type:'user_message'},'OUT','busy'],[{type:'direct_error'},'ERR','error'],[{type:'file_offer'},'FILE','idle']]){
  assert.equal(api.terminalDirection(event).label,label);assert.equal(api.indicator({state:'idle',transport:'connected',last_event:event}).state,state);
 }
});

test('newly enrolled roles appear even before an older workday snapshot observes them',()=>{
 const fleet=[{id:'rend--codex',runtime_id:'codex',control_center_gateway:'rend',name:'Odexi',state:'unknown',transport:'connected'}];
 const rows=api.factoryRoster([],fleet,'rend');assert.equal(rows.length,1);assert.equal(rows[0].name,'Odexi');assert.equal(rows[0].state,'unknown');
 assert.equal(api.factoryRoster(rows,fleet,'rend').length,1);
});

test('signed restored records without runtime metadata remain visible on the floor',()=>{
 const fleet=[{id:'rend--codex',control_center_gateway:'rend',name:'Odexi',state:'unknown',transport:'connected'}];
 const rows=api.factoryRoster([],fleet,'rend');assert.equal(rows.length,1);assert.equal(rows[0].runtime_id,'codex');assert.equal(rows[0].name,'Odexi');
});
test('unified office keeps saved IDs but removes native aliases and uses native state',()=>{
 const fleet=[{id:'rend',runtime_id:'main',state:'idle',transport:'connected'}, {id:'rend--codex',runtime_id:'codex',control_center_gateway:'rend',state:'working',transport:'connected'}];
 const snapshot={agents:[{id:'orchestrator',runtime_id:'codex',isDirector:true},{id:'runtime-main',runtime_id:'main'}],factoryAgents:[{id:'codex',runtime_id:'codex'},{id:'rend',runtime_id:'main'}],interactions:[{from:'factory-codex',to:'factory-rend'}]};
 const result=api.unifiedOffice(snapshot,fleet,'rend');assert.equal(result.agents.length,2);assert.equal(result.factoryAgents.length,0);assert.equal(result.agents[0].mesh_agent_id,'rend--codex');assert.equal(result.agents[0].native.state,'working');assert.equal(result.interactions[0].from,'orchestrator');assert.equal(result.interactions[0].to,'runtime-main');
});
test('current work label ignores connection boilerplate and exposes real task ids',()=>{
 assert.equal(api.workLabel({state:'unknown',transport:'connected',task:'Local host connected',phase:'Authenticated local host'}),'No active task reported');
 assert.equal(api.workLabel({state:'working',transport:'connected',task_id:'PT-2026-101'}),'PT-2026-101');
});
test('pulse colors strictly map current work, idle, error and sleep',()=>{
 assert.equal(api.indicator({state:'unknown',transport:'connected',gateway_agent:true}).state,'idle');
 assert.equal(api.indicator({state:'working',transport:'connected'}).state,'busy');
 assert.equal(api.indicator({state:'idle',transport:'connected',last_result:{severity:'error',code:'mesh_reply_timeout'}}).state,'error');
 assert.equal(api.indicator({state:'idle',transport:'connected',mesh_runtime:{sleeping:true}}).state,'sleeping');
});
test('a recovered or historical failure does not pin an idle agent red',()=>{
 const now=Date.now()/1000;
 assert.equal(api.indicator({state:'idle',transport:'connected',last_result:{severity:'error',code:'mesh_reply_timeout',at:now-360}}).state,'idle');
 assert.equal(api.indicator({state:'idle',transport:'connected',last_result:{severity:'error',code:'mesh_reply_timeout',at:now-30},health:{checked_at:now,gateway_reachable:true,model_provider_reachable:true,configured_model_installed:true}}).state,'idle');
 assert.equal(api.indicator({state:'idle',transport:'connected',last_result:{severity:'error',code:'mesh_reply_timeout',at:now-30},health:{checked_at:now-60,gateway_reachable:true,model_provider_reachable:true}}).state,'error');
});
test('stale work reports expire even while transport remains connected',()=>{
 const agent={state:'working',transport:'connected',activity:{observed_at:new Date(Date.now()-181000).toISOString()}};
 assert.equal(api.indicator(agent).state,'unknown');
 agent.activity.observed_at=new Date().toISOString();
 assert.equal(api.indicator(agent).state,'busy');
});
