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
    if(agent.transport && agent.transport!=='connected')return {state:'idle',label:'Offline',detail:'Gray: the gateway is offline.'};
    if(runtime.sleeping)return {state:'sleeping',label:'Asleep',detail:'Amber: this agent is asleep in Mesh and Factory.'+(last?' Previous result: '+last:'')};
    if(['active','working','processing'].includes(agent.state))return {state:'busy',label:'Working',detail:'Blue: the host reports active work.'+(last?' Previous result: '+last:'')};
    const health=runtime.health;
    const healthAge=health?Date.now()/1000-health.checked_at:Infinity;
    const current=health?' Current check: gateway '+(health.gateway_reachable?'reachable':'unavailable')+', model provider '+(health.model_provider_reachable===true?'reachable':health.model_provider_reachable===false?'unavailable':'not verified')+(health.configured_model_installed===false?', configured model missing':'')+'.':'';
    const fresh=health?.state==='reachable' && health.checked_at>=Number(result.at||0) && healthAge>=-5 && healthAge<45;
    if(result.severity==='error' && result.code==='mesh_provider_unavailable' && fresh)return {state:'warning',label:'Previous request failed',detail:'Amber: '+last+' Current gateway and model provider are reachable; the configured model is installed. The failed request was not retried.'};
    if(result.severity==='error')return {state:'error',label:'Last action failed',detail:'Red: '+(last || 'The last Mesh request failed; see its error in this conversation.')+current};
    if(agent.transport && agent.transport!=='connected')return {state:'idle',label:'Offline',detail:'Gray: the gateway is offline.'+(last?' Previous result: '+last:'')};
    if((monitoring || agent.gateway_agent) && agent.transport==='connected')return {state:'monitoring',label:'Gateway connected',detail:'Purple: the host gateway is connected.'+(last?' Last result: '+last:'')};
    if(agent.last_event){
      const direction=terminalDirection(agent.last_event),state={SYS:'monitoring',IN:'success',OUT:'busy',ERR:'error',FILE:'warning'}[direction.label];
      return {state,label:direction.label+' activity',detail:'Latest stream event: '+direction.label+'. The light matches the terminal.'};
    }
    if(agent.state==='unknown' && !result.code)return {state:'idle',label:'Activity unknown',detail:'Gray: no current activity observation is available.'};
    if(result.severity==='success')return {state:'success',label:'Last action completed',detail:'Green: '+(last || 'The last reply completed.')};
    return {state:'idle',label:'Idle',detail:'Gray: no current work or recorded result is reported.'};
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
  window.MeshRuntime={history,request,run,errors,indicator,memoryLabel,recover,terminalDirection,factoryAgent,factoryRoster,unifiedOffice};
})();
