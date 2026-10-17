/* Owner-selected agent identity is fixed for the lifetime of this page. */
(() => {
  'use strict';
  const root = document.getElementById('controlCenter');
  if (!root) return;
  const form = document.getElementById('ccProfile');
  const status = document.getElementById('ccStatus');
  const field = (name) => form.elements.namedItem(name);
  const endpoint = `/api/agents/${encodeURIComponent(root.dataset.agentId)}/control-center`;
  let saved = null;
  let capabilities = new Set();
  let busy = false;
  let connected = root.dataset.connected === 'true';
  let statusPending = false;
  let hostProfileLoaded = false;
  const notify = (message, error = false) => { status.textContent = message; status.classList.toggle('error', error); };

  function updateControls() {
    const custom = field('provider').value === 'custom';
    document.getElementById('ccCustomVoice').hidden = !custom;
    field('customProvider').required = custom; field('customVoice').required = custom;
    document.getElementById('ccWorkstation').hidden = field('workstation').value !== 'yes';
    for (const button of document.querySelectorAll('[data-capability]')) {
      const hostControl = button.closest('#ccWorkstation');
      const permitted = saved?.permissions.includes(button.dataset.grant);
      const hostPermitted = !hostControl || (saved?.workstation === 'yes' && saved.permissions.includes('workstation'));
      button.disabled = busy || !connected || !capabilities.has(button.dataset.capability) || !permitted || !hostPermitted;
      button.title = button.disabled ? 'Requires a connected provider, advertised capability, and saved permissions.' : '';
    }
    form.querySelector('[type=submit]').disabled = busy || !connected;
    document.getElementById('ccRefresh').disabled = busy;
  }

  async function requestControl(action, args = {}) {
    const response = await fetch(endpoint, {
      method: 'POST', headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
      body: JSON.stringify({action, args}), signal: AbortSignal.timeout(52000)
    });
    if (response.status === 401) throw new Error('Your Mesh session expired. Sign in again.');
    const data = await response.json();
    if (!response.ok || data.ok !== true) throw new Error(`${data.error || 'Control unavailable'}${data.detail ? `: ${data.detail}` : ''}`);
    return data.result;
  }

  async function run(task) {
    if (busy) return;
    busy = true; updateControls();
    try { await task(); }
    catch (error) { notify(error.name === 'TimeoutError' ? 'No reply yet. The action may still finish; load settings before retrying.' : error.message, true); }
    finally { busy = false; updateControls(); }
  }

  function paragraph(text) { const node = document.createElement('p'); node.textContent = text; return node; }
  function render(data) {
    saved = data.profile;
    if (!saved || !Array.isArray(saved.permissions) || !saved.voice) throw new Error('The provider returned an incompatible profile.');
    capabilities = new Set(data.capabilities || []);
    for (const key of ['role', 'workstation', 'stack']) field(key).value = saved[key];
    field('models').value = (saved.models || []).join('\n');
    field('provider').value = ['kokoro', 'piper'].includes(saved.voice.provider) ? saved.voice.provider : 'custom';
    field('customProvider').value = saved.voice.provider;
    field('customVoice').value = saved.voice.voice;
    field('voice').value = saved.voice.voice;
    field('pitch').value = saved.voice.pitch;
    for (const input of form.querySelectorAll('[name=permission]')) input.checked = saved.permissions.includes(input.value);
    const discovered = data.discovered || {};
    const inventory = document.getElementById('ccInventory');
    inventory.replaceChildren(
      paragraph(`Runtime role: ${discovered.role || 'Not reported / inventory permission needed'}`),
      paragraph(`Configured model access: ${(discovered.models || []).join(', ') || 'Not reported'}`),
      paragraph(`User-supplied role: ${saved.role || 'Not supplied'}`),
      paragraph(`User-supplied models: ${(saved.models || []).join(', ') || 'Not supplied'}`),
      paragraph(discovered.models_meaning || 'User-supplied details do not change runtime model routing or role instructions.')
    );
    updateControls();
  }

  async function load() {
    notify('Loading this agent’s local profile…');
    render(await requestControl('profile.get'));
    hostProfileLoaded = true;
    notify('Agent settings loaded. Controls require saved grants and a supported local capability.');
  }
  async function syncStatus() {
    if (statusPending) return;
    statusPending = true;
    const wasConnected = connected;
    try {
      const response = await fetch('/api/status', {signal: AbortSignal.timeout(10000)});
      if (!response.ok) throw Error('Unable to check gateway status. Sign in again if your session expired.');
      const data = await response.json();
      const agent = data.agents?.find(item => item.id === root.dataset.agentId);
      connected = agent?.transport === 'connected' && agent?.control_center_available === true;
      document.getElementById('ccConnection').textContent = connected ? 'Gateway connected' : 'Gateway offline or unavailable';
      document.getElementById('ccRuntime').textContent = agent ? MeshRuntime.indicator(agent).label : 'Agent unavailable';
      if (connected && !wasConnected && !hostProfileLoaded && !busy) await run(load);
    } catch (error) {
      connected = false;
      document.getElementById('ccConnection').textContent = 'Gateway status unavailable';
      document.getElementById('ccRuntime').textContent = 'Activity unknown';
    } finally { statusPending = false; updateControls(); }
  }
  document.getElementById('ccRefresh').addEventListener('click', () => run(async () => { await syncStatus(); if (connected) await load(); else notify('Connect this gateway from the agent fleet, then load settings again.', true); }));
  const statusTimer = setInterval(syncStatus, 4000);
  window.addEventListener('pagehide', () => clearInterval(statusTimer));
  syncStatus();
  field('workstation').addEventListener('change', updateControls);
  field('provider').addEventListener('change', () => { field('voice').value = field('provider').value === 'piper' ? 'current' : 'am_onyx'; updateControls(); });
  document.getElementById('ccDefaults').addEventListener('click', () => {
    field('provider').value = 'kokoro'; field('voice').value = 'am_onyx'; field('pitch').value = '4';
    updateControls();
    notify('Rend’s reference voice copied into this form. Save to apply it to this agent’s preview profile.');
  });
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const profile = {
      role: field('role').value.trim(), models: field('models').value.split('\n').map((s) => s.trim()).filter(Boolean),
      workstation: field('workstation').value, stack: field('stack').value,
      voice: {provider: field('provider').value === 'custom' ? field('customProvider').value.trim() : field('provider').value,
              voice: field('provider').value === 'custom' ? field('customVoice').value.trim() : field('voice').value, pitch: Number(field('pitch').value)},
      permissions: Array.from(form.querySelectorAll('[name=permission]:checked'), (input) => input.value)
    };
    run(async () => {
      notify('Saving this agent’s setup on its host…');
      await requestControl('profile.save', profile);
      await load(); notify('Agent setup saved. Voice previews use this profile; continuous speech requires runtime support.');
    });
  });
  document.getElementById('ccPreview').addEventListener('submit', (event) => {
    event.preventDefault();
    run(async () => {
      notify('Playing the saved agent voice on the host speaker…');
      const result = await requestControl('voice.preview', {text: event.target.elements.namedItem('text').value});
      document.getElementById('ccPreviewResult').textContent = JSON.stringify(result, null, 2);
      notify('Voice preview completed.');
    });
  });
  for (const button of document.querySelectorAll('[data-action]')) button.addEventListener('click', () => {
    if (button.disabled || (button.dataset.confirm && !window.confirm(button.dataset.confirm))) return;
    run(async () => {
      notify('Waiting for the selected agent’s workstation…');
      const target = button.closest('#ccWorkstation') ? 'ccHostResult' : 'ccAgentResult';
      document.getElementById(target).textContent = JSON.stringify(await requestControl(button.dataset.action), null, 2);
      notify('Workstation response received.');
    });
  });
  document.getElementById('ccChatter').addEventListener('submit', (event) => {
    event.preventDefault();
    if (event.target.querySelector('[type=submit]').disabled || !window.confirm('Change shared workstation spoken activity updates?')) return;
    const args = {enabled: event.target.elements.enabled.checked, quiet: event.target.elements.quiet.checked};
    run(async () => {
      document.getElementById('ccHostResult').textContent = JSON.stringify(await requestControl('chatter.settings', args), null, 2);
      notify('Shared chatter settings saved.');
    });
  });
  for (const [id, action, warning] of [
    ['ccAudio', 'audio.set', 'Change the shared workstation microphone and speaker routing?'],
    ['ccVision', 'vision.analyze', 'Capture and analyze one observation from the shared workstation visual source?']
  ]) document.getElementById(id).addEventListener('submit', (event) => {
    event.preventDefault();
    if (event.target.querySelector('[type=submit]').disabled || !window.confirm(warning)) return;
    const args = Object.fromEntries(new FormData(event.target));
    run(async () => {
      document.getElementById('ccHostResult').textContent = JSON.stringify(await requestControl(action, args), null, 2);
      notify('Workstation action completed.');
    });
  });
  if (root.dataset.savedProfile && root.dataset.savedProfile !== 'null') {
    try { render({profile: JSON.parse(root.dataset.savedProfile), capabilities: []}); } catch { /* Host refresh can replace an older saved profile. */ }
  }
  updateControls();
  if (!connected) notify('This agent is offline or unverified. Setup guidance is available; connect its verified gateway to save settings.', true);
  else run(load);
})();
