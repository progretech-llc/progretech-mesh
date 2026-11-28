import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {recordInteraction,recordAgentResult} from './interactions.js';
test('Only successful exact named handoffs publish metadata; prompt stays private',()=>{
 const root=mkdtempSync(join(tmpdir(),'mesh-interaction-'));try{
 recordInteraction(root,{toolName:'sessions_send',params:{sessionKey:'agent:coder:main',message:'PRIVATE'}},{agentId:'researcher'});
 recordInteraction(root,{toolName:'sessions_send',error:'rejected',params:{sessionKey:'agent:main:main'}},{agentId:'researcher'});
 const raw=readFileSync(join(root,'agent-interactions.json'),'utf8'),rows=JSON.parse(raw);assert.equal(rows.length,1);assert.equal(rows[0].from,'lyra');assert.equal(rows[0].to,'mak');assert.ok(!raw.includes('PRIVATE'));
 recordAgentResult(root,{success:false},{agentId:'researcher'});assert.equal(JSON.parse(readFileSync(join(root,'agent-signals/researcher.json'),'utf8')).severity,'error');
 }finally{rmSync(root,{recursive:true,force:true});}
});
