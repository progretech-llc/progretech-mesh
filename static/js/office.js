(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const stages = {intake:'Intake',ready:'Ready',working:'In progress',blocked:'Needs input',review:'Review',done:'Done'};
  let snapshot=null, fleet=[], chatter=null, pending=false, sharedPending=false, online=false, epoch=0, zoom=1;
  let positions={}, selected=null, taskId=null, draggedTask=null, artifacts=[], sharedSignature='';
  const host=()=>$('officeHost').value;
  const say=text=>{$('officeStatus').textContent=text;};
  const scrum=a=>Boolean(a.isScrumMaster || a.isDirector);
  const stage=t=>t.stage || ({todo:'intake',doing:'working',blocked:'blocked',done:'done'}[t.status] || 'intake');
  const agentName=id=>snapshot?.agents.find(a=>a.id===id)?.name || 'Scrum Master';
  const chatterTab=new MeshChatterTab(MeshRuntime,()=>loadShared());
  async function api(operation,args={}) {
    const gateway=host(),requestEpoch=epoch;
    if(!gateway)throw Error('Connect an OpenClaw gateway from the agent fleet first.');
    const response=await fetch(`/api/agents/${encodeURIComponent(gateway)}/office`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation,args})});
    const data=await response.json();
    if(requestEpoch!==epoch)throw Error('Gateway changed; refresh before continuing.');
    if(!response.ok || !data.ok){
      const messages={task_running:'This task is still running. Wait for its agent to finish before changing its assignment or deleting it.',task_has_dependents:'Another task depends on this one. Remove that dependency before deleting it.',dependency_cycle:'These dependencies would form a loop. Choose a different prerequisite.',dependency_not_found:'A prerequisite is no longer available. Refresh the board and choose it again.',task_not_found:'This task is no longer on the board. Refresh to see the latest work.',office_paused:'Work is paused. Resume work before starting this task.',task_not_ready:'This task is waiting for its prerequisites or requested input.',gateway_not_connected:'Your OpenClaw gateway is offline. Reconnect it to continue.',office_runtime_binding_required:'Import a connected OpenClaw agent before starting work.',approval_not_pending:'There is no unanswered request for this task.',task_run_required:'Use Start work to ask an agent to begin this task.'};
      throw Error(messages[data.error] || data.error || 'The gateway could not complete this action.');
    }
    return data.result;
  }
  function fit() {
    const floor=$('officeFloor'),scale=Math.min(floor.clientWidth/1000,floor.clientHeight/700)*zoom;
    $('floorWorld').style.transform=`translate(${(floor.clientWidth-1000*scale)/2}px,${(floor.clientHeight-700*scale)/2}px) scale(${scale})`;
    $('floorWorld').style.setProperty('--node-scale',Math.min(2,Math.max(1,.75/scale)));
  }
  function savePositions(){try{sessionStorage.setItem('mesh-office-layout:'+host(),JSON.stringify(positions));}catch{}}
  function renderFloor() {
    const agents=snapshot.agents,workers=agents.filter(a=>!scrum(a));
    $('floorEmpty').hidden=agents.length>0;
    for(const a of agents) {
      if(!positions[a.id]){
        const angle=2*Math.PI*workers.indexOf(a)/Math.max(1,workers.length)-Math.PI/2;
        positions[a.id]=scrum(a)?{x:500,y:350}:{x:500+320*Math.cos(angle),y:350+220*Math.sin(angle)};
      }
    }
    const markup=agents.map(a=>{
      const indicator=a.native?MeshRuntime.indicator(a.native):{state:a.state || 'idle',label:a.state || 'Idle'};
      const working=snapshot.tasks.find(t=>t.assignee===a.id && (t.running || stage(t)==='working'));
      const state=working?'working':indicator.state;
      const role=scrum(a)?'Scrum Master':working?working.title:a.role;
      const p=positions[a.id],source=MeshAvatar.source(a);
      return `<button type="button" class="floor-node ${scrum(a)?'scrum-master':''} ${esc(state)} ${selected===a.id?'selected':''}" data-agent="${esc(a.id)}" style="left:${p.x}px;top:${p.y}px" aria-label="${esc(a.name)}, ${esc(role)}, ${esc(indicator.label)}" title="${esc(role)}"><span class="node-orb">${source?`<img src="${esc(source)}" alt="">`:esc(a.name.slice(0,2))}</span><span class="node-state"></span><span class="node-name">${esc(a.name)}</span><span class="node-role">${esc(role)}</span></button>`;
    }).join('');
    const container=$('floorNodes'),template=document.createElement('template');template.innerHTML=markup;
    const old=new Map([...container.children].map(n=>[n.dataset.agent,n]));
    [...template.content.children].forEach((next,index)=>{
      let node=old.get(next.dataset.agent);
      if(node){for(const attr of next.attributes)if(node.getAttribute(attr.name)!==attr.value)node.setAttribute(attr.name,attr.value);if(node.innerHTML!==next.innerHTML)node.innerHTML=next.innerHTML;}else node=next;
      if(container.children[index]!==node)container.insertBefore(node,container.children[index]||null);old.delete(node.dataset.agent);
    });
    old.forEach(node=>node.remove());
    container.querySelectorAll('[data-agent]').forEach(node=>{
      node.onclick=()=>{if(node.dataset.dragged==='true'){node.dataset.dragged='false';return;}selected=node.dataset.agent;};
      node.ondblclick=()=>makeScrum(node.dataset.agent);
      node.onkeydown=e=>{if(e.key==='Enter' || e.key===' '){e.preventDefault();openAgent(node.dataset.agent);}};
      node.oncontextmenu=e=>{e.preventDefault();openAgent(node.dataset.agent);};
      node.onpointerdown=e=>{
        if(e.button!==0)return;
        const start={x:e.clientX,y:e.clientY},id=node.dataset.agent,origin={...positions[id]},scale=Math.min($('officeFloor').clientWidth/1000,$('officeFloor').clientHeight/700)*zoom;
        node.setPointerCapture(e.pointerId);
        node.onpointermove=move=>{if(Math.hypot(move.clientX-start.x,move.clientY-start.y)<5)return;node.dataset.dragged='true';positions[id]={x:Math.max(85,Math.min(915,origin.x+(move.clientX-start.x)/scale)),y:Math.max(100,Math.min(600,origin.y+(move.clientY-start.y)/scale))};node.style.left=positions[id].x+'px';node.style.top=positions[id].y+'px';renderLinks();};
        node.onpointerup=()=>{node.onpointermove=null;savePositions();};node.onpointercancel=()=>{node.onpointermove=null;};
      };
    });
    renderLinks();fit();
  }
  function renderLinks() {
    if(!snapshot)return;
    const links=[...(snapshot.interactions||[])];
    if(chatter?.enabled)for(const c of chatter.conversations||[]){
      if(!['first','second','third','reply_wait'].includes(c.state))continue;
      const ids=[c.a_role,c.b_role,c.c_role].filter(Boolean).map(role=>snapshot.agents.find(a=>a.native?.runtime_id===role || a.runtime_id===role || a.native?.id===role)?.id).filter(Boolean);
      for(let i=1;i<ids.length;i++)links.push({id:'chatter-'+c.id+'-'+i,from:ids[0],to:ids[i],kind:'conversation',title:c.topic});
    }
    $('floorLinks').innerHTML=links.filter(l=>positions[l.from]&&positions[l.to]).map(l=>{const a=positions[l.from],b=positions[l.to];return `<path tabindex="0" role="button" data-interaction="${esc(l.id)}" class="floor-link ${l.kind==='conversation'?'conversation':''}" aria-label="${esc(l.title || 'Agent collaboration')}" d="M${a.x} ${a.y-20} L${b.x} ${b.y-20}"><title>${esc(l.title)}</title></path>`;}).join('');
    $('floorLinks').querySelectorAll('[data-interaction]').forEach(node=>{const open=()=>{const l=links.find(x=>String(x.id)===node.dataset.interaction);$('interactionDetails').textContent=`${agentName(l.from)} ↔ ${agentName(l.to)}\n${l.title || 'Working together'}\n${l.source || 'Recorded host activity'}`;$('interactionDialog').showModal();};node.onclick=open;node.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();open();}};});
  }
  async function makeScrum(id){
    if(!online)return;
    const a=snapshot.agents.find(a=>a.id===id);if(!a || scrum(a))return;
    try{await api('orchestrator.set',{id});await refresh();say(`${a.name} is now Scrum Master.`);if($('agentDialog').open)$('agentDialog').close();}catch(e){say(e.message);}
  }
  function openAgent(id){
    selected=id;const a=snapshot.agents.find(a=>a.id===id);if(!a)return;
    $('agentName').textContent=a.name;$('agentDetail').textContent=scrum(a)?'Scrum Master':a.role;
    $('makeScrumMaster').disabled=scrum(a)||!online;
    const binding=a.mesh_agent_id || fleet.find(f=>(f.control_center_gateway===host()||f.id===host())&&f.runtime_id===(a.native?.runtime_id||a.runtime_id))?.id;
    $('agentMemory').hidden=!binding;$('agentMemory').onclick=()=>{$('agentDialog').close();MeshMemory.open(binding,a.name);};
    $('agentTerminal').hidden=!binding;if(binding)$('agentTerminal').href='/agents/'+encodeURIComponent(binding)+'/terminal';
    $('agentDialog').showModal();
  }
  $('makeScrumMaster').onclick=()=>makeScrum(selected);
  function options(includeDefault=true){return (includeDefault?'<option value="">Scrum Master chooses</option>':'')+snapshot.agents.map(a=>`<option value="${esc(a.id)}">${esc(a.name)}${scrum(a)?' · Scrum Master':''}</option>`).join('');}
  function renderBoard(){
    if(draggedTask)return;
    const query=$('taskSearch').value.trim().toLowerCase(),filter=$('taskFilter').value;
    const tasks=snapshot.tasks.filter(t=>(!filter||t.assignee===filter)&&(!query||(t.title+' '+(t.description||'')).toLowerCase().includes(query)));
    $('officeBoard').innerHTML=Object.entries(stages).map(([key,label])=>{
      const rows=tasks.filter(t=>stage(t)===key).sort((a,b)=>(a.order??a.position??0)-(b.order??b.position??0)||(b.priority||0)-(a.priority||0));
      return `<section class="office-column" data-stage="${key}" aria-label="${label}" tabindex="0"><h3>${label}<span>${rows.length}</span></h3>${rows.map(t=>`<article class="mission-card ${key}" data-task="${esc(t.id)}" tabindex="0" role="button" aria-label="Open ${esc(t.title)}" draggable="${online&&!t.running}"><h4>${esc(t.title)}</h4><p>${esc(agentName(t.assignee))}</p>${(t.dependsOn||[]).some(id=>!snapshot.tasks.some(d=>d.id===id&&stage(d)==='done'))?'<p>Waiting on dependencies</p>':''}${key==='blocked'?'<p>Input or resolution needed</p>':''}<div class="task-card-meta"><span>${t.running?'● Working':esc(t.id.slice(-6))}</span><span>${(t.comments||[]).length} comments${t.priority?' · P'+esc(t.priority):''}</span></div></article>`).join('')||'<p class="empty-column">Drop a task here</p>'}</section>`;
    }).join('');
    $('officeBoard').querySelectorAll('[data-task]').forEach(card=>{
      card.onclick=()=>openTask(card.dataset.task);card.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();openTask(card.dataset.task);}};
      card.ondragstart=e=>{if(card.draggable===false){e.preventDefault();return;}draggedTask=card.dataset.task;e.dataTransfer.setData('text/plain',draggedTask);e.dataTransfer.effectAllowed='move';card.classList.add('dragging');};
      card.ondragend=()=>{draggedTask=null;renderBoard();};
    });
    $('officeBoard').querySelectorAll('[data-stage]').forEach(column=>{
      column.ondragover=e=>{if(!draggedTask)return;e.preventDefault();e.dataTransfer.dropEffect='move';column.classList.add('drag-over');};
      column.ondragleave=e=>{if(!column.contains(e.relatedTarget))column.classList.remove('drag-over');};
      column.ondrop=async e=>{e.preventDefault();const id=draggedTask;if(!id)return;const cards=[...column.querySelectorAll('[data-task]')].filter(c=>c.dataset.task!==id),index=cards.filter(c=>e.clientY>c.getBoundingClientRect().top+c.getBoundingClientRect().height/2).length;draggedTask=null;column.classList.remove('drag-over');await move(id,column.dataset.stage,index);};
    });
  }
  async function move(id,destination,index=0){
    try{if(destination==='working'){await start(id);}else{await api('task.move',{id,stage:destination,index});await refresh();}if(destination!=='working')say(`Task moved to ${stages[destination]}.`);}catch(e){say(e.message);await refresh();}
  }
  async function start(id){const result=await api('run',{id});say('Work queued with your Scrum Master.');await refresh();return result;}
  function fillTask(t){
    const f=$('taskEditForm');f.dataset.dirty='false';$('taskTitle').textContent=t.title;$('taskIdentity').textContent=`${t.id} · ${stages[stage(t)]}${t.running?' · active execution':''}`;
    f.elements.title.value=t.title;f.elements.description.value=t.description||'';f.elements.assignee.innerHTML=options();f.elements.assignee.value=t.assignee||'';f.elements.priority.value=t.priority||0;
    f.elements.dependsOn.innerHTML=snapshot.tasks.filter(x=>x.id!==t.id).map(x=>`<option value="${esc(x.id)}" ${(t.dependsOn||[]).includes(x.id)?'selected':''}>${esc(x.title)}</option>`).join('');
    for(const node of f.elements)node.disabled=!online||Boolean(t.running);
    $('taskStage').innerHTML=Object.entries(stages).map(([s,label])=>`<option value="${s}">${label}</option>`).join('');$('taskStage').value=stage(t);$('taskStage').disabled=!online||Boolean(t.running);$('moveTask').disabled=!online||Boolean(t.running);
    $('deleteTask').disabled=!online||Boolean(t.running);$('runTask').disabled=!online||Boolean(t.running)||snapshot.paused||!snapshot.runtimeReady||stage(t)==='done';
    const question=(t.humanQA||[]).filter(q=>!q.a).at(-1);$('taskQuestion').hidden=!question;$('taskQuestionText').textContent=question?.q||'';
    $('taskResult').hidden=!t.result;$('taskResult').querySelector('pre').textContent=t.result||'';
    $('taskComments').innerHTML=(t.comments||[]).map(c=>`<li><strong>${esc(c.author||'Agent')}</strong><small>${esc(c.createdAt?new Date(c.createdAt).toLocaleString():'')}${c.kind?' · '+esc(c.kind):''}</small>${esc(c.text)}</li>`).join('')||'<li class="muted">No comments yet. Context stays with this task.</li>';
  }
  function openTask(id){const t=snapshot.tasks.find(t=>t.id===id);if(!t)return;taskId=id;fillTask(t);$('taskError').textContent='';$('taskDialog').showModal();}
  async function taskMutation(operation,args,after){
    const id=taskId,generation=epoch;
    try{await api(operation,{id,...args});if(after)await after(id);await refresh();const t=snapshot.tasks.find(t=>t.id===id);if(t&&id===taskId&&generation===epoch)fillTask(t);$('taskError').textContent='';}catch(e){$('taskError').textContent=e.message;}
  }
  $('taskEditForm').oninput=()=>{$('taskEditForm').dataset.dirty='true';};
  $('taskEditForm').onsubmit=e=>{e.preventDefault();const f=e.target;taskMutation('task.update',{title:f.elements.title.value,description:f.elements.description.value,assignee:f.elements.assignee.value,dependsOn:[...f.elements.dependsOn.selectedOptions].map(o=>o.value),priority:Number(f.elements.priority.value)});};
  $('moveTask').onclick=async()=>{await move(taskId,$('taskStage').value);const t=snapshot.tasks.find(t=>t.id===taskId);if(t)fillTask(t);};
  $('runTask').onclick=()=>taskMutation('run',{});
  $('taskCommentForm').onsubmit=async e=>{e.preventDefault();const text=e.target.elements.text.value;await taskMutation('task.comment',{text});if(!$('taskError').textContent)e.target.reset();};
  $('taskAnswerForm').onsubmit=e=>{e.preventDefault();taskMutation('task.approve',{answer:e.target.elements.answer.value},id=>snapshot.paused?Promise.resolve():start(id));};
  $('deleteTask').onclick=async()=>{if(!confirm('Delete this task? Its removal is recorded in the host activity history.'))return;try{await api('task.delete',{id:taskId});$('taskDialog').close();taskId=null;await refresh();}catch(e){$('taskError').textContent=e.message;}};
  $('taskSearch').oninput=renderBoard;$('taskFilter').onchange=renderBoard;
  $('openMission').onclick=()=>{const f=$('missionForm');f.elements.assignee.innerHTML=options();f.elements.dependsOn.innerHTML=snapshot.tasks.filter(t=>stage(t)!=='done').map(t=>`<option value="${esc(t.id)}">${esc(t.title)}</option>`).join('');f.querySelector('.dialog-error').textContent='';$('missionDialog').showModal();};
  $('missionForm').onsubmit=async e=>{
    e.preventDefault();const f=e.target,button=f.querySelector('[type=submit]'),requestEpoch=epoch;button.disabled=true;
    let created=null;
    try{const files=[...$('missionFormFiles').files],references=files.length?await FactoryFiles.attach(host(),files,text=>$('missionFormFileStatus').textContent=text):[];if(requestEpoch!==epoch)throw Error('Gateway changed; task was not created.');const result=await api('task.create',{title:f.elements.title.value,description:FactoryFiles.brief(f.elements.description.value,references),assignee:f.elements.assignee.value,dependsOn:[...f.elements.dependsOn.selectedOptions].map(o=>o.value),needsApproval:f.elements.needsApproval.checked});created=result.result?.id||result.id;const canStart=!f.elements.needsApproval.checked&&!snapshot.paused&&snapshot.runtimeReady;f.reset();$('missionDialog').close();await refresh();if(canStart&&created)await start(created);else say('Task added to Intake.');}
    catch(error){if(created){say('Task created; execution is waiting: '+error.message);await refresh();}else f.querySelector('.dialog-error').textContent=error.message;}finally{button.disabled=false;}
  };
  async function refresh(){
    if(pending || !host())return;pending=true;const requestEpoch=epoch;
    try{const [result,response]=await Promise.all([api('snapshot'),fetch('/api/status')]);if(!response.ok)throw Error('Fleet status unavailable.');const status=await response.json();if(requestEpoch!==epoch)return;fleet=status.agents||[];snapshot=MeshRuntime.unifiedOffice(result.snapshot,fleet,host());online=true;
      $('officeSignal').classList.add('online');for(const id of ['openMission','officePause','saveOfficeSettings'])$(id).disabled=false;$('officePause').textContent=snapshot.paused?'Resume work':'Pause work';
      if(document.activeElement!==$('maxIterations'))$('maxIterations').value=snapshot.maxIterations;
      $('officeRuntimeNotice').textContent=MeshRuntime.officeReadinessNotice(snapshot);
      const filter=$('taskFilter').value;$('taskFilter').innerHTML='<option value="">All agents</option>'+options(false);$('taskFilter').value=filter;
      renderFloor();renderBoard();say(snapshot.paused?'Work paused · your board remains available':'Connected · tasks and agent state come from your gateway');
      if($('taskDialog').open && $('taskEditForm').dataset.dirty!=='true' && !$('taskDialog').contains(document.activeElement?.closest('input,textarea,select'))) {const current=snapshot.tasks.find(t=>t.id===taskId);if(current)fillTask(current);}
      if($('taskDialog').open && !snapshot.tasks.some(t=>t.id===taskId)){$('taskDialog').close();taskId=null;}
    }catch(e){if(requestEpoch!==epoch)return;online=false;$('officeSignal').classList.remove('online');for(const id of ['openMission','officePause','saveOfficeSettings'])$(id).disabled=true;say(e.message);}
    finally{pending=false;}
  }
  async function loadShared(){
    if(sharedPending||!host())return;sharedPending=true;const requestEpoch=epoch;
    try{const result=await MeshRuntime.request(host(),'handoff.list');if(requestEpoch!==epoch)return;chatter=result.chatter;chatterTab.observe(host(),chatter);const own=chatterTab.owns(host(),chatter);$('officeChatter').checked=own;
      for(const id of ['chatterConcurrency','chatterGroup'])$(id).disabled=!own;$('chatterMinutes').readOnly=!own;
      if(document.activeElement!==$('chatterMinutes'))$('chatterMinutes').value=chatter?.session_minutes||15;if(document.activeElement!==$('chatterConcurrency'))$('chatterConcurrency').value=chatter?.max_conversations||1;$('chatterGroup').checked=Boolean(chatter?.experimental_group_chat);
      renderChatter();renderLinks();
    }catch(e){if(requestEpoch===epoch)$('chatterNotice').textContent=e.message;}finally{sharedPending=false;}
  }
  function renderChatter(){
    const enabled=Boolean(chatter?.enabled),feed=$('chatterFeed');feed.hidden=!enabled;
    $('chatterNotice').textContent=enabled?`${chatterTab.owns(host(),chatter)?'Chatter on in this tab':'Chatter on in another tab'} · Idle agents only. ${chatter.admission||'Waiting for available agents.'} Leaving the controlling tab turns chatter off.`:'Chatter is off. Turn it on to see the team’s live conversation.';
    if(!enabled){feed.replaceChildren();sharedSignature='';return;}
    const rows=(chatter.conversations||[]).flatMap(c=>(c.messages||[]).map(m=>({agent:m.agent,text:m.text,time:m.created||m.at||c.created})));const signature=JSON.stringify(rows);if(signature===sharedSignature)return;sharedSignature=signature;
    const follow=feed.scrollHeight-feed.scrollTop-feed.clientHeight<50;
    feed.innerHTML=rows.map(m=>`<div class="chatter-line"><time>${esc(m.time?new Date(typeof m.time==='number'?m.time*1000:m.time).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}):'Live')}</time><strong>${esc(m.agent)}</strong><span>${esc(m.text)}</span></div>`).join('')||'<p class="muted">Waiting for idle agents to begin a conversation…</p>';if(follow)feed.scrollTop=feed.scrollHeight;
  }
  $('officeChatter').onchange=async()=>{const b=$('officeChatter'),enabled=b.checked;b.disabled=true;try{await chatterTab.configure(host(),{enabled});await loadShared();}catch(e){b.checked=!enabled;say(e.message);}finally{b.disabled=false;}};
  for(const id of ['chatterMinutes','chatterConcurrency','chatterGroup'])$(id).onchange=async()=>{if(!chatterTab.owns(host(),chatter)||!$('chatterMinutes').reportValidity()||!$('chatterConcurrency').reportValidity())return;try{await chatterTab.configure(host(),{enabled:true,session_minutes:Number($('chatterMinutes').value),max_conversations:Number($('chatterConcurrency').value),experimental_group_chat:$('chatterGroup').checked});await loadShared();}catch(e){say(e.message);await loadShared();}};
  async function loadArtifacts(){const requestEpoch=epoch;$('artifactStatus').textContent='Loading published files…';try{const result=await MeshRuntime.request(host(),'files.list');if(requestEpoch!==epoch)return;artifacts=result.files||[];renderArtifacts();$('artifactStatus').textContent='Published files from your connected host.';}catch(e){$('artifactStatus').textContent=e.message;}}
  function renderArtifacts(){const query=$('artifactSearch').value.toLowerCase();$('artifactItems').innerHTML=artifacts.filter(f=>(f.name+' '+f.producer).toLowerCase().includes(query)).map(f=>`<li><strong>${esc(f.name)}</strong><p>${esc(f.producer)} · ${(f.size/1024).toFixed(1)} KB</p><button data-file="${esc(f.id)}" ${!f.downloadable?'disabled':''}>Download</button></li>`).join('')||'<li>No matching artifacts.</li>';$('artifactItems').querySelectorAll('[data-file]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await FactoryFiles.download(host(),artifacts.find(f=>f.id===b.dataset.file),false);}catch(e){$('artifactStatus').textContent=e.message;}finally{b.disabled=false;}});}
  $('openArtifacts').onclick=()=>{$('artifactDialog').showModal();loadArtifacts();};$('artifactRefresh').onclick=loadArtifacts;$('artifactSearch').oninput=renderArtifacts;
  $('officePause').onclick=async()=>{try{await api('pause',{paused:!snapshot.paused});await refresh();}catch(e){say(e.message);}};
  $('saveOfficeSettings').onclick=async()=>{if(!$('maxIterations').reportValidity())return;try{await api('settings',{maxIterations:Number($('maxIterations').value)});await refresh();}catch(e){say(e.message);}};
  $('officeRefresh').onclick=()=>{refresh();loadShared();};
  $('zoomIn').onclick=()=>{zoom=Math.min(1.8,zoom+.15);fit();};$('zoomOut').onclick=()=>{zoom=Math.max(.6,zoom-.15);fit();};$('zoomReset').onclick=()=>{zoom=1;fit();};new ResizeObserver(fit).observe($('officeFloor'));
  document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>b.closest('dialog').close());
  function restoreLayout(){try{positions=JSON.parse(sessionStorage.getItem('mesh-office-layout:'+host())||'{}');for(const [id,p] of Object.entries(positions))if(!p||!Number.isFinite(p.x)||!Number.isFinite(p.y)||p.x<80||p.x>920||p.y<90||p.y>620)delete positions[id];}catch{positions={};}}
  $('officeHost').onchange=()=>{chatterTab.release();epoch++;snapshot=null;fleet=[];chatter=null;online=false;selected=null;taskId=null;positions={};sharedSignature='';for(const d of document.querySelectorAll('dialog[open]'))d.close();$('floorNodes').replaceChildren();$('floorLinks').replaceChildren();$('officeBoard').replaceChildren();$('floorEmpty').hidden=false;restoreLayout();renderChatter();refresh();loadShared();};
  restoreLayout();refresh();loadShared();const timer=setInterval(refresh,4000),sharedTimer=setInterval(loadShared,5000);window.addEventListener('pagehide',()=>{clearInterval(timer);clearInterval(sharedTimer);});
})();
