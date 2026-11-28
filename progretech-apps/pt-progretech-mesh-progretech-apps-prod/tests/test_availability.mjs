import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const code=readFileSync(new URL('../static/js/availability.js',import.meta.url),'utf8');
function client(results) {
  const calls=[];const context={window:{},Date,setTimeout:fn=>fn(),fetch:async(url,options)=>{
    calls.push({url,...JSON.parse(options.body)});
    return {ok:true,json:async()=>({ok:true,result:results.shift()})};
  }};
  vm.runInNewContext(code,context);return {api:context.window.MeshAvailability,calls};
}
test('unknown never renders Awake and cannot trigger sleep',async()=>{
  const {api,calls}=client([]);
  assert.equal(api.label({sleeping:null}),'Availability unknown');
  assert.equal(api.label({sleeping:false}),'Awake');
  assert.equal(api.label({sleeping:true}),'Asleep');
  await assert.rejects(api.power('host--imagen',null),/unknown/);assert.equal(calls.length,0);
});
test('inactive agent wakes through scoped job polling',async()=>{
  const {api,calls}=client([{job_id:'a'.repeat(32),done:false},{done:true,result:{sleeping:false}}]);
  const result=await api.power('host--imagen',true);
  assert.equal(result.sleeping,false);assert.equal(calls[0].action,'runtime.wake');
  assert.equal(calls[1].action,'communication.job');
  assert.ok(calls.every(c=>c.url==='/api/agents/host--imagen/control-center'));
});
test('host failure is reported without resubmitting wake',async()=>{
  const {api,calls}=client([{done:true,error:'runtime_controls_unavailable'}]);
  await assert.rejects(api.power('host--imagen',true),/runtime_controls_unavailable/);
  assert.equal(calls.length,1);
});
