import test from 'node:test';
import assert from 'node:assert/strict';
import {forwardControlCenter, discoverControlAgents} from './control-center.js';

test('gateway targets its own identity by default', async () => {
  let sent;
  const result = await forwardControlCenter({action:'profile.get', args:{}}, 'lyra', 'test-token', async (url, options) => {
    sent = {url, options}; return {ok:true, json:async () => ({ok:true, result:{agent_id:'lyra'}})};
  });
  assert.equal(JSON.parse(sent.options.body).agent_id, 'lyra');
  assert.equal(sent.url, 'http://127.0.0.1:8787/api/mesh/control-center');
  assert.equal(result.result.agent_id, 'lyra');
});
test('linked role is restricted to the gateway namespace', async () => {
  let sent;
  await forwardControlCenter({action:'profile.get',agent_id:'rend--researcher'},'rend','test',async (_,options)=>{
    sent=JSON.parse(options.body);return {ok:true,json:async()=>({ok:true})};
  });
  assert.equal(sent.agent_id,'rend--researcher');
  await assert.rejects(forwardControlCenter({action:'profile.get',agent_id:'someone-else--researcher'},'rend','test'),/agent_binding_required/);
});
test('discovery exposes only locally approved roles belonging to this gateway', async () => {
  const roles=await discoverControlAgents('rend','test',async()=>({ok:true,json:async()=>({agents:[{id:'rend'},{id:'rend--researcher'},{id:'other--researcher'}]})}));
  assert.deepEqual(roles,[{id:'rend'},{id:'rend--researcher'}]);
  assert.equal(await discoverControlAgents('rend','test',async()=>({ok:false})),null);
});
test('global voice mutation and arbitrary actions are rejected', async () => {
  for (const action of ['voice.settings','voice.select','shell.exec']) {
    await assert.rejects(forwardControlCenter({action,args:{}},'lyra','test'), /action_not_allowed/);
  }
});
test('missing identity and local credentials fail closed', async () => {
  await assert.rejects(forwardControlCenter({action:'profile.get'},'','test'), /agent_binding_required/);
  await assert.rejects(forwardControlCenter({action:'profile.get'},'lyra',''), /local_auth_missing/);
});
test('local provider failure is preserved', async () => {
  const result = await forwardControlCenter({action:'voice.start'},'lyra','test',async () => ({ok:false,json:async () => ({ok:false,error:'permission_required'})}));
  assert.equal(result.error,'permission_required');
});
test('wake, sleep and progress polling use the same scoped host bridge', async () => {
  const sent=[];
  for(const action of ['runtime.wake','runtime.sleep','communication.job']) {
    await forwardControlCenter({action,agent_id:'rend--progre',args:action==='communication.job'?{job_id:'a'.repeat(32)}:{}},'rend','fixture',async(_,opts)=>{
      sent.push(JSON.parse(opts.body));return {ok:true,json:async()=>({ok:true})};
    });
  }
  assert.deepEqual(sent.map(x=>x.action),['runtime.wake','runtime.sleep','communication.job']);
  assert.ok(sent.every(x=>x.agent_id==='rend--progre'));
});
test('chunked artifact transfer is owner-bound and bounded separately from ordinary controls', async () => {
 let body;
 await forwardControlCenter({action:'files.chunk',agent_id:'rend--designer',args:{upload_id:'a'.repeat(32),offset:0,data:'A'.repeat(44000)}},'rend','fixture',async(_,options)=>{body=JSON.parse(options.body);return {ok:true,json:async()=>({ok:true,result:{offset:32768}})};});
 assert.equal(body.agent_id,'rend--designer');
 await assert.rejects(forwardControlCenter({action:'files.chunk',agent_id:'other--designer',args:{}},'rend','fixture'),/binding/);
 await assert.rejects(forwardControlCenter({action:'files.chunk',args:{data:'A'.repeat(65536)}},'rend','fixture'),/too_large/);
 await assert.rejects(forwardControlCenter({action:'profile.save',args:{data:'A'.repeat(20000)}},'rend','fixture'),/too_large/);
});
test('floor encounters use the scoped host bridge without changing their receipt data', async()=>{
 const args={tab_id:'a'.repeat(32),participants:['rend','rend--imagen'],positions:[{x:500,y:350},{x:600,y:350}],idea_id:''};let sent;
 await forwardControlCenter({action:'chatter.encounter',args},'rend','fixture',async(_,opts)=>{sent=JSON.parse(opts.body);return {ok:true,json:async()=>({ok:true,result:{state:'approaching'}})};});
 assert.deepEqual(sent,{agent_id:'rend',action:'chatter.encounter',args});
 await assert.rejects(forwardControlCenter({action:'chatter.encounter',agent_id:'other',args},'rend','fixture'),/agent_binding_required/);
});
