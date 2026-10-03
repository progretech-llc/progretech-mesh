'use strict';
const $ = (selector) => document.querySelector(selector);
let generation = 0;
const notice = (text, error = false) => { $('#status').textContent = text; $('#status').classList.toggle('error', error); };
const hostPath = (host = $('#host').value) => `/api/agents/${encodeURIComponent(host)}`;
async function jsonFetch(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'Content-Type': 'application/json', ...options.headers}, signal: AbortSignal.timeout(52000)});
  if (response.status === 401) throw new Error('Your session expired. Sign in to Mesh again.');
  const data = await response.json();
  if (!response.ok || data.ok === false) throw new Error(`${data.error || 'Request failed'}${data.detail ? ': ' + data.detail : ''}`);
  return data;
}
async function control(action, args = {}, host = $('#host').value) {
  if (!host) throw new Error('Choose an owned workstation first.');
  const data = await jsonFetch(`${hostPath(host)}/factory/control`, {method:'POST', body:JSON.stringify({action,args})});
  return data.result;
}
function element(tag, text, className) {
  const node = document.createElement(tag); node.textContent = text; if (className) node.className = className; return node;
}
function renderStatus(data) {
  const agents = Array.isArray(data.agents) ? data.agents : [];
  $('#agents').replaceChildren(); $('#controller').replaceChildren();
  for (const agent of agents) {
    const card = element('article','', 'factory-agent');
    if (MeshAvatar.source(agent)) {
      const avatar = document.createElement('img'); avatar.src=MeshAvatar.source(agent); avatar.alt=''; avatar.width=64; avatar.height=64; avatar.style.objectFit='cover'; card.append(avatar);
    }
    card.append(element('h3',agent.name || agent.id),element('p',agent.role || 'Role not reported'));
    card.append(element('span',agent.controller ? 'Controller' : 'Worker','badge'));
    card.append(element('span',agent.workspace_ready ? 'Workspace ready' : 'Workspace not ready','badge'));
    const model = typeof agent.model === 'string' ? agent.model : agent.model?.primary;
    card.append(element('p',`Model: ${model || 'Not reported'}`));
    card.append(element('p',`Hardware: ${agent.hardware_status || 'Not reported'}`,'muted'));
    $('#agents').append(card);
    if (/^[a-z0-9_-]+$/.test(agent.id || '')) {
      const option = new Option(agent.name || agent.id,agent.id); option.selected = agent.id === 'lyra'; $('#controller').append(option);
    }
  }
  for (const id of ['rend','lyra','mak']) {
    if (!agents.some(a => a.id === id)) {
      const card = element('article','', 'factory-agent');
 card.append(element('h3',id[0].toUpperCase()+id.slice(1)),element('p','Not reported by this workstation.','muted')); $('#agents').append(card);
    }
  }
  $('#providers').replaceChildren();
  for (const [name, value] of Object.entries(data.providers || {})) {
    const details = document.createElement('details');details.append(element('summary',name),element('pre',JSON.stringify(value,null,2)));$('#providers').append(details);
  }
  $('#capabilities').replaceChildren();
  for (const cap of data.capabilities || []) $('#capabilities').append(element('p',typeof cap === 'string' ? cap : JSON.stringify(cap)));
  $('#updated').textContent = `Reported: ${data.timestamp || 'timestamp unavailable'}`;
}
async function refresh() {
  const token = ++generation; const host = $('#host').value;
  if (!host) return notice('No owned workstation is enrolled. Connect Rend from the Mesh console.',true);
  notice('Requesting live factory status…'); $('#refresh').disabled = true;
  try {
    const data = await jsonFetch(`${hostPath(host)}/factory`);
    if (token !== generation) return;
    renderStatus(data.result || {}); notice('Live workstation status received.');
  } catch (error) {if(token===generation){notice(error.message,true);$('#agents').replaceChildren(element('p','Live agent status unavailable.'));$('#controller').replaceChildren(new Option('Load agents first',''));$('#providers').replaceChildren();$('#capabilities').textContent='Live status unavailable.';$('#updated').textContent='';}}
  finally {if(token===generation) $('#refresh').disabled=false;}
}
function loadDevices(data) {
  for (const kind of ['source','sink']) {
    const select = $(`#audio-${kind}`);select.replaceChildren(new Option('System default',''));
    for (const device of data?.[`${kind}s`] || []) select.append(new Option(device.description || device.name,device.name));
    select.value = data?.[`selected_${kind}`] || '';
  }
}
async function perform(target, args) {
  const action = target.dataset.action;
  const host = $('#host').value;
  if(target.dataset.confirm && !window.confirm(target.dataset.confirm)) return;
  const panel = target.closest('.panel');const output = panel.querySelector('.result');
  const buttons = [...panel.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);output.textContent='Waiting for workstation…';
  try {
    const data = await control(action,args,host);
    if (host !== $('#host').value) {output.textContent='Workstation selection changed. Reload this view for the selected workstation.'; return;}
    output.textContent=JSON.stringify(data ?? {},null,2);
    if(action==='audio.get') loadDevices(data);
    if(action==='chatter.get') {
      const settings=data?.settings || data?.config || data;
      for(const key of ['enabled','quiet']) if(typeof settings?.[key]==='boolean') panel.querySelector(`[name="${key}"]`).checked=settings[key];
    }
  } catch(error) {output.textContent=error.message;}
  finally {buttons.forEach(b=>b.disabled=false);}
}
document.querySelectorAll('button[data-action]').forEach(button=>button.addEventListener('click',()=>perform(button,{})));
document.querySelectorAll('form[data-action]').forEach(form=>form.addEventListener('submit',event=>{
  event.preventDefault();const args=Object.fromEntries(new FormData(form));
  form.querySelectorAll('input[type="checkbox"]').forEach(input=>args[input.name]=input.checked);
  if('pitch' in args) args.pitch=Number(args.pitch);
  perform(form,args);
}));
$('#task-form').addEventListener('submit', async event=>{
  event.preventDefault();const host=$('#host').value;const agent=$('#controller').value;const text=$('#task').value.trim();
  if(!host||!agent||!text) return;
  const button=$('#task-form button');button.disabled=true;$('#task-result').textContent='Sending…';
  try {
    const sent=await jsonFetch(`${hostPath(host)}/message`,{method:'POST',body:JSON.stringify({text:`/agent ${agent} ${text}`})});
    $('#task-result').textContent=`Accepted by ${agent}. Waiting for a correlated response…`;
    for(let attempt=0;attempt<120;attempt++) {
      await new Promise(resolve=>setTimeout(resolve,2000));
      const events=await jsonFetch(`${hostPath(host)}/events`);
      const matches=(events.events || []).filter(e=>e.payload?.request_id===sent.request_id && e.type!=='user_message');
      if(matches.length) $('#task-result').textContent=matches.map(e=>e.message || JSON.stringify(e.payload)).join('\n\n');
      if(matches.some(e=>['agent_message','message_response','error'].includes(e.type)||e.payload?.final===true||e.payload?.status==='completed')) return;
    }
    $('#task-result').textContent+='\nLive waiting ended. The task may still be running; open the Mesh conversation for further updates. No duplicate task was submitted.';
  } catch(error) {$('#task-result').textContent=error.message;}
  finally {button.disabled=false;}
});
$('#refresh').addEventListener('click',refresh);$('#host').addEventListener('change',refresh);refresh();
