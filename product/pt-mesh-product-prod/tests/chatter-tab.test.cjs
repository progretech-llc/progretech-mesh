const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function fixture() {
  const events={}, calls=[], timers=[], releases=[];
  const window={addEventListener:(name,callback)=>events[name]=callback};
  const ctx={window,crypto:{randomUUID:()=> 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'},setInterval:fn=>{timers.push(fn);return timers.length;},clearInterval:()=>{},fetch:(url,args)=>{releases.push([url,JSON.parse(args.body)]);return Promise.resolve();}};
  vm.runInNewContext(fs.readFileSync('static/js/chatter-tab.js','utf8'),ctx);
  const runtime={request:async(agent,action,args)=>{calls.push([agent,action,args]);return {enabled:args.enabled!==false,tab_id:args.tab_id};}};
  return {tab:new window.MeshChatterTab(runtime),events,calls,timers,releases,runtime};
}
test('opening and status observations never enable chatter; explicit enable renews',async()=>{
  const f=fixture();await f.tab.heartbeat();assert.equal(f.calls.length,0);
  f.tab.observe('host',{enabled:true,tab_id:'b'.repeat(32)});await f.tab.heartbeat();assert.equal(f.calls.length,0);
  await f.tab.configure('host',{enabled:true});await f.tab.heartbeat();
  assert.deepEqual(f.calls.map(c=>c[1]),['chatter.configure','chatter.configure']);
  assert.equal(f.calls[1][2].renew_only,true);
  assert.equal(f.calls[0][2].tab_id,'a'.repeat(32));
});
test('closing or navigating releases only this tab; restored page requires enablement',async()=>{
  const f=fixture();await f.tab.configure('host',{enabled:true});f.events.pagehide();
  assert.equal(f.releases.length,1);assert.equal(f.releases[0][1].args.enabled,false);
  f.events.pageshow();await f.tab.heartbeat();assert.equal(f.calls.length,1);
});
test('expired renewal never automatically re-enables',async()=>{
  const f=fixture();await f.tab.configure('host',{enabled:true});
  f.runtime.request=async()=>{throw Error('chatter_tab_expired');};
  await f.tab.heartbeat();assert.equal(f.tab.agent,null);
  await f.tab.heartbeat();assert.equal(f.calls.length,1);
});
test('tab closure during enablement also releases a late successful enable',async()=>{
  const f=fixture();let resolve;
  f.runtime.request=()=>new Promise(r=>resolve=r);
  const pending=f.tab.configure('host',{enabled:true});f.events.pagehide();
  resolve({enabled:true,tab_id:'a'.repeat(32)});await pending;
  assert.equal(f.tab.agent,null);assert.equal(f.releases.length,2);
});
