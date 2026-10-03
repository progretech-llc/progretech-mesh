import test from 'node:test';
import assert from 'node:assert/strict';
import {route,finalText,chunks,eventKey} from './hooks.js';
const cfg={agents:['main','imagen'],telegram:[{agent:'main',account:'default',owner:'123'}]};
test('unknown roles and internal jobs are excluded',()=>{
 for(const key of ['agent:reviewer:main','agent:main:subagent:xyz','agent:main:mesh-chatter:abc','agent:main:cron:abc'])assert.equal(route({sessionKey:key},cfg),null);
 assert.equal(route({sessionKey:'agent:main:main',trigger:'heartbeat'},cfg),null);
});
test('Telegram must match the explicitly bound owner',()=>{
 const ctx={sessionKey:'agent:main:main',channel:'telegram',senderId:'123'};
 assert.equal(route(ctx,cfg).origin,'telegram');
 assert.equal(route({...ctx,senderId:'456'},cfg),null);
});
test('OpenHands preserves canonical project and source',()=>{
 const row=route({sessionKey:'agent:main:factory-api:Product:abc',channel:'openhands'},cfg);
 assert.equal(row.origin,'openhands');assert.equal(row.project,'Product');
});
test('final reply excludes previous turns and tools',()=>{
 assert.equal(finalText([{role:'assistant',content:'old'},{role:'user',content:'new'},{role:'assistant',content:[{type:'toolCall',name:'exec'}]},{role:'toolResult',content:'secret tool result'},{role:'assistant',content:[{type:'text',text:'reply'}]}]),'reply');
});
test('chunks preserve all Unicode text and order',()=>{
 const text='🐱 hello '.repeat(1000);const parts=chunks(text);assert.equal(parts.join(''),text);assert.ok(parts.every(x=>Array.from(x).length<=3400));
});
test('separate runs of the same prompt are distinct',()=>{
 assert.notEqual(eventKey({runId:'a'},{prompt:'hello'}),eventKey({runId:'b'},{prompt:'hello'}));
});
