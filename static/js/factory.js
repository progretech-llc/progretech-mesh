'use strict';
const $ = (selector) => document.querySelector(selector);
let generation = 0;
let liveReady = false;
let availableActions = new Set();
let renderedHost = null;
let taskPending = false;
let requireSelection = false;
const notice = (text, error = false) => { $('#status').textContent = text; $('#status').classList.toggle('error', error); };
function updateActionButtons() {
  document.querySelectorAll('button[data-action]').forEach(button => {
    const available = liveReady && availableActions.has(button.dataset.action);
    button.disabled = !available;
    button.title = available ? '' : 'This control is not available through the connected gateway.';
  });
  document.querySelectorAll('form[data-action]').forEach(form => {
    const available = liveReady && availableActions.has(form.dataset.action);
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = !available;
    form.title = available ? '' : 'This control is not available through the connected gateway.';
  });
}
const hostPath = (host = $('#host').value) => `/api/agents/${encodeURIComponent(host)}`;
async function jsonFetch(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'Content-Type': 'application/json', ...options.headers}, signal: AbortSignal.timeout(52000)});
  if (response.status === 401) throw new Error('Your session expired. Sign in to Mesh again.');
  const data = await response.json();
  if (!response.ok || data.ok === false) throw new Error(`${data.error || 'Request failed'}${data.detail ? ': ' + data.detail : ''}`);
  return data;
}
async function control(action, args = {}, host = $('#host').value) {
  if (!host || !liveReady) throw new Error('Load a connected workstation first.');
  const data = await jsonFetch(`${hostPath(host)}/factory/control`, {method:'POST', body:JSON.stringify({action,args})});
  return data.result;
}
function element(tag, text, className) {
  const node = document.createElement(tag); node.textContent = text; if (className) node.className = className; return node;
}
function clearStatus(message) {
  liveReady = false;
  availableActions = new Set();
  $('#agents').replaceChildren(element('p', message));
  $('#controller').replaceChildren(new Option('Load agents first', ''));
  $('#mail-agent').replaceChildren(new Option('No available mailboxes', ''));
  $('#providers').replaceChildren(); $('#capabilities').textContent = 'Live status unavailable.';
  $('#updated').textContent = '';
  document.querySelectorAll('.panel button').forEach(button => button.disabled = true);
  updateActionButtons();
}
function renderStatus(data, selectedAgent = '') {
  const agents = Array.isArray(data.agents) ? data.agents : [];
  $('#agents').replaceChildren(); $('#controller').replaceChildren();
  $('#mail-agent').replaceChildren();
  const seen = new Set();
  for (const agent of agents) {
    if (!/^[A-Za-z0-9_.-]{1,128}$/.test(agent.id || '') || seen.has(agent.id)) continue;
    seen.add(agent.id);
    const card = element('article','', 'factory-agent');
    if (MeshAvatar.source(agent)) {
      const avatar = document.createElement('img'); avatar.src=MeshAvatar.source(agent); avatar.alt=''; avatar.width=64; avatar.height=64; avatar.style.objectFit='cover'; card.append(avatar);
    }
    card.append(element('h3',agent.name || agent.id),element('p',agent.role || 'Role not reported'));
    const role = element('span', agent.controller === true ? 'Controller' : agent.controller === false ? 'Worker' : 'Role not reported', 'badge');
    role.title = agent.controller_basis || ''; card.append(role);
    card.append(element('span',agent.workspace_ready === true ? 'Workspace ready' : agent.workspace_ready === false ? 'Workspace not ready' : 'Workspace not reported','badge'));
    const model = typeof agent.model === 'string' ? agent.model : agent.model?.primary;
    card.append(element('p',`Runtime: ${agent.runtime || 'Not reported'}`),element('p',`Model: ${model || 'Not reported'}`));
    card.append(element('p',`Hardware: ${agent.hardware_status || 'Not reported'}`,'muted'));
    $('#agents').append(card);
    $('#controller').append(new Option(agent.name || agent.id,agent.id));
    if (agent.mail_identity) $('#mail-agent').append(new Option(agent.name || agent.id,agent.mail_identity));
  }
  if (!seen.size) $('#agents').append(element('p','No agents reported by this gateway.'));
  if (!$('#mail-agent').options.length) $('#mail-agent').append(new Option('No available mailboxes',''));
  liveReady = true;
  availableActions = new Set(Array.isArray(data.capabilities) ? data.capabilities : []);
  updateActionButtons();
  if (seen.has(selectedAgent)) $('#controller').value = selectedAgent;
  else if (selectedAgent) $('#controller').prepend(new Option('Choose a current agent','',true,true));
  $('#task-form button').disabled = taskPending || !$('#controller').value;
  $('form[data-action="mail.status"] button').disabled = !$('#mail-agent').value || !availableActions.has('mail.status');
  $('#providers').replaceChildren();
  for (const [name, value] of Object.entries(data.providers || {})) {
    const details = document.createElement('details');details.append(element('summary',name),element('pre',JSON.stringify(value,null,2)));$('#providers').append(details);
  }
  $('#capabilities').replaceChildren();
  for (const cap of data.capabilities || []) $('#capabilities').append(element('p',typeof cap === 'string' ? cap : JSON.stringify(cap)));
  $('#updated').textContent = `Reported: ${data.timestamp || 'timestamp unavailable'}`;
}
async function refresh() {
  const token = ++generation;
  const selected = $('#host').value;
  const selectedAgent = renderedHost === selected ? $('#controller').value : '';
  if (renderedHost !== selected) {
    clearStatus('Loading the selected gateway’s agents…');
    document.querySelectorAll('.result').forEach(node => node.textContent = 'Not checked for this workstation.');
    $('#task-result').textContent = 'No task submitted for this workstation.';
  }
  notice('Checking connected workstations…'); $('#refresh').disabled = true;
  try {
    const inventory = await jsonFetch('/api/factory/gateways');
    if (token !== generation) return;
    const hosts = Array.isArray(inventory.gateways) ? inventory.gateways : [];
    $('#host').replaceChildren(...hosts.map(host => new Option(`${host.name || host.id} · connected`, host.id)));
    const present = hosts.some(host => host.id === selected);
    if (present) {$('#host').value = selected; requireSelection = false;}
    else if (selected || !hosts.length || requireSelection) {
      requireSelection = true;
      $('#host').prepend(new Option(hosts.length ? 'Choose a connected workstation' : 'No connected workstations','',true,true));
      clearStatus('The selected workstation is unavailable. Connect a gateway or choose an available workstation.');
      renderedHost = null;
      return notice('Choose a connected workstation. Connections can be managed from the Mesh console.',true);
    }
    const host = $('#host').value;
    clearStatus('Requesting the gateway’s current agents…');
    const data = await jsonFetch(`${hostPath(host)}/factory`);
    if (token !== generation || host !== $('#host').value) return;
    renderedHost = host; renderStatus(data.result || {}, selectedAgent); notice('Live workstation status received.');
  } catch (error) {
    if (token === generation) {clearStatus('Live agent status unavailable. Use Refresh status to try again.');notice(error.message,true);}
  } finally {if(token===generation) $('#refresh').disabled=false;}
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
  if (panel.dataset.busy === 'true' || !liveReady) return;
  panel.dataset.busy = 'true';
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
  finally {delete panel.dataset.busy;updateActionButtons();}
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
  if(taskPending||!liveReady||!host||!agent||!text) return;
  taskPending = true;
  const button=$('#task-form button');button.disabled=true;$('#task-result').textContent='Sending…';
  try {
    const sent=await jsonFetch(`${hostPath(host)}/message`,{method:'POST',body:JSON.stringify({text:`/agent ${agent} ${text}`})});
    if (host !== $('#host').value) return;
    $('#task-result').textContent=`Accepted by ${agent}. Waiting for a correlated response…`;
    for(let attempt=0;attempt<120;attempt++) {
      await new Promise(resolve=>setTimeout(resolve,2000));
      if(host !== $('#host').value) return;
      const events=await jsonFetch(`${hostPath(host)}/events`);
      if(host !== $('#host').value) return;
      const matches=(events.events || []).filter(e=>e.payload?.request_id===sent.request_id && e.type!=='user_message');
      if(matches.length) $('#task-result').textContent=matches.map(e=>e.message || JSON.stringify(e.payload)).join('\n\n');
      if(matches.some(e=>['agent_message','message_response','error'].includes(e.type)||e.payload?.final===true||e.payload?.status==='completed')) return;
    }
    $('#task-result').textContent+='\nLive waiting ended. The task may still be running; open the Mesh conversation for further updates. No duplicate task was submitted.';
  } catch(error) {if (host === $('#host').value) $('#task-result').textContent=error.message;}
  finally {taskPending=false;button.disabled=!liveReady || !$('#controller').value;}
});
$('#controller').addEventListener('change',()=>{$('#task-form button').disabled=taskPending||!liveReady||!$('#controller').value;});
$('#refresh').addEventListener('click',refresh);$('#host').addEventListener('change',refresh);refresh();
setInterval(() => {if (!document.hidden && !$('#refresh').disabled) refresh();}, 30000);
