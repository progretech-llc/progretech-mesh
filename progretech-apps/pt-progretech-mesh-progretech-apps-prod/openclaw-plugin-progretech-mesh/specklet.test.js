import {test} from 'node:test';
import assert from 'node:assert/strict';
import {registerSpecklet} from './specklet.js';
test('task tool binds runtime, preserves revision conflicts and never accepts model runtime override',async()=>{
 let factory,hook,calls=[];
 const api={registerTool:f=>factory=f,on:(_name,f)=>hook=f};
 const boards=[{boardId:'host--reviewer',revision:2,localFile:'/fixture/reviewer.json',workspace:{tasks:[{id:'t',title:'Scope',status:'open',meshStatus:'doing',notes:'Review'}]}}];
 registerSpecklet(api,()=> 'fixture',async(_url,options)=>{calls.push(JSON.parse(options.body));return {ok:true,json:async()=>({ok:true,result:{boards}})};});
 const ctx={agentId:'reviewer'},tool=factory.create(ctx);
 await tool.execute('id',{action:'get',runtime:'main'});assert.equal(calls[0].runtime,'reviewer');
 const h=await hook({},ctx);assert.match(h.appendSystemContext,/MemPalace/);assert.match(h.appendSystemContext,/Scope/);
 await tool.execute('id',{action:'task',boardId:'host--reviewer',revision:2,task:{id:'t',status:'done'}});
 assert.equal(calls.at(-1).args.revision,2);assert.equal(calls.at(-1).runtime,'reviewer');
});
test('disabled board adds no board instructions and failed host does not claim saved status',async()=>{
 let factory,hook;const api={registerTool:f=>factory=f,on:(_n,f)=>hook=f};
 registerSpecklet(api,()=> 'fixture',async()=>({ok:true,json:async()=>({ok:true,result:{boards:[]}})}));
 assert.equal(await hook({},{agentId:'reviewer'}),undefined);
 const result=await factory.create({}).execute('id',{action:'get'});assert.equal(result.isError,true);
 registerSpecklet(api,()=> 'fixture',async()=>({ok:false,json:async()=>({ok:false,error:'specklet_revision_conflict'})}));
 const failure=await factory.create({agentId:'reviewer'}).execute('id',{action:'task',boardId:'x',revision:1,task:{status:'done'}});assert.equal(failure.isError,true);assert.match(failure.content[0].text,/revision_conflict/);
});
