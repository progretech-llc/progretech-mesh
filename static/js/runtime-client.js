/* Shared, factual host progress for the fleet and Factory. */
(() => {
  const errors = {
    mesh_no_active_work:'No active work session is currently observed for this agent. Send chat or create a mission instead.',
    mesh_active_session_unavailable:'The host has no verified active session for this role.',
    mesh_context_delivery_unconfirmed:'Instruction delivery is unconfirmed. Check activity before sending it again; no automatic retry was sent.',
    mesh_agent_sleeping:'This agent is asleep. Wake it to send a message.',
    mesh_agent_busy:'This agent already has a request in progress.',
    mesh_context_limit:'The conversation exceeds the local model context. Start a new conversation; existing history is preserved.',
    mesh_provider_rejected:'The model rejected the request format or context. Try a new conversation. If it persists, check the local provider configuration.',
    mesh_provider_unavailable:'The earlier request could not reach or complete with the local model provider.',
    mesh_image_provider_unavailable:'No approved local image provider is active. No image was generated.',
    mesh_image_generation_failed:'Local image generation failed. No deliverable was published.',
    mesh_image_validation_failed:'The generated file failed image validation.',
    mesh_image_memory_headroom_required:'Image generation needs more available RAM.',
    mesh_image_review_model_unavailable:'No configured downloaded vision model is available for review.',
    mesh_image_brief_too_long:'Keep image-generation briefs under 1,200 characters.',
    mesh_reply_timeout:'The reply timed out. Check agent activity before sending again.',
    model_memory_headroom_required:'Not enough free memory to load this model alongside current models.',
    runtime_controls_unavailable:'Shared agent controls are unavailable on this host.',
    mesh_queue_timeout:'The shared model slot stayed busy. Check host activity.',
  };
  async function request(agent, action, args={}) {
    const r=await fetch(`/api/agents/${encodeURIComponent(agent)}/management`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,args})});
    const d=await r.json();
    if(!r.ok || !d.ok) throw Error(errors[d.error] || d.error || 'Host request failed');
    return d.result;
  }
  async function history(agent) { return (await request(agent,'communication.get')).conversation || {enabled:false,events:[]}; }
  async function run(agent,action,args={},progress=()=>{}) {
    let job=await request(agent,action,args);
    const deadline=Date.now()+(job.capability==='image_generation'?40:21)*60*1000;
    while(true) {
      progress(job);
      if(job.done) {if(job.error)throw Error(errors[job.error] || job.error);return job.result;}
      if(Date.now()>deadline)throw Error('Progress polling timed out. The host request may still be running; check activity before sending again.');
      await new Promise(resolve=>setTimeout(resolve,1500));
      job=await request(agent,'communication.job',{job_id:job.job_id});
    }
  }
  function terminalDirection(message) {
    const type=String(message?.type || 'event'),payload=message?.payload || {};
    const direction=String(payload.direction || '').toLowerCase(),severity=String(payload.severity || '').toLowerCase();
    if(severity==='error' || type==='direct_error')return {label:'ERR',cls:'dir-err'};
    if(type.startsWith('file_') || type==='file')return {label:'FILE',cls:'dir-file'};
    if(['user_message','group_message'].includes(type) || ['input','out','outbound'].includes(direction))return {label:'OUT',cls:'dir-out'};
    if(['message_response','command_ack'].includes(type) || ['output','in','inbound'].includes(direction))return {label:'IN',cls:'dir-in'};
    return {label:'SYS',cls:'dir-sys'};
  }
  function factoryAgent(row,fleet,host) {
    const match=(row.runtime_id==='main'?fleet.find(a=>a.id===host):null) || fleet.find(a=>a.id===host+'--'+row.runtime_id) || fleet.find(a=>a.runtime_id===row.runtime_id && a.control_center_gateway===host) || (row.runtime_id==='main'?fleet.find(a=>a.id===host):null);
    // Both views use the same authenticated fleet observation; unknown stays unknown.
    return match ? {...row,...match,mesh_runtime:match.mesh_runtime || row} : {...row,state:'unknown',transport:'not-connected'};
  }
  function factoryRoster(rows,fleet,host) {
    const all=[...rows];
    for(const agent of fleet.filter(a=>a.control_center_gateway===host && !a.office_worker && !a.office_archived).map(a=>({...a,runtime_id:a.runtime_id || a.id.slice(host.length+2)}))){
      if(!all.some(row=>row.runtime_id===agent.runtime_id))all.push({id:agent.runtime_id,runtime_id:agent.runtime_id,state:'unknown'});
    }
    return all.filter((row,i)=>all.findIndex(a=>a.runtime_id===row.runtime_id)===i).map(row=>({...row,...factoryAgent(row,fleet,host),id:row.id}));
  }
  function unifiedOffice(snapshot,fleet,host) {
    const observed=factoryRoster(snapshot.factoryAgents || [],fleet,host);
    const aliases={};
    const agents=snapshot.agents.map(agent=>{
      const live=observed.find(row=>row.runtime_id===agent.runtime_id);
      if(!live)return agent;
      aliases['factory-'+live.id]=agent.id;
      return {...agent,native:live,mesh_agent_id:live.id===host?host:(fleet.find(a=>a.runtime_id===agent.runtime_id && (a.control_center_gateway===host||a.id===host))?.id),state:live.state};
    });
    const bound=new Set(agents.map(a=>a.runtime_id).filter(Boolean));
    const archived=new Set((snapshot.archivedAgents||[]).map(a=>a.runtime_id).filter(Boolean));
    snapshot.agents=agents;
    snapshot.factoryAgents=observed.filter(a=>!bound.has(a.runtime_id)&&!archived.has(a.runtime_id));
    snapshot.interactions=(snapshot.interactions||[]).map(l=>({...l,from:aliases[l.from]||l.from,to:aliases[l.to]||l.to,parts:Object.fromEntries(Object.entries(l.parts||{}).map(([id,text])=>[aliases[id]||id,text]))})).filter(l=>l.from!==l.to);
    return snapshot;
  }
  function indicator(agent, {monitoring=false}={}) {
    const runtime=agent.mesh_runtime || agent;
    const result=runtime.last_result || {};
    const labels={native_agent_failed:'The last native agent turn failed. This occurred outside this Mesh conversation; detailed provider diagnostics are unavailable here.',native_turn_complete:'The last native agent turn completed.',reply_received:'The last Mesh reply was received.'};
    const last=result.code ? `${labels[result.code] || errors[result.code] || result.code}${result.at ? ' Recorded '+new Date(result.at*1000).toLocaleString()+'.' : ''}` : '';
    // Current observed activity takes precedence over the last completed turn.
    if(agent.transport && agent.transport!=='connected')return {state:'offline',label:'Offline',detail:'Gray: the gateway is offline.'};
    if(runtime.sleeping)return {state:'sleeping',label:'Sleeping',detail:'Gray: this agent is asleep and can be woken by ping or the Wake up control.'+(last?' Previous result: '+last:'')};
    const observedAt=agent.activity?.observed_at || agent.last_heartbeat;
    const age=observedAt ? (Date.now()-Date.parse(observedAt))/1000 : null;
    if(['active','working','processing'].includes(agent.state) && age!==null && (!Number.isFinite(age) || age<0 || age>180))return {state:'unknown',label:'Activity unknown',detail:'The activity report expired. Connectivity does not confirm active work.'};
    if(['active','working','processing'].includes(agent.state))return {state:'busy',label:'Working',detail:'Blue: the host reports active work.'+(last?' Previous result: '+last:'')};
    const health=runtime.health;
    const current=health?' Current check: gateway '+(health.gateway_reachable?'reachable':'unavailable')+', model provider '+(health.model_provider_reachable===true?'reachable':health.model_provider_reachable===false?'unavailable':'not verified')+(health.configured_model_installed===false?', configured model missing':'')+'.':'';
    const resultAt=Number(result.at || 0);
    const healthyAfterError=result.severity==='error' && resultAt>0 && Number(health?.checked_at || 0)>=resultAt && health?.gateway_reachable===true && health?.model_provider_reachable!==false && health?.configured_model_installed!==false;
    const recentError=result.severity==='error' && (!resultAt || Date.now()/1000-resultAt<300);
    if(result.severity==='error' && !healthyAfterError && recentError)return {state:'error',label:'Last action failed',detail:'Red: '+(last || 'The last Mesh request failed; see its error in this conversation.')+current};
    const previousFailure=result.severity==='error' ? ' Previous failure: '+(last || 'A prior Mesh request failed.')+current : '';
    if(agent.transport && agent.transport!=='connected')return {state:'offline',label:'Offline',detail:'Gray: the gateway is offline.'+(last?' Previous result: '+last:'')};
    if((monitoring || agent.gateway_agent) && agent.transport==='connected')return {state:'idle',label:'Idle',detail:'Green: the gateway is connected and no active work is currently observed.'+(previousFailure || (last?' Last result: '+last:''))};
    if(agent.last_event){
      const direction=terminalDirection(agent.last_event),state={SYS:'idle',IN:'idle',OUT:'busy',ERR:'error',FILE:'idle'}[direction.label];
      return {state,label:direction.label+' activity',detail:'Latest stream event: '+direction.label+'. The light matches the terminal.'};
    }
    if(agent.state==='unknown' && !result.code && agent.transport!=='connected')return {state:'offline',label:'Activity unknown',detail:'Gray: no current gateway observation is available.'};
    if(agent.state==='unknown' && (!result.code || previousFailure))return {state:'idle',label:'Idle',detail:'Green: the agent is connected and no active work is currently observed.'+previousFailure};
    if(result.severity==='success')return {state:'idle',label:'Idle',detail:'Green: '+(last || 'The last reply completed; no current work is reported.')};
    return {state:'idle',label:'Idle',detail:'Green: the agent is connected and no current work is reported.'+previousFailure};
  }
  function workLabel(agent) {
    const runtime=agent.mesh_runtime || agent;
    const candidates=[runtime.current_task,runtime.task_title,runtime.task_id,agent.current_task,agent.task_title,agent.task_id,agent.task,agent.phase];
    const generic=new Set(['local host connected','authenticated local host','connected','idle','unknown','—','-']);
    const value=candidates.find(item=>item && !generic.has(String(item).trim().toLowerCase()));
    return value ? String(value) : (indicator(agent).state==='busy' ? 'Active work · details not reported by gateway' : 'No active task reported');
  }
  function memoryLabel(memory={}) {
    if(memory.latest_status==='activity_write_unavailable')return 'MemPalace: last activity write failed'+(memory.at?' · '+new Date(memory.at).toLocaleString():'')+'.';
    if(memory.recall_verified && memory.memory_id)return 'MemPalace: saved and recall verified · '+(memory.activity_kind==='reviewed_activity'?'reviewed activity':memory.activity_kind==='runtime_activity'?'automatic runtime activity; reviewed summary missing':'continuity checkpoint')+(memory.at?' · '+new Date(memory.at).toLocaleString():'')+' · '+memory.memory_id;
    return 'MemPalace: no verified recent activity receipt observed'+(memory.latest_status && memory.latest_status!=='not_observed'?' · '+memory.latest_status:'')+'.';
  }
  async function recover(agent,progress=()=>{}) {
    const result=await run(agent,'runtime.recover',{},progress);
    return (result.steps || []).map(s=>s.name+' · '+s.state+': '+s.detail).join('\n')+'\n'+result.note;
  }
  window.MeshRuntime={history,request,run,errors,indicator,workLabel,memoryLabel,recover,terminalDirection,factoryAgent,factoryRoster,unifiedOffice};
})();
