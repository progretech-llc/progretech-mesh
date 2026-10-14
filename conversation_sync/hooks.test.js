import test from 'node:test';
import assert from 'node:assert/strict';
import {route,finalText,chunks,eventKey,telegramBinding} from './hooks.js';
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
 const text='🐱 hello '.repeat(1000);const parts=chunks(text);assert.equal(parts.join(''),text);assert.ok(parts.every(x=>x.length<=3400));
});
test('separate runs of the same prompt are distinct',()=>{
 assert.notEqual(eventKey({runId:'a'},{prompt:'hello'}),eventKey({runId:'b'},{prompt:'hello'}));
});

test('Telegram sent hooks are owner-bound even when SDK omits session key',()=>{
 const ctx={channelId:'telegram',accountId:'default',conversationId:'123'};
 assert.equal(telegramBinding({to:'123'},ctx,cfg,true).agent,'main');
 assert.equal(telegramBinding({to:'telegram:123'},ctx,cfg,true).agent,'main');
 assert.equal(telegramBinding({to:'456'},ctx,cfg,true),null);
 assert.equal(telegramBinding({from:'telegram:123',senderId:'123'},ctx,cfg).agent,'main');
 assert.equal(telegramBinding({from:'telegram:group:-100',senderId:'123'},{...ctx,conversationId:'-100'},cfg),null);
});

test('emoji-only messages respect Telegram UTF-16 limits without breaking characters',()=>{
 const text='🐱'.repeat(5000),parts=chunks(text);
 assert.equal(parts.join(''),text);assert.ok(parts.every(x=>x.length<=3400 && !/^[\uDC00-\uDFFF]|[\uD800-\uDBFF]$/.test(x)));
});

test('explicit native owner conversations sync; internal provenance does not',()=>{
 const ctx={sessionKey:'agent:main:explicit:conversation',channel:'webchat',inputProvenance:{kind:'external_user'}};
 assert.equal(route(ctx,cfg).origin,'openclaw');
 assert.equal(route({...ctx,inputProvenance:{kind:'internal_system'}},cfg),null);
});
