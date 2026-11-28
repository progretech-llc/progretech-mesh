import test from 'node:test';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {forwardRoleCompletion} from './ide-client.js';
const config={gateway:{port:18789,http:{endpoints:{chatCompletions:{enabled:true}}},auth:{mode:'token',token:'synthetic-test-only'}},agents:{entries:{main:{},custom_role:{}}}};
const response={ok:true,json:async()=>({id:'x',choices:[{message:{role:'assistant',content:null,tool_calls:[{id:'a',type:'function',function:{name:'lookup',arguments:'{}'}}]},finish_reason:'tool_calls'}]})};
const host={target:{agent_id:'any-host',gateway_id:'any-host',runtime_id:'main'},gatewayId:'any-host',agents:[{id:'any-host',runtime_id:'main'}]};
test('custom host selects its actual configured intake role without aliases',async()=>{
 const result=await forwardRoleCompletion(config,{model:'any-host',messages:[{role:'user',content:'Hi'}]},async(url,options)=>{
  assert.equal(url,'http://127.0.0.1:18789/v1/chat/completions');assert.equal(options.headers['x-openclaw-agent-id'],'main');assert.equal(JSON.parse(options.body).model,'openclaw/main');assert.equal(options.redirect,'error');return response;
 },host);assert.equal(result.model,'any-host');
});
test('original messages and tools preserved with isolated sessions',async()=>{
 const messages=[{role:'user',content:'Hi'},{role:'assistant',content:null,tool_calls:[{id:'a',type:'function',function:{name:'lookup',arguments:'{}'}}]},{role:'tool',tool_call_id:'a',content:'done'}];
 const tools=[{type:'function',function:{name:'lookup',parameters:{type:'object'}}}];
 const out=await forwardRoleCompletion(config,{model:'any-host',messages,tools,tool_choice:'auto',stream:true,user:'caller'},async(_,options)=>{
  const body=JSON.parse(options.body);assert.deepEqual(body.messages,messages);assert.deepEqual(body.tools,tools);assert.equal(body.stream,false);assert.equal(body.tool_choice,'auto');assert.match(options.headers['x-openclaw-session-key'],/^agent:main:mesh-api:/);return response;
 },host);assert.ok(out.choices[0].message.tool_calls);
});
test('retired aliases and targetless requests cannot reach inference',async()=>{
 const forbidden=async()=>assert.fail('must not dispatch');
 for(const model of ['rend-code','rend-research','mak','lyra','odexi','any-host-code'])
  await assert.rejects(forwardRoleCompletion(config,{model,messages:[{}]},forbidden,host),/ide_role_binding_invalid/);
 await assert.rejects(forwardRoleCompletion(config,{model:'any-host',messages:[{}]},forbidden),/ide_role_binding_invalid/);
 await assert.rejects(forwardRoleCompletion(config,{model:'any-host',messages:[{}]},forbidden,{...host,agents:[]}),/ide_role_binding_unavailable/);
 await assert.rejects(forwardRoleCompletion({...config,agents:{entries:{}}},{model:'any-host',messages:[{}]},forbidden,host),/ide_role_not_available/);
 await assert.rejects(forwardRoleCompletion(config,{model:'any-host',messages:[{}],model_override:'other'},forbidden,host),/ide_unsupported_parameter/);
});
test('upstream errors never include sensitive bodies or fetch details',async()=>{
 await assert.rejects(forwardRoleCompletion(config,{model:'any-host',messages:[{}]},async()=>({ok:false,status:500,json:()=>{throw Error('secret')}}),host),/^Error: ide_gateway_http_500$/);
 await assert.rejects(forwardRoleCompletion(config,{model:'any-host',messages:[{}]},async()=>{throw Error('secret')},host),/^Error: ide_gateway_unreachable$/);
});
test('bounded timeout aborts and is sanitized',async()=>{
 await assert.rejects(forwardRoleCompletion(config,{model:'any-host',messages:[{}]},async(_,options)=>new Promise((_,reject)=>{
  const keepAlive=setTimeout(()=>reject(Error('did not abort')),100);options.signal.addEventListener('abort',()=>{clearTimeout(keepAlive);reject(options.signal.reason);});
 }),{...host,timeoutMs:3}),/^Error: ide_gateway_timeout$/);
});

test('imported custom role selects exact local binding and isolated native API session',async()=>{
 const target={agent_id:'host-a--custom_role',gateway_id:'host-a',runtime_id:'custom_role'};
 const cfg={...config,agents:{entries:{...config.agents.entries,custom_role:{}}}};
 const agents=[{id:target.agent_id,runtime_id:'custom_role'}];
 const body={model:target.agent_id+'-code',messages:[{role:'user',content:'Synthetic fixture'}],user:'token-scoped-test-hash'};
 const out=await forwardRoleCompletion(cfg,body,async(_,options)=>{
  assert.equal(options.headers['x-openclaw-agent-id'],'custom_role');
  assert.match(options.headers['x-openclaw-session-key'],/^agent:custom_role:mesh-api:/);
  assert.notEqual(options.headers['x-openclaw-session-key'],'agent:custom_role:main');
  assert.equal(JSON.parse(options.body).model,'openclaw/custom_role');return response;
 },{target,gatewayId:'host-a',agents});
 assert.equal(out.model,body.model);
});

test('imported role cannot switch host, role, alias, hidden binding or disabled office worker',async()=>{
 const target={agent_id:'host-a--custom_role',gateway_id:'host-a',runtime_id:'custom_role'};
 const cfg={...config,agents:{entries:{custom_role:{},main:{}}}};
 const body={model:target.agent_id,messages:[{role:'user',content:'Synthetic fixture'}]};
 const options={target,gatewayId:'host-a',agents:[{id:target.agent_id,runtime_id:'custom_role'}]};
 const forbidden=async()=>{assert.fail('No invalid request may reach native runtime');};
 for(const change of [
  {gatewayId:'host-b'}, {target:{...target,runtime_id:'main'}},
  {target:{...target,agent_id:'host-b--custom_role',gateway_id:'host-b'}},
  {target:{...target,extra:'untrusted'}}, {target:null}, {agents:[]},
  {agents:[{id:target.agent_id,runtime_id:'main'}]},
  {agents:[{id:target.agent_id,runtime_id:'custom_role',office_worker:true}]},
  {agents:[{id:target.agent_id,runtime_id:'custom_role',office_archived:true}]},
 ]) await assert.rejects(forwardRoleCompletion(cfg,body,forbidden,{...options,...change}),/ide_role_binding/);
 await assert.rejects(forwardRoleCompletion(cfg,{...body,model:'rend'},forbidden,options),/ide_role_binding/);
 await assert.rejects(forwardRoleCompletion({...cfg,agents:{entries:{}}},body,forbidden,options),/ide_role_not_available/);
});


test('long custom native IDs keep exact configured identity behind hashed fleet ID',async()=>{
 const runtime='custom_native_role_with_a_long_name';
 const agent='host-a--role_'+createHash('sha256').update(runtime).digest('hex').slice(0,24);
 const target={agent_id:agent,gateway_id:'host-a',runtime_id:runtime};
 const cfg={...config,agents:{entries:{[runtime]:{}}}};
 const out=await forwardRoleCompletion(cfg,{model:agent+'-code',messages:[{role:'user',content:'Synthetic fixture'}]},async(_,options)=>{
  assert.equal(options.headers['x-openclaw-agent-id'],runtime);return response;
 },{target,gatewayId:'host-a',agents:[{id:agent,runtime_id:runtime}]});
 assert.equal(out.model,agent+'-code');
});

test('SecretRef authentication uses supported resolver and never falls back on failure',async()=>{
 const ref={source:'store',provider:'default',id:'SYNTHETIC_KEY'};
 const cfg={...config,gateway:{port:18789,http:{endpoints:{chatCompletions:{enabled:true}}},auth:{mode:'token',token:ref}}};
 const body={model:'any-host',messages:[{role:'user',content:'Fixture'}]};
 let resolutions=0;
 const resolveSecretInput=async params=>{
  resolutions++;assert.equal(params.path,'gateway.auth.token');assert.equal(params.value,ref);
  return {value:'synthetic-resolved-token'};
 };
 await forwardRoleCompletion(cfg,body,async(_,options)=>{
  assert.equal(options.headers.Authorization,'Bearer synthetic-resolved-token');return response;
 },{...host,resolveSecretInput});
 assert.equal(resolutions,1);
 const forbidden=async()=>assert.fail('unresolved credentials must not reach transport');
 await assert.rejects(forwardRoleCompletion(cfg,body,forbidden,{...host,resolveSecretInput:async()=>({})}),/^Error: ide_gateway_token_auth_required$/);
 await assert.rejects(forwardRoleCompletion(cfg,body,forbidden,{...host,resolveSecretInput:async()=>{throw Error('private diagnostic')}}),/^Error: ide_gateway_token_auth_required$/);
});

test('large-model budget permits native attempts but rejects unbounded waits',async()=>{
 const body={model:'any-host',messages:[{role:'user',content:'Fixture'}]};
 await forwardRoleCompletion(config,body,async()=>response,{...host,timeoutMs:590000});
 for (const timeoutMs of [0,-1,590001,Infinity,NaN]) {
  await assert.rejects(forwardRoleCompletion(config,body,async()=>assert.fail('invalid budget dispatched'),{...host,timeoutMs}),/^Error: ide_timeout_invalid$/);
 }
});

test('disabled gateway API is reported without sending an inference request',async()=>{
 const disabled={...config,gateway:{...config.gateway,http:{}}};
 await assert.rejects(forwardRoleCompletion(disabled,{model:'any-host',messages:[{role:'user',content:'Hi'}]},()=>assert.fail('disabled API must not be called'),host),/ide_chat_endpoint_disabled/);
});
