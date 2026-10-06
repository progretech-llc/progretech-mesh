import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const sandbox={window:{}};vm.runInNewContext(readFileSync(new URL('../static/js/runtime-client.js',import.meta.url),'utf8'),sandbox);
const indicator=sandbox.window.MeshRuntime.indicator;
test('lights explain actual errors, neutral status and current monitoring',()=>{
 const a={state:'idle',transport:'connected',mesh_runtime:{last_result:{severity:'error',code:'native_agent_failed',at:1700000000}}};
 assert.equal(indicator(a).state,'error');assert.match(indicator(a).detail,/outside this Mesh conversation/);assert.match(indicator(a).detail,/Recorded/);
 assert.equal(indicator(a,{monitoring:true}).state,'error'); // A view option cannot hide a recorded failure.
 a.mesh_runtime.sleeping=true;assert.equal(indicator(a).state,'sleeping');
 a.mesh_runtime.sleeping=false;a.state='active';assert.equal(indicator(a).state,'busy');
 a.state='idle';a.mesh_runtime.last_result={};assert.equal(indicator(a).state,'idle');
 a.mesh_runtime.last_result={severity:'success',code:'native_turn_complete'};assert.equal(indicator(a).state,'idle');
});

test('memory indicator never turns unavailable logging into verified activity',()=>{
 const label=sandbox.window.MeshRuntime.memoryLabel;
 assert.match(label({latest_status:'activity_write_unavailable'}),/write failed/);
 assert.match(label({latest_status:'runtime_activity',recall_verified:true,memory_id:'fixture',activity_kind:'runtime_activity'}),/reviewed summary missing/);
 assert.match(label({latest_status:'no_change',recall_verified:true,memory_id:'fixture',activity_kind:'reviewed_activity'}),/reviewed activity/);
 assert.match(label({recall_verified:false,memory_id:'fixture'}),/no verified/);
});

test('fresh connectivity never hides a recorded provider error',()=>{
 const now=Date.now()/1000;const a={state:'idle',mesh_runtime:{last_result:{severity:'error',code:'mesh_provider_unavailable',at:now-120},health:{state:'reachable',checked_at:now,gateway_reachable:true,model_provider_reachable:true}}};
 assert.equal(indicator(a).state,'error');assert.match(indicator(a).detail,/earlier request could not reach/);assert.match(indicator(a).detail,/reachable/);
 a.mesh_runtime.health.checked_at=now-50;assert.equal(indicator(a).state,'error');
 a.mesh_runtime.health.checked_at=now-200;assert.equal(indicator(a).state,'error');
 a.mesh_runtime.health={state:'unavailable',checked_at:now};assert.equal(indicator(a).state,'error');
 a.mesh_runtime.last_result.code='mesh_context_limit';a.mesh_runtime.health.state='reachable';assert.equal(indicator(a).state,'error');
 a.mesh_runtime.last_result.code='mesh_provider_unavailable';a.state='active';assert.equal(indicator(a).state,'busy');
});
