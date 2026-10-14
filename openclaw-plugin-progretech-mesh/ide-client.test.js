import test from 'node:test';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {forwardRoleCompletion,IDE_ROLE_ALIASES} from './ide-client.js';
const config={gateway:{port:18789,auth:{mode:'token',token:'test-secret'}},agents:{entries:Object.fromEntries(Object.values(IDE_ROLE_ALIASES).map(id=>[id,{}]))}};
const response={ok:true,json:async()=>({id:'x',choices:[{message:{role:'assistant',content:null,tool_calls:[{id:'a',type:'function',function:{name:'lookup',arguments:'{}'}}]},finish_reason:'tool_calls'}]})};
test('all aliases select only configured role without model override',async()=>{
 for(const [model,agent] of Object.entries(IDE_ROLE_ALIASES)) {
  let called=false;
  const result=await forwardRoleCompletion(config,{model,messages:[{role:'user',content:'Hi'}]},async(url,options)=>{
   called=true;assert.equal(url,'http://127.0.0.1:18789/v1/chat/completions');assert.equal(options.headers['x-openclaw-agent-id'],agent);assert.equal(JSON.parse(options.body).model,`openclaw/${agent}`);assert.equal(options.redirect,'error');return response;
  });assert.ok(called);assert.equal(result.model,model);
 }
});
test('original messages and tools preserved; stream forced false; separate sessions',async()=>{
 const messages=[{role:'system',content:'Instructions'},{role:'user',content:'Hi'},{role:'assistant',content:null,tool_calls:[{id:'a',type:'function',function:{name:'lookup',arguments:'{}'}}]},{role:'tool',tool_call_id:'a',content:'done'}];
 const tools=[{type:'function',function:{name:'lookup',parameters:{type:'object'}}}];
 const out=await forwardRoleCompletion(config,{model:'mak',messages,tools,tool_choice:'auto',stream:true,user:'caller'},async(_,options)=>{
  const body=JSON.parse(options.body);assert.deepEqual(body.messages,messages);assert.deepEqual(body.tools,tools);assert.equal(body.stream,false);assert.equal(body.tool_choice,'auto');assert.match(options.headers['x-openclaw-session-key'],/^agent:coder:mesh-api:/);return response;
 });assert.ok(out.choices[0].message.tool_calls);
});
test('reject unknown/unconfigured model, model override and malformed body',async()=>{
 for(const body of [{model:'gpt-x',messages:[]},{model:'mak',messages:[]},{model:'mak',messages:[{}],model_override:'other'},[]]) await assert.rejects(forwardRoleCompletion(config,body));
 await assert.rejects(forwardRoleCompletion({...config,agents:{entries:{}}},{model:'mak',messages:[{}]}),/role_not_available/);
});
test('upstream errors never include sensitive bodies or fetch details',async()=>{
 await assert.rejects(forwardRoleCompletion(config,{model:'rend',messages:[{}]},async()=>({ok:false,status:500,json:()=>{throw Error('secret')}})),/^Error: ide_gateway_http_500$/);
 await assert.rejects(forwardRoleCompletion(config,{model:'rend',messages:[{}]},async()=>{throw Error('token=test-secret')}),/^Error: ide_gateway_unreachable$/);
});
test('bounded timeout aborts and is sanitized',async()=>{
 await assert.rejects(forwardRoleCompletion(config,{model:'rend',messages:[{}]},async(_,options)=>new Promise((_,reject)=>{
  const keepAlive=setTimeout(()=>reject(Error('did not abort')),100);options.signal.addEventListener('abort',()=>{clearTimeout(keepAlive);reject(options.signal.reason);});
 }),{timeoutMs:3}),/^Error: ide_gateway_timeout$/);
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
