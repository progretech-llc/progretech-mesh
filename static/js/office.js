(() => {
  const $ = id => document.getElementById(id);
  const escape = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let snapshot = null, selected = null, positions = {}, manualPositions = {}, zoom = 1, pending = false, online = false, hostEpoch = 0;
  let basePositions={}, selectedLink=null, fleet=[], runtimeState=null, powerBusy=false, mailboxEpoch=0, artifacts=[], chatter=null, handoffs=[], lastProximityCheck=0;
  const conversations=new Map();
  const host = () => $('officeHost').value;
  const say = text => { $('officeStatus').textContent = text; };
  const legend=document.querySelector('.floor-legend');
  if(legend)legend.innerHTML='<span class="cyan">Director ring</span><span class="blue">Working</span><span class="green">Idle</span><span class="gray">Sleeping / offline</span><span class="pink">Needs you</span><span class="red">Error</span><span>··· chatter</span><span>— agents working together</span>';
  const activeChatterStates=new Set(['queued','approaching','first','second','third','reply_wait']);
  const pairCooldown=new Map();
  function officeRow(id) {
    const office=snapshot?.agents.find(a=>a.id===id);
    return office?.native || snapshot?.factoryAgents?.find(a=>'factory-'+a.id===id) || null;
  }
  function runtimeRole(id) { return officeRow(id)?.runtime_id || officeRow(id)?.id || null; }
  function fleetBinding(id) {
    const role=runtimeRole(id);
    return fleet.find(a=>(a.control_center_gateway===host() || a.id===host()) && a.runtime_id===role)?.id || null;
  }
  function chatterEligible(id) {
    const row=officeRow(id);if(!row)return false;
    const binding=fleetBinding(id);
    // The parent gateway/director is not a chatter participant, and legacy
    // office nodes without an exact signed runtime binding must not reach the
    // stricter host-side pair validator.
    if(!binding || !binding.startsWith(host()+'--'))return false;
    const state=MeshRuntime.indicator(row).state;
    return state==='idle' && row.sleeping!==true && !(chatter?.conversations||[]).some(c=>activeChatterStates.has(c.state)&&[c.a_role,c.b_role,c.c_role].includes(runtimeRole(id)));
  }
  async function api(operation, args = {}) {
    if (!host()) throw Error('Connect a personally hosted agent to open an office.');
    const response = await fetch(`/api/agents/${encodeURIComponent(host())}/office`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({operation,args})});
    const data = await response.json();
    if (!response.ok || !data.ok) throw Error(data.error || 'Office unavailable');
    return data.result;
  }
  function fit() {
    const floor = $('officeFloor');
    const scale = Math.min(floor.clientWidth / 1000, floor.clientHeight / 700) * zoom;
    $('floorWorld').style.setProperty('--node-scale', Math.min(2.1, Math.max(1, .7/scale)));
    $('floorWorld').style.transform = `translate(${(floor.clientWidth - 1000 * scale)/2}px,${(floor.clientHeight - 700 * scale)/2}px) scale(${scale})`;
  }
  function arrange() {
    const workers = snapshot.agents.filter(a => !a.isDirector);
    snapshot.agents.forEach(a => {
      const manual=manualPositions[a.id];
      if (manual && Number.isFinite(manual.x) && Number.isFinite(manual.y) && manual.x >= 80 && manual.x <= 920 && manual.y >= 90 && manual.y <= 600) { positions[a.id]={...manual}; basePositions[a.id]={...manual}; return; }
      if (a.isDirector) basePositions[a.id] = {x:500,y:(snapshot.factoryAgents?.length ? 220 : 300)};
      else { const angle = 2*Math.PI*workers.findIndex(x => x.id===a.id)/Math.max(workers.length,1)-Math.PI/2; basePositions[a.id] = {x:500+310*Math.cos(angle),y:(snapshot.factoryAgents?.length ? 220+130*Math.sin(angle) : 340+225*Math.sin(angle))}; }
      if (!positions[a.id]) positions[a.id]={...basePositions[a.id]};
    });
  }
  function renderFloor() {
    arrange();
    $('floorEmpty').hidden = snapshot.agents.length + (snapshot.factoryAgents?.length || 0) > 0;
    const note=document.querySelector('.floor-footnote');if(note)note.hidden=Boolean(snapshot.factoryAgents?.length);
    const live=(snapshot.factoryAgents || []).map(a => ({...a,name:a.name || a.id[0].toUpperCase()+a.id.slice(1),role:a.role||'Live OpenClaw role',id:'factory-'+a.id,isDirector:false,factoryObserved:true}));
    const display=[...snapshot.agents,...live];
    const liveRows=Math.ceil(live.length/4),rowGap=Math.min(115,250/Math.max(1,liveRows-1)),firstRow=Math.min(505,620-rowGap*(liveRows-1));
    live.forEach((a,i)=>{basePositions[a.id]={x:140+(i%4)*240,y:firstRow+Math.floor(i/4)*rowGap};positions[a.id]=manualPositions[a.id] || positions[a.id] || {...basePositions[a.id]};});
    const visible=new Set(display.map(a=>a.id));
    for(const id of Object.keys(positions))if(!visible.has(id)){delete positions[id];delete basePositions[id];}
    const markup = display.map(a => {
      const blocked = snapshot.tasks.some(t => t.assignee===a.id && t.status==='blocked');
      const indicator=a.native?MeshRuntime.indicator(a.native):a.factoryObserved?MeshRuntime.indicator(a):null;
      const state = indicator?indicator.state:blocked?'blocked':a.state;
      const p = positions[a.id];
      const work=indicator?.state==='busy'?MeshRuntime.workLabel(a.native||a):a.role;
      return `<button class="floor-node ${a.isDirector?'director':''} ${state==='active'?'working':escape(state)} ${a.id===selected?'selected':''}" data-agent="${escape(a.id)}" ${a.factoryObserved?'data-factory-role="'+escape(a.id.slice(8))+'"':''} style="left:${p.x}px;top:${p.y}px" title="${escape(indicator?.detail||a.role)}" aria-label="${escape(a.name)}, ${escape(a.role)}, ${escape(indicator?.detail||state)}"><span class="node-orb">${MeshAvatar.source(a)?`<img src="${MeshAvatar.source(a)}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%">`:a.isDirector?'◈':escape(a.name.slice(0,2).toUpperCase())}</span><span class="node-state" aria-hidden="true"></span><span class="node-name">${escape(a.name)} · ${escape(indicator?.label||state)}</span><span class="node-role">${escape(work)}</span></button>`;
    }).join('');
    // Preserve live nodes, focus, pointer capture and CSS animation timelines.
    // Polling updates metadata, rather than resetting the animated coordinates.
    const container=$('floorNodes'),template=document.createElement('template');template.innerHTML=markup;
    const previous=new Map([...container.children].map(node=>[node.dataset.agent,node]));
    [...template.content.children].forEach((next,index)=>{
      let node=previous.get(next.dataset.agent);
      if(node){for(const attr of next.attributes)if(node.getAttribute(attr.name)!==attr.value)node.setAttribute(attr.name,attr.value);if(node.innerHTML!==next.innerHTML)node.innerHTML=next.innerHTML;}
      else node=next;
      if(container.children[index]!==node)container.insertBefore(node,container.children[index]||null);
      previous.delete(node.dataset.agent);
    });
    for(const node of previous.values())node.remove();
    $('floorNodes').querySelectorAll('[data-agent]').forEach(node => {
      node.onclick = () => { if (node.dataset.dragged==='true') {node.dataset.dragged='false'; return;} selected=node.dataset.agent;selectedLink=null;runtimeState=null; renderInspector(); renderFloor(); if(node.dataset.factoryRole || snapshot.agents.find(a=>a.id===selected)?.native)loadRuntime();loadMailbox(); };
      node.onpointerdown = e => {
        if(e.button!==0)return;
        const start={x:e.clientX,y:e.clientY},id=node.dataset.agent,original={...positions[id]};
        const scale=Math.min($('officeFloor').clientWidth/1000,$('officeFloor').clientHeight/700)*zoom;
        node.setPointerCapture(e.pointerId);
        node.onpointermove = move => {if(Math.hypot(move.clientX-start.x,move.clientY-start.y)<4)return;node.dataset.dragged='true';manualPositions[id]=positions[id]={x:Math.max(80,Math.min(920,original.x+(move.clientX-start.x)/scale)),y:Math.max(90,Math.min(600,original.y+(move.clientY-start.y)/scale))};node.style.left=positions[id].x+'px';node.style.top=positions[id].y+'px';renderLinks();};
        node.onpointerup=()=>{node.onpointermove=null;if(node.dataset.dragged!=='true')return;try{manualPositions[id]={...positions[id]};sessionStorage.setItem('mesh-office-layout:'+host(),JSON.stringify(manualPositions));}catch{};if(chatter?.enabled&&chatterEligible(id)){const near=Object.keys(positions).filter(other=>other!==id&&chatterEligible(other)).map(other=>({id:other,d:Math.hypot(positions[other].x-positions[id].x,positions[other].y-positions[id].y)})).sort((a,b)=>a.d-b.d)[0];if(near&&near.d<90)requestPair(id,near.id);}};
      };
    });
    renderLinks(); fit();if(chatter)renderShared();
  }
  async function requestPair(a,b){
    const epoch=hostEpoch;
    if(!chatterEligible(a)||!chatterEligible(b)){say('Working or sleeping agents stay on their current work; chatter will wait for two idle agents.');return;}
    const key=[a,b].sort().join('|'),now=Date.now();if(now-(pairCooldown.get(key)||0)<60000)return;pairCooldown.set(key,now);
    const first=fleetBinding(a),second=fleetBinding(b);
    if(!first||!second||first===second||!first.startsWith(host()+'--')||!second.startsWith(host()+'--')){say('Choose two different signed team agents for chatter.');return;}
    try{await MeshRuntime.request(host(),'chatter.pair',{a:first,b:second,topic:''});if(epoch!==hostEpoch)return;manualPositions[a]=positions[a]={x:Math.max(80,Math.min(920,positions[b].x+(positions[b].x>800?-110:110))),y:positions[b].y};try{sessionStorage.setItem('mesh-office-layout:'+host(),JSON.stringify(manualPositions));}catch{}say('Conversation requested; the configured timer and concurrency limit remain authoritative.');await loadShared();await refresh();}catch(e){pairCooldown.delete(key);if(epoch===hostEpoch)say(e.message);}
  }
  function geometry(link,t=0) {
    const a=positions[link.from],b=positions[link.to];if(!a||!b)return '';
    const dx=b.x-a.x,dy=b.y-a.y,length=Math.hypot(dx,dy)||1;
    if(link.kind==='instruction')return `M${a.x} ${a.y-20} L${b.x} ${b.y-20}`;
    let d=`M${a.x} ${a.y-20}`;
    for(let i=1;i<=36;i++){const u=i/36,wiggle=Math.sin(u*Math.PI*8+t)*7*Math.sin(Math.PI*u);d+=` L${a.x+dx*u-dy/length*wiggle} ${a.y-20+dy*u+dx/length*wiggle}`;}
    return d;
  }
  function showInteraction(link) {
    selectedLink=link.id;
    const panel=$('interactionDetails');if(panel.dataset.link===link.id&&panel.contains(document.activeElement))return;panel.dataset.link=link.id;panel.hidden=false;
    const names=id=>snapshot.agents.find(a=>a.id===id)?.name || id.replace('factory-','');
    panel.innerHTML=`<h3>${link.kind==='instruction'?'Instruction / handoff':link.kind==='conversation'?'Office chatter':'Shared task'}</h3><p>${escape(link.title)}${link.task_id?'<br>'+escape(link.task_id):''}</p><p>${escape(names(link.from))}${link.kind==='instruction'?' → ':' ↔ '}${escape(names(link.to))}</p>${[link.from,link.to].map(id=>`<p><strong>${escape(names(id))}</strong><br>${escape(link.parts?.[id] || 'Specific task part not reported.')}</p>`).join('')}<p>${escape(link.source || 'Recorded activity')}</p>${link.topic_editable?'<form id="chatterTopicForm"><label>Conversation topic<input id="chatterTopic" maxlength="200" value="'+escape(link.title)+'"></label><button type="submit">Set topic for next turn</button></form>':''}`;
    const form=$('chatterTopicForm');if(form)form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button');button.disabled=true;try{await MeshRuntime.request(host(),'chatter.topic',{id:link.chatter_id,topic:$('chatterTopic').value});say('Topic saved for the next chatter turn.');await loadShared();}catch(error){say(error.message);}finally{button.disabled=false;}};
  }
  function renderLinks() {
    const links=snapshot.interactions || [];
    $('floorLinks').innerHTML='<defs><marker id="instructionArrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7" fill="#62d6ed"/></marker></defs>'+links.filter(l=>positions[l.from]&&positions[l.to]).map(l=>`<path tabindex="0" role="button" aria-label="${escape(l.kind+': '+l.title)}" data-interaction="${escape(l.id)}" class="floor-link ${l.kind==='instruction'?'instruction':l.kind==='conversation'?'conversation':'collaboration'}" ${l.kind==='instruction'?'marker-end="url(#instructionArrow)"':''} d="${geometry(l)}"><title>${escape(l.title)}</title></path>`).join('');
    $('floorLinks').querySelectorAll('[data-interaction]').forEach(path=>{
      const open=()=>showInteraction(links.find(l=>l.id===path.dataset.interaction));path.onclick=open;
      path.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();open();}};
    });
    if(selectedLink){const link=links.find(l=>l.id===selectedLink);if(link)showInteraction(link);else{$('interactionDetails').hidden=true;selectedLink=null;}}
    else $('interactionDetails').hidden=true;
  }
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
  let animation;
  function float(time) {
    if(snapshot && !document.hidden && !reduced.matches) {
      $('floorNodes').querySelectorAll('[data-agent]').forEach((node,i)=>{
        const id=node.dataset.agent,p=basePositions[id];if(!p || manualPositions[id] || node.matches(':focus,:hover'))return;
        const meeting=(chatter?.conversations||[]).find(c=>['approaching','first','second','third','reply_wait'].includes(c.state) && [c.a_role,c.b_role,c.c_role].includes(id.slice(8)));const meetingIndex=meeting?(chatter.conversations||[]).filter(c=>['approaching','first','second','third','reply_wait'].includes(c.state)).indexOf(meeting):0;const participantIndex=meeting?[meeting.a_role,meeting.b_role,meeting.c_role].indexOf(id.slice(8)):0;const q=meeting?{x:260+(meetingIndex%2)*420+(participantIndex-1)*75,y:360+Math.floor(meetingIndex/2)*160}:p;const target={x:q.x+Math.sin(time/5400+i*1.7)*(meeting?10:40),y:q.y+Math.cos(time/6200+i*1.7)*(meeting?7:25)},current=positions[id]||p;positions[id]={x:current.x+(target.x-current.x)*.04,y:current.y+(target.y-current.y)*.04};
        node.style.left=positions[id].x+'px';node.style.top=positions[id].y+'px';
      });
      const links=snapshot.interactions||[];
      $('floorLinks').querySelectorAll('[data-interaction]').forEach(path=>{const l=links.find(l=>l.id===path.dataset.interaction);if(l)path.setAttribute('d',geometry(l,time/900));});
      if(chatter?.enabled && time-lastProximityCheck>5000){
        lastProximityCheck=time;
        const ids=Object.keys(positions).filter(chatterEligible);
        let nearest=null;
        for(let i=0;i<ids.length;i++)for(let j=i+1;j<ids.length;j++){
          const d=Math.hypot(positions[ids[i]].x-positions[ids[j]].x,positions[ids[i]].y-positions[ids[j]].y);
          if(d<90 && (!nearest || d<nearest.d))nearest={a:ids[i],b:ids[j],d};
        }
        if(nearest)requestPair(nearest.a,nearest.b);
      }
    }
    animation=requestAnimationFrame(float);
  }
  animation=requestAnimationFrame(float);
  function renderInspector() {
    const officeAgent=snapshot?.agents.find(a=>a.id===selected);
    const live=officeAgent?.native || snapshot?.factoryAgents?.find(a=>'factory-'+a.id===selected);
    const a=officeAgent || (live ? {...live,name:live.name||live.id,role:live.role||'Local agent'} : null);
    $('factoryChat').hidden=!live;
    let tracking=$('factorySpeckletToggle');if(!tracking){const label=document.createElement('label');tracking=document.createElement('input');tracking.type='checkbox';tracking.id='factorySpeckletToggle';label.append(tracking,document.createTextNode(' Use Specklet'));$('factoryMemoryStatus').after(label);tracking.onchange=async()=>{const aid=selectedRuntime(),selection=selected,wanted=tracking.checked;if(!aid)return;tracking.disabled=true;try{const r=await fetch('/api/agents/'+encodeURIComponent(aid)+'/management',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'specklet.toggle',args:{enabled:wanted}})});const d=await r.json();if(!r.ok||!d.ok)throw Error(d.error||'Specklet unavailable');if(selected===selection){runtimeState={...(runtimeState||{}),specklet_enabled:d.result.enabled};say(d.result.enabled?'Specklet enabled':'Specklet off; board retained');}}catch(e){if(selected===selection){tracking.checked=!wanted;say(e.message);}}finally{tracking.disabled=false;}};}tracking.parentElement.hidden=!live;tracking.checked=Boolean(runtimeState?.specklet_enabled);
    let taskButton=$('factoryTaskBoard');if(!taskButton){taskButton=document.createElement('a');taskButton.id='factoryTaskBoard';taskButton.textContent='Task Board';$('factoryMemoryStatus').after(taskButton);}taskButton.hidden=!live;const boardAgent=selectedRuntime();taskButton.href=boardAgent?'/agents/'+encodeURIComponent(boardAgent)+'/task-board':'#';
    let memoryButton=$('factoryMemorySearch');if(!memoryButton){memoryButton=document.createElement('button');memoryButton.id='factoryMemorySearch';memoryButton.textContent='Memory search';$('factoryMemoryStatus').after(memoryButton);memoryButton.onclick=()=>{const aid=selectedRuntime();if(aid)MeshMemory.open(aid,$('inspectorName').textContent);else say('Select an enrolled agent to search its memory.');};}memoryButton.hidden=!live;
    $('officeMailbox').hidden=!officeAgent;
    if(live){renderConversation();$('factoryRecovery').hidden=!['error','warning'].includes(MeshRuntime.indicator(live).state);$('factoryRecovery').textContent=MeshRuntime.indicator(live).state==='warning'?'Check recovery options':'Try to resolve';const status=$('factoryRuntimeStatus');status.textContent=MeshRuntime.indicator(live).detail;status.className='runtime-status '+MeshRuntime.indicator(live).state;$('factoryMemoryStatus').textContent=MeshRuntime.memoryLabel(live.memory);}
    $('inspectorActions').hidden=!officeAgent;
    $('inspectorName').textContent=a?.name || 'Choose an agent';
    $('inspectorRole').textContent=a ? `${a.role} · ${live?MeshRuntime.indicator(live).label:a.state} · ${live ? (live.sleeping===true?'asleep':live.sleeping===false?'awake':'availability unknown') : a.pendingMessages+' mailbox messages'}` : 'Select a circle to follow its work and send guidance.';
    $('inspectorGoal').textContent=a?.goal || '';
    let directorButton=$('makeOrchestrator');
    if(!directorButton){directorButton=document.createElement('button');directorButton.id='makeOrchestrator';$('inspectorGoal').after(directorButton);directorButton.onclick=async()=>{directorButton.disabled=true;try{await api('orchestrator.set',{id:selected});await refresh();}catch(e){say(e.message);directorButton.disabled=false;}};}
    let terminal=$('officeTerminalView');if(!terminal){terminal=document.createElement('a');terminal.id='officeTerminalView';terminal.textContent='Terminal view';terminal.target='_blank';terminal.rel='noopener';directorButton.after(terminal);}terminal.hidden=!a;terminal.href='/agents/'+encodeURIComponent(selectedRuntime() || host())+'/terminal';
    directorButton.hidden=!officeAgent;directorButton.disabled=!online || Boolean(a?.isDirector);directorButton.textContent=a?.isDirector?'Orchestrator':'Make Orchestrator';
    $('agentWork').hidden=!a;
    if(a) {
      const tasks=!officeAgent && live ? (snapshot.workdayTasks||[]).filter(t=>t.role===live.id).sort((a,b)=>(a.day+' '+a.slot).localeCompare(b.day+' '+b.slot)) : snapshot.tasks.filter(t=>a.isDirector || t.assignee===a.id);
      $('agentAssignments').innerHTML=tasks.map(t=>`<li><strong>${escape(t.title||t.phase||t.id)}</strong><br>${escape(t.status||t.state)} · ${!officeAgent && live?'Scheduled '+escape(t.day)+' '+escape(t.slot):'Assigned to '+escape(snapshot.agents.find(a=>a.id===t.assignee)?.name||t.assignee||'unassigned')}${t.description?'<details><summary>Task brief</summary>'+escape(t.description)+'</details>':''}${t.dependsOn?.length?'<br>Depends on '+escape(t.dependsOn.join(', ')):''}</li>`).join('') || '<li>No recorded assignment. Mailbox context alone does not start a mission.</li>';
      const links=(snapshot.interactions||[]).filter(l=>l.from===selected || l.to===selected);
      const delegations=(snapshot.events||[]).filter(e=>e.kind==='delegation' && (e.agentId===selected||e.to===selected));
      $('agentPartners').innerHTML=links.map(l=>`<li>${escape(l.kind)} · ${escape((l.from===selected?l.to:l.from).replace('factory-',''))}<br>${escape(l.title)}${l.parts?.[selected]?'<br>My part: '+escape(l.parts[selected]):''}</li>`).join('')+delegations.slice(-8).map(e=>`<li>Delegation · ${escape(e.agentId)} → ${escape(e.to)}<br>${escape(e.summary||e.taskId||'')}</li>`).join('') || '<li>No recorded collaboration or delegation.</li>';
    }
    $('archiveWorker').disabled=!a || a.isDirector || !officeAgent || !online;
    $('officeActivity').innerHTML=(snapshot?.events || []).filter(e=>!selected||e.agentId===selected||e.from===selected||e.to===selected).slice(-10).reverse().map(e=>`<li>${escape(e.kind)}${e.summary?'<br>'+escape(e.summary):''}${e.taskId?'<br>'+escape(e.taskId):''}</li>`).join('') || (live ? `<li>${escape(live.state)}${live.task_id?'<br>'+escape(live.task_id):''}${live.last_result?.severity==='error'?'<br>Recorded failure: '+escape(live.last_result.code):''}</li>` : '<li>No recent activity.</li>');
    if(live)$('officeActivity').insertAdjacentHTML('afterbegin',`<li><strong>Current work</strong><br>${escape(MeshRuntime.workLabel(live))}</li>`);
    if(live)$('officeActivity').insertAdjacentHTML('afterbegin',`<li>${escape(MeshRuntime.indicator(live).detail)}</li>`);
    if(live && !powerBusy) {if(runtimeState)runtimeState.sleeping=live.sleeping;const asleep=live.sleeping;$('factoryPower').textContent=asleep?'Wake up':'Sleep';$('factoryPower').disabled=asleep===null || !online;$('factoryPowerStatus').textContent=asleep===null?'Availability unknown':asleep?'Asleep in Mesh and Factory':'Awake in Mesh and Factory';}
  }
  function renderBoard() {
    const labels={todo:'Queued',doing:'In progress',blocked:'Needs you',done:'Delivered'};
    $('officeBoard').innerHTML=Object.entries(labels).map(([state,label])=>{
      const tasks=snapshot.tasks.filter(t=>t.status===state).sort((a,b)=>(b.priority||0)-(a.priority||0));
      return `<div class="office-column" tabindex="0" role="region" aria-label="${label} missions"><h3>${label}<span>${tasks.length}</span></h3>${tasks.map(t=>{
        const dependencies=t.dependsOn.filter(id=>!snapshot.tasks.some(d=>d.id===id&&d.status==='done'));
        const assignee=snapshot.agents.find(a=>a.id===t.assignee)?.name || 'Director';
        return `<article class="mission-card ${state}"><strong>${escape(t.title)}</strong><p>${escape(assignee)}${dependencies.length?' · waiting on '+dependencies.length+' dependencies':''}</p><details><summary>Brief & result</summary><pre>${escape(t.description || '')}</pre>${t.result?'<pre>'+escape(t.result)+'</pre>':''}${(t.humanQA||[]).map(qa=>'<p>'+escape(qa.q)+(qa.a?'<br>'+escape(qa.a):'')+'</p>').join('')}</details>${state==='todo'?`<button data-run="${escape(t.id)}" ${!online||!snapshot.runtimeReady||snapshot.paused||dependencies.length||snapshot.agents.length<2?'disabled':''}>Start mission</button>`:state==='blocked'?`<button data-approve="${escape(t.id)}" ${!online?'disabled':''}>Approve & queue</button>`:''}</article>`;
      }).join('')||'<p class="muted">No missions</p>'}</div>`;
    }).join('');
    $('officeBoard').querySelectorAll('[data-run]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const result=await api('run',{id:b.dataset.run});say(`Mission queued · ${result.job_id}. Follow live activity on the floor.`);await refresh();}catch(e){say(e.message);b.disabled=false;}});
    $('officeBoard').querySelectorAll('[data-approve]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await api('task.approve',{id:b.dataset.approve,answer:'Approved by the office owner in Mesh.'});await refresh();}catch(e){say(e.message);b.disabled=false;}});
  }
  function render() {
    $('officeSignal').classList.toggle('online',online);
    for(const id of ['openHire','openMission','officePause','saveOfficeSettings'])$(id).disabled=!online;
    $('officePause').textContent=snapshot.paused?'Resume office':'Pause office';
    $('officeAgentCount').textContent=snapshot.agents.length+(snapshot.factoryAgents?.length||0);
    $('officeTaskCount').textContent=snapshot.tasks.filter(t=>t.status!=='done').length;
    $('officeMessageCount').textContent=snapshot.messages.length;
    $('officeRuntimeNotice').textContent=document.body.dataset.offline?snapshot.runtimeReady?'Your local GGUF model runs through the bundled inference engine. Linked workers can delegate to your imported agents. Pausing stops work at the next agent step.':'Choose a GGUF model in Mission Control to execute missions. You can hire workers and organize missions now.':snapshot.nativeRuntimeReady?'Missions run through the assigned connected OpenClaw role. Pausing stops work at the next agent step.':snapshot.runtimeReady?'CrewAI is configured on this host. Missions use its model and approved workspace. Pausing stops work at the next agent step.':'Connect the assigned native role or configure CrewAI before starting a mission.';
    if(document.activeElement!==$('maxIterations'))$('maxIterations').value=snapshot.maxIterations;
    const current=$('handoffSource').value;
    const sources=[...snapshot.agents.map(a=>a.native).filter(Boolean),...(snapshot.factoryAgents||[])].filter((a,i,all)=>a.id&&all.findIndex(row=>row.id===a.id)===i);
    $('handoffSource').innerHTML='<option value="">Send now</option>'+sources.map(a=>`<option value="${escape(a.id)}">${escape(a.name||a.id)}</option>`).join('');
    if(sources.some(a=>a.id===current))$('handoffSource').value=current;
    renderFloor();renderBoard();renderInspector();
  }
  function selectedRuntime() {
    const office=snapshot?.agents.find(a=>a.id===selected);
    if(office?.mesh_agent_id)return office.mesh_agent_id;
    const row=snapshot?.factoryAgents?.find(a=>'factory-'+a.id===selected);
    return fleet.find(a=>(a.control_center_gateway===host()||a.id===host()) && a.runtime_id===row?.runtime_id)?.id;
  }
  async function loadRuntime() {
    syncConversation();
    const id=selected;try{const response=await fetch('/api/status');const data=await response.json();fleet=data.agents||[];const aid=selectedRuntime();if(!aid)throw Error('Enroll this signed agent in the fleet to use live chat and wake controls.');const state=await MeshRuntime.request(aid,'runtime.status');if(selected===id){runtimeState=state;renderInspector();}}
    catch(e){if(selected===id){$('factoryPower').disabled=true;$('factoryPowerStatus').textContent=e.message;}}
  }
  const originAttachments=new Map();
  async function syncConversation() {
    const id=selected,aid=selectedRuntime();if(!aid || $('factoryMessage').querySelector('button').disabled)return;
    try{const feed=await MeshRuntime.history(aid);if(selected!==id || !feed.enabled || $('factoryMessage').querySelector('button').disabled)return;
      conversations.set(id,feed.events.map(m=>({sender:(m.speaker==='user'?'You':m.agent)+' · '+m.origin,text:m.text,files:originAttachments.get(m.seq)||[],error:m.speaker==='status'})));renderConversation();
    }catch{/* Existing history remains visible on a disconnect. */}
  }
  function renderConversation() {
    $('factoryConversation').innerHTML=(conversations.get(selected)||[]).map(m=>`<li class="${m.error?'chat-error':''}"><strong>${escape(m.sender)}</strong><br>${escape(m.text)}</li>`).join('') || '<li>No synchronized conversation yet.</li>';
    [...$('factoryConversation').children].forEach((node,i)=>FactoryFiles.links(node,selectedRuntime(),(conversations.get(selected)||[])[i]?.files));
  }
  $('handoffSource').onchange=()=>{$('factoryMessage').querySelector('button').textContent=$('handoffSource').value?'Queue conditional instruction':'Send chat';};
  $('factoryMessage').onsubmit=async e=>{
    e.preventDefault();const aid=selectedRuntime(),id=selected,epoch=hostEpoch;if(!aid){say('Enroll this role in the fleet first.');return;}
    const original=e.target.elements.text.value.trim(),files=[...$('factoryMessageFiles').files],source=$('handoffSource').value;if(!original && !files.length)return;
    const button=e.target.querySelector('button');button.disabled=true;let text;
    try{text=FactoryFiles.brief(original,await FactoryFiles.attach(aid,files,n=>$('factoryMessageFileStatus').textContent=n));}
    catch(error){say(error.message);button.disabled=false;return;}
    if(epoch!==hostEpoch){say('Execution host changed; prompt was not sent.');button.disabled=false;return;}
    if(source){try{const rule=await MeshRuntime.request(aid,'handoff.create',{source,text});say(rule.note);if(selected===id)e.target.reset();await loadShared();}catch(error){say(error.message);}finally{button.disabled=false;}return;}
    const rows=conversations.get(id)||[];conversations.set(id,rows);rows.push({sender:'You',text});const reply={sender:snapshot.agents.find(a=>a.id===id)?.name || id.slice(8),text:'Requesting host…'};rows.push(reply);if(rows.length>80)rows.splice(0,rows.length-80);if(selected===id){e.target.reset();renderConversation();}
    try{const result=await MeshRuntime.run(aid,'communication.start',{text},job=>{reply.text=job.detail;if(selected===id)renderConversation();});reply.text=result.reply;reply.files=result.attachments||[];if(result.sync_event_id)originAttachments.set(result.sync_event_id,reply.files);}
    catch(e){reply.text=e.message;reply.error=true;}
    button.disabled=false;if(selected===id)renderConversation();refresh();
  };
  $('factoryRecovery').onclick=async()=>{
    const id=selected,aid=selectedRuntime();if(!aid)return;
    const rows=conversations.get(id)||[];conversations.set(id,rows);const report={sender:'Host recovery',text:'Checking recovery options…'};rows.push(report);const button=$('factoryRecovery');button.disabled=true;renderConversation();
    try{report.text=await MeshRuntime.recover(aid,job=>{report.text=job.detail;if(selected===id)renderConversation();});}
    catch(e){report.text=e.message;report.error=true;}finally{button.disabled=false;if(selected===id)renderConversation();refresh();}
  };
  $('factoryActiveContext').onclick=async()=>{
    const id=selected,aid=selectedRuntime(),input=$('factoryMessage').elements.text,text=input.value.trim();if(!aid || !text){say('Enter the context to add to this agent’s active work.');return;}
    const button=$('factoryActiveContext');button.disabled=true;
    try{const attached=FactoryFiles.brief(text,await FactoryFiles.attach(aid,[...$('factoryMessageFiles').files],n=>$('factoryMessageFileStatus').textContent=n));const receipt=await MeshRuntime.request(aid,'runtime.context',{text:attached});const rows=conversations.get(id)||[];conversations.set(id,rows);rows.push({sender:'You · active work context',text},{sender:'Host delivery receipt',text:receipt.note});if(selected===id){input.value='';$('factoryMessageFiles').value='';renderConversation();}}
    catch(e){say(e.message);}finally{button.disabled=false;}
  };
  $('factoryPower').onclick=async()=>{
    const aid=selectedRuntime(),id=selected;if(!aid)return;powerBusy=true;$('factoryPower').disabled=true;
    try{const state=await MeshRuntime.run(aid,(snapshot.agents.find(a=>a.id===id)?.native || snapshot.factoryAgents.find(a=>'factory-'+a.id===id))?.sleeping?'runtime.wake':'runtime.sleep',{},j=>{if(selected===id)$('factoryPowerStatus').textContent=j.detail;});if(selected===id)runtimeState=state;}
    catch(e){say(e.message);}finally{powerBusy=false;refresh();}
  };
  for(const action of ['pause','resume'])$('factory'+(action==='pause'?'Pause':'Resume')).onclick=async()=>{
    const id=selected,row=snapshot.agents.find(a=>a.id===id)?.native || snapshot.factoryAgents.find(a=>'factory-'+a.id===id);if(!row)return;
    try{await api('workday.control',{action,role:row.id,duration:'1s'});await refresh();say(action==='pause'?'Activity paused across Mesh and Factory. Active work was asked to stop; completed actions remain.':'Activity resumed across Mesh and Factory. Interrupted work remains visible for review.');}catch(e){say(e.message);}
  };
  $('factoryWorkSummary').onclick=async()=>{
    try{const id=selected,r=await MeshRuntime.request(selectedRuntime(),'runtime.snapshot',{kind:'task'});const rows=conversations.get(id)||[];conversations.set(id,rows);rows.push({sender:'Host status summary',text:r.lines.join('\n')});if(selected===id)renderConversation();}catch(e){say(e.message);}
  };
  $('factoryNewChat').onclick=async()=>{try{await MeshRuntime.request(selectedRuntime(),'communication.new');say('New conversation ready; previous runtime history is preserved.');}catch(e){say(e.message);}};
  for(const kind of ['Task','Terminal'])$('factory'+kind+'Snapshot').onclick=async()=>{
    const id=selected;try{const result=await MeshRuntime.request(selectedRuntime(),'runtime.snapshot',{kind:kind.toLowerCase()});const rows=conversations.get(id)||[];conversations.set(id,rows);rows.push({sender:'Host',text:result.lines.join('\n')});if(selected===id)renderConversation();}catch(e){say(e.message);}
  };
  async function loadMailbox() {
    const id=selected,epoch=++mailboxEpoch;if(!id || id.startsWith('factory-'))return;
    try{const result=await api('mailbox.list',{agent:id});const data=result.result;if(id!==selected || epoch!==mailboxEpoch)return;
      $('mailboxItems').innerHTML=data.pending.map(m=>`<li><strong>${escape(m.subject)}</strong><p>${escape(m.body)}</p><small>Pending · priority ${m.priority||0}</small><div><button data-mail-mission="${escape(m.id)}">Create mission</button><button data-mail-edit="${escape(m.id)}">Edit</button><button data-mail-priority="${escape(m.id)}" data-priority="${Math.min(100,(m.priority||0)+1)}">Raise priority</button><button data-mail-priority="${escape(m.id)}" data-priority="${Math.max(-100,(m.priority||0)-1)}">Lower priority</button><button data-mail-remove="${escape(m.id)}">Remove</button></div></li>`).join('')||'<li>No pending items.</li>';
      $('mailboxHistory').innerHTML=data.history.map(m=>`<li><strong>${escape(m.subject)}</strong><p>${escape(m.body)}</p><small>Delivered context · ${escape(m.created_at)}</small></li>`).join('')||'<li>No delivered items.</li>';
      $('mailboxItems').querySelectorAll('button').forEach(b=>b.onclick=async()=>{
        if(b.dataset.mailMission){const m=data.pending.find(m=>m.id===b.dataset.mailMission);$('openMission').click();$('missionForm').elements.title.value=m.subject||'Owner mission';$('missionForm').elements.description.value=m.body;$('missionForm').elements.assignee.value=id;return;}
        const mid=b.dataset.mailEdit||b.dataset.mailRemove||b.dataset.mailPriority;
        const action=b.dataset.mailEdit?'mailbox.edit':b.dataset.mailRemove?'mailbox.remove':'mailbox.priority';const args={agent:id,id:mid};
        if(action==='mailbox.edit'){const text=prompt('Edit pending mailbox item',data.pending.find(m=>m.id===mid).body);if(text===null || !text.trim())return;args.text=text;}
        if(action==='mailbox.priority')args.priority=Number(b.dataset.priority);
        b.disabled=true;try{await api(action,args);loadMailbox();}catch(e){say(e.message);b.disabled=false;}
      });
    }catch(e){if(selected===id)$('mailboxItems').textContent=e.message;}
  }
  async function refresh() {
    if(pending)return;pending=true;const epoch=hostEpoch;
    try{const [result,status]=await Promise.all([api('snapshot'),fetch('/api/status').then(async r=>{if(!r.ok)throw Error('Fleet status unavailable');return r.json();})]);if(epoch!==hostEpoch)return;fleet=status.agents || [];snapshot=MeshRuntime.unifiedOffice(result.snapshot,fleet,host());online=true;render();if(selected && !selected.startsWith('factory-'))loadMailbox();say(snapshot.paused?'Office paused · coordination remains available':'Office connected · live state from your host');}
    catch(e){if(epoch!==hostEpoch)return;online=false;$('officeSignal').classList.remove('online');say(e.message);for(const id of ['openHire','openMission','officePause','saveOfficeSettings'])$(id).disabled=true;if(snapshot){snapshot.agents.forEach(a=>a.state='offline');render();}}
    finally{pending=false;}
  }
  $('officeHost').onchange=()=>{hostEpoch++;mailboxEpoch++;runtimeState=null;conversations.clear();selectedLink=null;snapshot=null;selected=null;online=false;chatter=null;artifacts=[];handoffs=[];positions={};basePositions={};manualPositions={};$('floorNodes').replaceChildren();$('floorLinks').replaceChildren();$('floorEmpty').hidden=false;try{manualPositions=JSON.parse(sessionStorage.getItem('mesh-office-layout:'+host())||'{}');}catch{}refresh();};
  $('officeRefresh').onclick=refresh;
  $('zoomIn').onclick=()=>{zoom=Math.min(1.8,zoom+.15);fit();};$('zoomOut').onclick=()=>{zoom=Math.max(.6,zoom-.15);fit();};$('zoomReset').onclick=()=>{zoom=1;fit();};
  new ResizeObserver(fit).observe($('officeFloor'));
  document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>b.closest('dialog').close());
  $('openHire').onclick=()=>{
    let restore=$('restoreWorkers');if(!restore){restore=document.createElement('div');restore.id='restoreWorkers';$('hireDialog').append(restore);}
    restore.innerHTML=(snapshot.archivedAgents||[]).map(a=>`<p>${escape(a.name)} <button data-restore="${escape(a.id)}">Return to office</button></p>`).join('');
    restore.querySelectorAll('button').forEach(b=>b.onclick=async()=>{try{await api('restore',{id:b.dataset.restore});$('hireDialog').close();await refresh();}catch(e){say(e.message);}});$('hireDialog').showModal();};
  $('openMission').onclick=()=>{
    $('missionForm').elements.assignee.innerHTML=snapshot.agents.map(a=>`<option value="${escape(a.id)}">${escape(a.name)} · ${escape(a.role)}</option>`).join('');
    $('missionForm').elements.dependsOn.innerHTML=snapshot.tasks.filter(t=>t.status!=='done').map(t=>`<option value="${escape(t.id)}">${escape(t.title)}</option>`).join('');
    $('missionDialog').showModal();
  };
  function formAction(id,operation,args) {
    $(id).onsubmit=async e=>{e.preventDefault();const form=e.target;const error=form.querySelector('.dialog-error');error.textContent='';form.querySelector('button[type="submit"],.primary-btn').disabled=true;try{await api(operation,args(form));form.closest('dialog').close();form.reset();await refresh();}catch(e){error.textContent=e.message;}finally{form.querySelector('button[type="submit"],.primary-btn').disabled=false;}};
  }
  formAction('hireForm','hire',f=>({name:f.elements.name.value,role:f.elements.role.value,goal:f.elements.goal.value}));
  $('missionForm').onsubmit=async e=>{e.preventDefault();const f=e.target,b=f.querySelector('.primary-btn'),epoch=hostEpoch,aid=host();b.disabled=true;try{const references=await FactoryFiles.attach(aid,[...$('missionFormFiles').files],n=>$('missionFormFileStatus').textContent=n);if(epoch!==hostEpoch)throw Error('Execution host changed; prompt was not sent.');await api('task.create',{title:f.elements.title.value,description:FactoryFiles.brief(f.elements.description.value,references),assignee:f.elements.assignee.value,dependsOn:[...f.elements.dependsOn.selectedOptions].map(o=>o.value),needsApproval:f.elements.needsApproval.checked});f.closest('dialog').close();f.reset();refresh();}catch(error){f.querySelector('.dialog-error').textContent=error.message;}finally{b.disabled=false;}};
  formAction('memoryForm','memory.save',f=>({id:selected,text:f.elements.text.value}));
  $('officeMessage').onsubmit=async e=>{e.preventDefault();const id=selected,epoch=hostEpoch,aid=host(),b=e.target.querySelector('button');b.disabled=true;try{const references=await FactoryFiles.attach(aid,[...$('officeMessageFiles').files],n=>$('officeMessageFileStatus').textContent=n);if(epoch!==hostEpoch)throw Error('Execution host changed; prompt was not sent.');await api('message',{to:id,text:FactoryFiles.brief(e.target.elements.text.value,references)});if(selected===id)e.target.reset();await refresh();say('Message delivered to the office mailbox. It will be read with the next mission.');}catch(e){say(e.message);}finally{b.disabled=false;}};
  $('openMemory').onclick=async()=>{try{const result=await api('memory',{id:selected});$('memoryForm').elements.text.value=result.result.text;$('memoryDialog').showModal();}catch(e){say(e.message);}};
  $('archiveWorker').onclick=async()=>{try{await api('archive',{id:selected});selected=null;await refresh();}catch(e){say(e.message);}};
  $('officePause').onclick=async()=>{try{await api('pause',{paused:!snapshot.paused});await refresh();}catch(e){say(e.message);}};
  $('saveOfficeSettings').onclick=async()=>{try{await api('settings',{maxIterations:Number($('maxIterations').value)});await refresh();}catch(e){say(e.message);}};

  let sharedPending=false;
  async function loadShared() {
    if(!host() || sharedPending)return;sharedPending=true;const epoch=hostEpoch,aid=host();
    try {
      const fleetResponse=await fetch('/api/status');const fleetData=await fleetResponse.json();if(epoch!==hostEpoch)return;fleet=fleetData.agents||[];
      const r=await MeshRuntime.request(aid,'handoff.list');if(epoch!==hostEpoch)return;
      handoffs=r.rules||[];chatter=r.chatter;$('officeChatter').checked=Boolean(chatter?.enabled);if(document.activeElement!==$('chatterMinutes'))$('chatterMinutes').value=chatter?.session_minutes||15;$('chatterMinutes').readOnly=!chatter?.enabled;$('chatterConcurrency').disabled=!chatter?.enabled;$('chatterGroup').disabled=!chatter?.enabled;if(document.activeElement!==$('chatterConcurrency'))$('chatterConcurrency').value=chatter?.max_conversations||1;$('chatterGroup').checked=Boolean(chatter?.experimental_group_chat);renderShared();
    } catch(e) {if(epoch===hostEpoch)$('chatterNotice').textContent=e.message;}
    finally {sharedPending=false;}
  }
  function renderShared() {
    if(snapshot)$('officeMessageCount').textContent=snapshot.messages.length+(chatter?.conversations||[]).reduce((n,c)=>n+c.messages.length,0);
    $('chatterNotice').textContent=chatter?.enabled?'Chatter on · idle agents only · '+(chatter.max_conversations||1)+' concurrent conversations · '+(chatter.experimental_group_chat?'3-agent groups':'pairs')+' · repeating '+(chatter.session_minutes||15)+'-minute sessions · '+(chatter.admission||'Waiting for idle agents and capacity')+'.':'Chatter off. Enable to discuss shared projects with idle agents.';
    $('chatterFeed').innerHTML=(chatter?.conversations||[]).slice().reverse().map(c=>`<li><strong>${escape(c.a_role)} ↔ ${escape(c.b_role)}${c.c_role?' ↔ '+escape(c.c_role):''} · ${escape(c.topic)}</strong><p>${escape(c.state)}${c.note?' · '+escape(c.note):''}</p>${(c.memory||[]).map(m=>`<small>${escape(m.agent)} · ${escape(m.status)}${m.ids?.length?' · '+escape(m.ids.join(', ')):''}</small>`).join('')}${c.messages.map(m=>`<p><strong>${escape(m.agent)}</strong><br>${escape(m.text)}</p>`).join('')}<small>${escape(new Date(c.created*1000).toLocaleString())}</small></li>`).join('')||'<li>No office conversations recorded.</li>';
    $('handoffItems').innerHTML=handoffs.filter(r=>!selected || !selected.startsWith('factory-') || r.target===selectedRuntime()).map(r=>`<li><strong>${escape(r.source)} → ${escape(r.target_role)}</strong><p>${escape(r.text)}</p><p>${escape(r.state)} · ${escape(r.note||'')}</p>${r.artifact?'<p>Artifact: '+escape(r.artifact.name)+'</p>':''}${['waiting','paused'].includes(r.state)?`<button data-rule="${r.id}" data-target="${escape(r.target)}" data-state="${r.state==='paused'?'waiting':'paused'}">${r.state==='paused'?'Resume':'Pause'}</button><button data-rule="${r.id}" data-target="${escape(r.target)}" data-state="cancelled">Cancel</button>`:''}</li>`).join('')||'<li>No conditional instructions.</li>';
    $('handoffItems').querySelectorAll('[data-rule]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{await MeshRuntime.request(b.dataset.target,'handoff.control',{id:b.dataset.rule,state:b.dataset.state});loadShared();}catch(e){say(e.message);b.disabled=false;}});
  }
  $('officeChatter').onchange=async()=>{const b=$('officeChatter'),enabled=b.checked;b.disabled=true;try{await MeshRuntime.request(host(),'chatter.configure',{enabled});await loadShared();}catch(e){b.checked=!enabled;say(e.message);}finally{b.disabled=false;}};
  for(const id of ['chatterConcurrency','chatterGroup'])$(id).onchange=async()=>{if(!chatter?.enabled||!$('chatterConcurrency').reportValidity())return;try{await MeshRuntime.request(host(),'chatter.configure',{enabled:true,max_conversations:Number($('chatterConcurrency').value),experimental_group_chat:$('chatterGroup').checked});await loadShared();}catch(e){say(e.message);await loadShared();}};
  $('chatterMinutes').onchange=async()=>{const input=$('chatterMinutes');if(!chatter?.enabled)return;if(!input.reportValidity())return;input.disabled=true;try{await MeshRuntime.request(host(),'chatter.configure',{enabled:true,session_minutes:Number(input.value)});await loadShared();}catch(e){input.value=chatter?.session_minutes||15;say(e.message);}finally{input.disabled=false;}};
  async function loadArtifacts() {
    const epoch=hostEpoch,aid=host();$('artifactStatus').textContent='Loading host files…';
    try{const r=await MeshRuntime.request(aid,'files.list');if(epoch!==hostEpoch)return;artifacts=r.files;renderArtifacts();$('artifactStatus').textContent=`${artifacts.length} files · attachments/downloads up to 10 MB. New files are published under /mnt/pt-context/deliverables/mesh-<agent>/.`;}
    catch(e){if(epoch===hostEpoch)$('artifactStatus').textContent=e.message;}
  }
  function renderArtifacts() {
    const query=$('artifactSearch').value.toLowerCase();
    $('artifactItems').innerHTML=artifacts.filter(f=>(f.name+' '+f.producer+' '+f.source+' '+f.relative_path).toLowerCase().includes(query)).map(f=>`<li><strong>${escape(f.name)}</strong><p>${escape(f.producer)} · ${escape(f.source)} · ${escape(f.relative_path)}<br>${(f.size/1024).toFixed(1)} KB · ${escape(new Date(f.modified*1000).toLocaleString())}</p><button data-download="${f.id}" ${!f.downloadable?'disabled':''}>Download</button>${/\.(txt|md|csv|json|py|js|ts|html|css|yaml|yml)$/i.test(f.name)?`<button data-preview="${f.id}">Preview text</button>`:/\.(png|jpe?g|gif|webp)$/i.test(f.name)?`<button data-image="${f.id}">Preview image</button>`:''}<button data-file-context="${f.id}">Use in prompt</button></li>`).join('')||'<li>No matching published files.</li>';
    $('artifactItems').querySelectorAll('button').forEach(b=>b.onclick=async()=>{
      const file=artifacts.find(f=>f.id===(b.dataset.download||b.dataset.preview||b.dataset.image||b.dataset.fileContext));if(!file)return;const aid=host(),epoch=hostEpoch;b.disabled=true;
      try{if(b.dataset.fileContext){const r=await MeshRuntime.request(aid,'files.reference',{id:file.id});if(epoch!==hostEpoch)return;const form=selected?.startsWith('factory-')?$('factoryMessage'):$('officeMessage');form.elements.text.value=FactoryFiles.brief(form.elements.text.value,[r.reference]);$('artifactDialog').close();say('Artifact reference added to the selected prompt.');}
        else {const text=await FactoryFiles.download(aid,file,b.dataset.preview?'text':b.dataset.image?'image':false);if(text && epoch===hostEpoch){if(b.dataset.image){const img=$('artifactImage');if(img.src.startsWith('blob:'))URL.revokeObjectURL(img.src);img.src=text;img.hidden=false;$('artifactPreview').hidden=true;}else{$('artifactImage').hidden=true;$('artifactPreview').hidden=false;$('artifactPreview').textContent=text;}}}}
      catch(e){$('artifactStatus').textContent=e.message;}finally{b.disabled=false;}
    });
  }
  $('openArtifacts').onclick=()=>{$('artifactDialog').showModal();loadArtifacts();};$('artifactRefresh').onclick=loadArtifacts;$('artifactSearch').oninput=renderArtifacts;
  function showCounter(kind) {
    $('counterTitle').textContent={agents:'Agent roster',missions:'Mission queue',messages:'Messages'}[kind];
    let html='';
    if(kind==='agents')html=[...snapshot.agents,...(snapshot.factoryAgents||[]).map(a=>({...a,name:a.id,id:'factory-'+a.id,role:fleet.find(f=>f.runtime_id===a.runtime_id)?.role||a.runtime_id,state:a.state}))].map(a=>`<p><button data-select-agent="${escape(a.id)}">${escape(a.name)}</button> · ${escape(a.role)} · ${escape(a.state)}</p>`).join('');
    if(kind==='missions')html=snapshot.tasks.slice().sort((a,b)=>(b.priority||0)-(a.priority||0)).map(t=>`<article><strong>${escape(t.title)}</strong><p>${escape(t.status)} · priority ${t.priority||0}</p><p>${escape(t.description)}</p>${t.status==='todo'?`<button data-task-priority="${t.id}" data-priority="${Math.min(100,(t.priority||0)+1)}">Raise priority</button><button data-task-priority="${t.id}" data-priority="${Math.max(-100,(t.priority||0)-1)}">Lower priority</button>`:''}</article>`).join('')||'<p>No missions.</p>';
    if(kind==='messages')html=snapshot.messages.map(m=>`<article><strong>${escape(m.subject||'Message')}</strong><p>${escape(m.from)} → ${escape(m.to)}</p><p>${escape(m.body)}</p><button data-reply="${escape(m.from)}">Reply</button></article>`).join('')||'<p>No messages.</p>';
    if(kind==='messages')html+=(chatter?.conversations||[]).flatMap(c=>c.messages.map(m=>`<article><strong>Office chatter · ${escape(m.agent)}</strong><p>${escape(m.text)}</p><button data-native-reply="${escape(m.agent)}">Reply to agent</button></article>`)).join('');
    $('counterContent').innerHTML=html;
    $('counterContent').querySelectorAll('[data-select-agent]').forEach(b=>b.onclick=()=>{selected=b.dataset.selectAgent;renderInspector();renderFloor();renderShared();$('counterDialog').close();selected.startsWith('factory-')?loadRuntime():loadMailbox();});
    $('counterContent').querySelectorAll('[data-task-priority]').forEach(b=>b.onclick=async()=>{try{await api('task.priority',{id:b.dataset.taskPriority,priority:Number(b.dataset.priority)});await refresh();showCounter('missions');}catch(e){say(e.message);}});
    $('counterContent').querySelectorAll('[data-reply]').forEach(b=>b.onclick=()=>{const agent=snapshot.agents.find(a=>a.id===b.dataset.reply);selected=agent?.id||'orchestrator';renderInspector();renderFloor();loadMailbox();$('counterDialog').close();$('officeMessage').elements.text.focus();});
    $('counterContent').querySelectorAll('[data-native-reply]').forEach(b=>b.onclick=()=>{selected='factory-'+b.dataset.nativeReply;renderInspector();renderFloor();loadRuntime();$('counterDialog').close();$('factoryMessage').elements.text.focus();});
    if(!$('counterDialog').open)$('counterDialog').showModal();
  }
  $('rosterCounter').onclick=()=>showCounter('agents');$('missionCounter').onclick=()=>showCounter('missions');$('messageCounter').onclick=()=>showCounter('messages');

  try{manualPositions=JSON.parse(sessionStorage.getItem('mesh-office-layout:'+host())||'{}');}catch{}
  refresh();loadShared();setInterval(syncConversation,4000);const sharedTimer=setInterval(loadShared,6000);const timer=setInterval(refresh,4000);window.addEventListener('pagehide',()=>{clearInterval(timer);clearInterval(sharedTimer);cancelAnimationFrame(animation);});
})();
