import {test} from 'node:test';import assert from 'node:assert/strict';
import {createReleaseWatch} from './release-watch.js';
function fixture(){let build='release-a',busy=false,broken=false;const reconnects=[];
 const watch=createReleaseWatch({mesh:'https://mesh.example',idle:()=>!busy,reconnect:x=>reconnects.push(x),fetchImpl:async(url,opts)=>{assert.equal(url,'https://mesh.example/healthz');assert.equal(opts.redirect,'error');if(broken)throw Error('offline');return {ok:true,text:async()=>JSON.stringify({ok:true,service:'progretech-mesh',build})};}});
 return {watch,reconnects,setBuild:x=>build=x,setBusy:x=>busy=x,break:()=>broken=true};}
test('release changes need two observations and wait for idle relay work',async()=>{const f=fixture();f.watch.paired('release-a');f.setBuild('release-b');await f.watch.poll();assert.equal(f.reconnects.length,0);f.setBusy(true);await f.watch.poll();assert.equal(f.reconnects.length,0);f.setBusy(false);await f.watch.poll();assert.deepEqual(f.reconnects,[{from:'release-a',to:'release-b'}]);await f.watch.poll();assert.equal(f.reconnects.length,1);});
test('stable release and network failures do not reconnect',async()=>{const f=fixture();await f.watch.poll();await f.watch.poll();f.break();await f.watch.poll();assert.equal(f.reconnects.length,0);});
test('transient mixed rollout and stopped watcher do not reconnect',async()=>{const f=fixture();f.watch.paired('release-a');f.setBuild('release-b');await f.watch.poll();f.setBuild('release-a');await f.watch.poll();f.setBuild('release-b');await f.watch.poll();assert.equal(f.reconnects.length,0);f.watch.stop();await f.watch.poll();assert.equal(f.reconnects.length,0);});

 test('release reconnect uses a client-legal close code', async()=>{
  const {closeForRelease}=await import('./release-watch.js');
  const socket=new WebSocket('ws://127.0.0.1:1');
  socket.addEventListener('error',()=>{});
  assert.doesNotThrow(()=>closeForRelease(socket));
 });

test('release reconnect is retryable while authentication rejection remains terminal', async()=>{
 const {closeForRelease,isAuthenticationClose}=await import('./release-watch.js');
 let code;closeForRelease({close:value=>{code=value;}});
 assert.equal(code,1000);assert.equal(isAuthenticationClose(code),false);
 for(const rejected of [4001,4003,4401,4403])assert.equal(isAuthenticationClose(rejected),true);
});
