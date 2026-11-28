export function parseIdentities(text) {
  if (text.length > 2 * 1024 * 1024 || /-----BEGIN [A-Z ]*PRIVATE KEY-----/.test(text)) throw Error('Import public identity bundles only. Private keys must stay on the host.');
  const value = JSON.parse(text);
  const rows = Array.isArray(value) ? value : [value];
  if (!rows.length || rows.length > 256) throw Error('Import between 1 and 256 identities.');
  const ids = new Set();
  return rows.map(row => {
    const identity = row?.codeseal_evidence?.manifest?.mesh_identity;
    if (!row || typeof row.name !== 'string' || !row.name.trim() || row.name.length > 80
        || typeof row.gateway_id !== 'string' || !/^[A-Za-z0-9_-]{1,80}$/.test(row.gateway_id)
        || typeof row.agent_id !== 'string' || !/^[A-Za-z0-9_-]{1,80}$/.test(row.agent_id)
        || !row.agent_id.startsWith(row.gateway_id + '--') || row.gateway_candidate_id !== row.agent_id
        || typeof row.public_key !== 'string' || row.public_key.length > 4096
        || identity?.agent_id !== row.agent_id || identity?.agent_name !== row.name
        || identity?.public_key?.trim() !== row.public_key.trim() || ids.has(row.agent_id)
        || typeof row.codeseal_evidence.registry_signature !== 'string'
        || typeof row.codeseal_evidence.registry_public_key !== 'string') throw Error('Each bundle must contain a distinct gateway role and its matching signed public identity.');
    ids.add(row.agent_id);
    return {agent_id:row.agent_id,name:row.name,role:typeof row.role === 'string' ? row.role : '',
      gateway_id:row.gateway_id,gateway_candidate_id:row.gateway_candidate_id,
      public_key:row.public_key,codeseal_evidence:row.codeseal_evidence};
  });
}

export async function enrollIdentities(rows, request, progress) {
  const response = await request('/api/agents');
  const fleet = await response.json();
  if (!response.ok || !Array.isArray(fleet.agents)) throw Error('Sign in to Mesh before enrolling.');
  let count = 0;
  for (const identity of rows) {
    const existing = fleet.agents.find(a => a.id === identity.agent_id);
    if (!(existing?.gateway_enrollment && existing.owner_bound && existing.trust_state === 'verified'
        && existing.control_center_gateway === identity.gateway_id && existing.public_key?.trim() === identity.public_key.trim())) {
      const added = await request('/api/agents/enroll', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(identity)});
      const body = await added.json();
      if (!added.ok || body.agent?.trust_state !== 'verified') throw Error(`${identity.name}: ${body.error || 'Identity verification failed'}`);
    }
    count++;
    progress(count, rows.length, identity.name);
  }
  return count;
}

if (typeof document !== 'undefined') {
  const file = document.getElementById('preparedIdentityFile');
  const button = document.getElementById('enrollPreparedIdentities');
  const status = document.getElementById('preparedIdentityStatus');
  const list = document.getElementById('preparedIdentityList');
  let rows = [];
  file?.addEventListener('change', async () => {
    rows = []; button.disabled = true; list.replaceChildren();
    try {
      const chosen = file.files[0];
      if (!chosen) return;
      if (chosen.size > 2 * 1024 * 1024) throw Error('Identity bundle is too large.');
      rows = parseIdentities(await chosen.text());
      for (const row of rows) {
        const item = document.createElement('li'); item.textContent = `${row.name} · ${row.agent_id}`; list.append(item);
      }
      button.textContent = `Verify and enroll ${rows.length} ${rows.length === 1 ? 'agent' : 'agents'}`;
      button.disabled = false; status.textContent = 'Review these identities before enrolling them in this account.';
    } catch (error) { status.textContent = error.message; }
  });
  button?.addEventListener('click', async () => {
    if (!rows.length || button.disabled) return;
    button.disabled = true; file.disabled = true;
    try {
      const count = await enrollIdentities(rows, fetch, (done,total,name) => { status.textContent = `${done} of ${total} enrolled · ${name}`; });
      status.textContent = `${count} signed agents enrolled. Close this dialog to see the fleet.`;
    } catch (error) { status.textContent = error.message; }
    finally {
      button.disabled = false; file.disabled = false;
      window.dispatchEvent(new Event('mesh-enrollment-completed'));
    }
  });
}
