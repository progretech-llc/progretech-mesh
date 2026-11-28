(() => {
 const id=document.body.dataset.agent,$=id=>document.getElementById(id);let agent=null,busy=false;
 const write=(direction,text)=>{$('output').textContent+=`${new Date().toLocaleTimeString()} ${direction}\n${text}\n\n`;};
 async function office(operation,args={}){const r=await fetch('/api/agents/'+encodeURIComponent(id)+'/office',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation,args})});const d=await r.json();if(!r.ok||!d.ok)throw Error(d.error||'Office unavailable');return d.result;}
 async function refresh(){if(busy)return;try{
  const r=await fetch('/api/status');if(!r.ok)throw Error('Sign in to reconnect');agent=(await r.json()).agents.find(a=>a.id===id);if(!agent)throw Error('Agent is unavailable');
  const snapshot=(await office('snapshot')).snapshot;
  const tasks=snapshot.tasks.filter(t=>snapshot.orchestratorId===agent.office_agent_id || t.assignee===agent.office_agent_id);
  let text=tasks.map(t=>`${t.title} · ${t.status}\n${t.result||t.description||''}`).join('\n\n');
  if(!agent.office_worker){const c=await MeshRuntime.request(id,'context.read');text=[c.text&&`Reviewed handoff · ${c.author} · ${c.updated_at}\n${c.text}`,text].filter(Boolean).join('\n\n');}
  if(!agent.office_worker){const feed=await MeshRuntime.history(id);if(feed.enabled)$('output').textContent=feed.events.map(m=>`${new Date(m.created*1000).toLocaleTimeString()} ${m.speaker==='user'?'You':m.agent} · ${m.origin}\n${m.text}\n`).join('\n');}
  $('context').textContent=text||'No reviewed handoff or mission result recorded.';$('status').textContent=MeshRuntime.indicator(agent).detail;
 }catch(e){$('status').textContent=e.message;}}
 $('input').onsubmit=async e=>{e.preventDefault();if(busy||!agent)return;busy=true;const text=$('prompt').value,button=e.target.querySelector('button');button.disabled=true;write('OUT',text);$('prompt').value='';
 try{if(agent.office_worker){await office('message',{to:agent.office_agent_id,text});write('SYS','Delivered to the office mailbox; read when the next mission starts.');}else{const r=await MeshRuntime.run(id,'communication.start',{text},j=>$('status').textContent=j.detail);write('IN',r.reply||JSON.stringify(r));}}
 catch(error){write('ERR',error.message);}finally{busy=false;button.disabled=false;refresh();}};
 refresh();const timer=setInterval(refresh,10000);window.addEventListener('pagehide',()=>clearInterval(timer));
})();
