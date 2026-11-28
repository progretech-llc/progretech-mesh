(() => {
  const modal = document.createElement('dialog');
  modal.className = 'onboarding-dialog';
  modal.setAttribute('aria-labelledby', 'onboardingTitle');
  modal.innerHTML = `<div class="modal-head"><h2 id="onboardingTitle">Connect a gateway</h2><button type="button" data-close aria-label="Close onboarding">×</button></div>
    <form data-consent><label>Connection<select name="connection"><option value="gateway">Connect a workstation</option><option value="runtime">Add a tool</option></select></label><label data-host hidden>Connected workstation<select name="gateway"></select></label><label>Platform<select name="platform" required><option value="hermes">Hermes profiles</option><option value="opencode">OpenCode agents</option><option value="codex">Codex profile</option><option value="harness">OpenHarness session</option><option value="openwebui">Open WebUI models / workspaces</option><option value="openai">Ollama or another OpenAI-compatible API</option><option value="openclaw">OpenClaw gateway</option></select></label>
    <label><span data-name-label>Computer / gateway name</span><input name="name" maxlength="80" required autocomplete="off" placeholder="e.g. Office workstation"></label>
    <p data-gateway-copy>Give the prompt to your authorized agent on that computer. It installs the connector using Python and Node.js, discovers its team and becomes the initial Scrum Master.</p>
    <p data-gateway-copy><strong>One active gateway per account.</strong> Connecting replaces the previous gateway. Change Scrum Master later from the fleet or Factory. Tools and execution depend on your platform; a model API alone provides inference.</p>
    <p data-runtime-copy hidden>Add one existing agent, profile or session. Other tools stay connected, and your Scrum Master selection stays in place.</p>
    <label><input type="checkbox" name="hosted" required> I own this hosted agent or am authorized to connect it and configure the integration.</label>
    <label><input type="checkbox" name="terms" required> Mesh is an intermediary. I remain responsible for my agent’s instructions and actions; ProgreTech does not operate it or guarantee its results.</label>
    <button class="primary-btn">Generate setup prompt</button></form>
    <section data-connect hidden><textarea data-prompt readonly rows="9" aria-label="Agent connection prompt"></textarea><button type="button" data-copy class="primary-btn">Copy prompt</button>
    <p><span class="onboarding-pulse" data-pulse aria-hidden="true"></span> <span data-connection>Waiting for agent connection</span></p>
    <form data-question hidden><label>Ask your agent to identify itself<textarea name="text" maxlength="1000" required>Identify yourself: what is your name, role and runtime, and are you awake and ready to work?</textarea></label><button class="ghost-btn" disabled>Send question</button></form>
    <pre data-answer hidden></pre><div data-confirm-area hidden><p>Automatic identity verification needs attention. Its private key stays on its host.</p>
    <details><summary>Use my CodeSeal account</summary><label>CodeSeal API token<input type="password" data-token autocomplete="off" placeholder="ptcs_live_…"></label><small>Only needed when automatic issuance is unavailable. Cleared after submission.</small></details><button type="button" data-confirm class="primary-btn">Confirm identity & finish</button></div>
    <button type="button" data-cancel class="ghost-btn">Cancel invitation</button></section><p data-status role="status" aria-live="polite"></p>`;
  document.body.append(modal);
  const q = s => modal.querySelector(s);
  let id = null, timer = null, busy = false, opener = null, completed = false, runtimeMode = false;
  const status = text => { q('[data-status]').textContent = text; };
  async function api(path, body) {
    const response = await fetch((runtimeMode ? '/api/runtime-enrollment' : '/api/onboarding') + path, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok || !data.ok) throw Error(data.error || 'Connection unavailable');
    return data;
  }
  function stop() { clearInterval(timer); timer = null; }
  async function poll() {
    if (!id || busy) return;
    busy = true;
    try {
      const data = await api('/' + id);
      if (runtimeMode) {
        if(data.state==='authorized') { q('[data-connection]').textContent='Configuring native tool'; status('Authorization verified. Waiting for the workstation to save and acknowledge its configuration.'); }
        if (data.state === 'complete') {
          completed = true; stop(); q('[data-cancel]').hidden = true;
          q('[data-connection]').textContent = 'Native tool registered';
          status('Your workstation will refresh its roster shortly. Select the Scrum Master in Factory.');
          window.dispatchEvent(new Event('mesh-enrollment-completed'));
        } else if (['expired', 'cancelled'].includes(data.state)) { completed = true; stop(); status('Invitation ' + data.state + '. Close and start again.'); }
        return;
      }
      q('[data-pulse]').classList.toggle('connected', data.connected);
      q('[data-connection]').textContent = data.connected ? 'Agent connected to onboarding' : 'Waiting for agent connection';
      q('[data-question] button').disabled = !data.connected || data.state !== 'connected';
      if (data.answer) { q('[data-answer]').hidden = false; q('[data-answer]').textContent = data.answer; }
      if (!data.automatic && data.state === 'connected' && data.connected) {
        await api('/' + id + '/question', {text: q('[data-question] textarea').value});
        status('Your agent is identifying its gateway…');
      }
      if (data.state === 'question') status('Question sent. Waiting for your agent’s reply.');
      if (!data.automatic && data.state === 'answered') { status('Verifying gateway identity and linking your account…'); await api('/' + id + '/confirm', {}); }
      if (data.error) throw Error(data.error);
      if (data.state === 'expired' || data.state === 'cancelled') { completed = true; stop(); status('Invitation ' + data.state + '. Close and start again.'); }
      if (data.state === 'complete') {
        q('[data-confirm-area]').hidden = true; q('[data-cancel]').hidden = true;
        const response = await fetch('/api/status');
        if (!response.ok) throw Error('Unable to check gateway status. Sign in again if your session expired.');
        const fleet = await response.json();
        if (fleet.agents?.some(agent => agent.id === data.agent_id && agent.transport === 'connected')) {
          completed = true; stop(); q('[data-connection]').textContent = 'Gateway connected'; status('Your agents are ready. Open Mission Control to inspect configuration, add a task in Factory, or copy API relay setup from an agent card for your IDE.');
          window.dispatchEvent(new Event('mesh-enrollment-completed'));
        } else status('Identity saved to your account. Your agent is finishing the gateway connection…');
      }
    } catch (e) { if(e.message === 'onboarding_not_found') completed = true; q('[data-pulse]').classList.remove('connected'); q('[data-question] button').disabled = true; if ((e.message.startsWith('codeseal_') || e.message.startsWith('account_security_'))) { q('[data-confirm-area]').hidden = false; stop(); } status(e.message); }
    finally { busy = false; }
  }
  window.MeshOnboarding = {async open() { if (completed) { id = null; completed = false; q('[data-consent]').hidden = false; q('[data-consent]').reset(); q('[data-connect]').hidden = true; q('[data-answer]').hidden = true; q('[data-confirm-area]').hidden = true; q('[data-cancel]').hidden = false; q('[data-prompt]').value = ''; q('[data-pulse]').classList.remove('connected'); status(''); } opener = document.activeElement; modal.showModal();
    if (!id) {
      try {
        const response = await fetch('/api/runtime-enrollment/hosts');
        if (!response.ok) throw Error('Unable to load connected workstations. Sign in and retry.');
        const data = await response.json(); const field = q('[name=gateway]'); field.replaceChildren();
        for (const host of data.hosts || []) { const option = document.createElement('option'); option.value = host.id; option.textContent = host.name; field.append(option); }
        q('[name=connection] option[value=runtime]').disabled = !field.options.length;
        q('[name=connection]').value = field.options.length ? 'runtime' : 'gateway';
        updateMode();
      } catch(e) { status(e.message); }
    }
 if (id) { stop(); timer = setInterval(poll, 2000); poll(); } (id ? q('[data-copy]') : q('[data-consent] input')).focus(); }};
  function updateMode() {
    const adding = q('[name=connection]').value === 'runtime';
    q('[data-host]').hidden = !adding; q('[name=gateway]').required = adding;
    q('[data-runtime-copy]').hidden = !adding;
    modal.querySelectorAll('[data-gateway-copy]').forEach(el => { el.hidden = adding; });
    q('[data-name-label]').textContent = adding ? 'Agent / tool name' : 'Computer / gateway name';
    q('#onboardingTitle').textContent = adding ? 'Connect a tool' : 'Connect a gateway';
    q('[name=name]').placeholder = adding ? 'e.g. Imagen' : 'e.g. Office workstation';
    for (const option of q('[name=platform]').options) option.disabled = adding && ['openai', 'openwebui'].includes(option.value);
    if (q('[name=platform] option:checked').disabled) q('[name=platform]').value = 'hermes';
  }
  q('[name=connection]').onchange = updateMode;
  q('[data-close]').onclick = () => modal.close();
  modal.addEventListener('close', () => { if (completed) stop(); opener?.focus(); });
  q('[data-consent]').onsubmit = async event => {
    event.preventDefault(); const form = event.target; form.querySelector('button').disabled = true;
    try { runtimeMode = form.elements.connection.value === 'runtime'; const data = await api('', {auto_connect: true, gateway: form.elements.gateway.value, platform: form.elements.platform.value, name: form.elements.name.value, personally_hosted: form.elements.hosted.checked, accept_intermediary: form.elements.terms.checked}); id = data.id; form.hidden = true; q('[data-connect]').hidden = false; q('[data-prompt]').value = data.prompt; status('Paste this into your authorized agent’s existing chat on the selected computer. Keep this window open to see progress. Invitation expires in 15 minutes.'); stop(); timer = setInterval(poll, 2000); }
    catch(e) { status(e.message); } finally { form.querySelector('button').disabled = false; }
  };
  q('[data-copy]').onclick = async () => { try { await navigator.clipboard.writeText(q('[data-prompt]').value); status('Prompt copied. Paste it into your agent’s existing chat.'); } catch { q('[data-prompt]').select(); status('Press Ctrl+C to copy the selected prompt.'); } };
  q('[data-question]').onsubmit = async event => { event.preventDefault(); event.target.querySelector('button').disabled = true; try { await api('/' + id + '/question', {text: event.target.elements.text.value}); await poll(); } catch(e) { status(e.message); } };
  q('[data-confirm]').onclick = async () => { q('[data-confirm]').disabled = true; try { await api('/' + id + '/confirm', {api_token: q('[data-token]').value || undefined}); stop(); timer = setInterval(poll, 2000); await poll(); } catch(e) { status(e.message === 'codeseal_issuer_not_configured' ? 'Automatic CodeSeal issuance is not configured. Open “Use my CodeSeal account” and enter your API token, then retry.' : e.message); } finally { q('[data-token]').value = ''; q('[data-confirm]').disabled = false; } };
  q('[data-cancel]').onclick = async () => { try { await api('/' + id + '/cancel', {}); stop(); id = null; q('[data-consent]').hidden = false; q('[data-connect]').hidden = true; q('[data-answer]').hidden = true; q('[data-prompt]').value = ''; status('Invitation cancelled.'); } catch(e) { status(e.message); } };
})();
