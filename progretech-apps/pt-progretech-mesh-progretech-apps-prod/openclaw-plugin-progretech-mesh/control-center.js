const actions = new Set('context.read specklet.get specklet.toggle specklet.import specklet.task memory.status memory.share memory.search chatter.encounter chatter.configure chatter.history chatter.pair chatter.group chatter.topic handoff.create handoff.list handoff.control files.begin files.chunk files.finish files.cancel files.list files.read files.reference communication.get communication.save communication.chat communication.start communication.job communication.new runtime.status runtime.wake runtime.sleep runtime.snapshot runtime.context runtime.recover enrollment.remove factory.providers factory.run factory.job factory.office profile.get profile.save voice.preview host.system models.list audio.get audio.set voice.get voice.start voice.stop vision.get vision.analyze skills.list mail.status orchestration.status harness.status grid.status vllm.status chatter.get chatter.settings chatter.test'.split(' '));

export async function forwardControlCenter(payload, agentId, token, fetchImpl = fetch) {
  if (!payload || !actions.has(payload.action)) throw new Error('action_not_allowed');
  if (!/^[A-Za-z0-9_-]{1,80}$/.test(agentId || '')) throw new Error('agent_binding_required');
  const args = payload.args ?? {};
  if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error('invalid_args');
  if (!token) throw new Error('local_auth_missing');
  // The authenticated gateway bounds every target to its own approved namespace.
  // The local provider further requires an exact administrator-owned binding.
  const target = typeof payload.agent_id === 'string' ? payload.agent_id : agentId;
  if (target !== agentId && (!target.startsWith(`${agentId}--`) || !/^[A-Za-z0-9_-]{1,80}$/.test(target))) throw new Error('agent_binding_required');
  const body = JSON.stringify({agent_id: target, action: payload.action, args});
  if (body.length > (payload.action.startsWith('specklet.') ? 550000 : payload.action.startsWith('files.') ? 65536 : 16384)) throw new Error('request_too_large');
  const response = await fetchImpl('http://127.0.0.1:8787/api/mesh/control-center', {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-ProgreTech-Mesh-Local-Token': token},
    body, redirect: 'error', signal: AbortSignal.timeout(payload.action === 'communication.chat' ? 310000 : 43000)
  });
  const data = await response.json();
  if (!response.ok && data.ok !== false) throw new Error(`local_control_http_${response.status}`);
  return data;
}

export async function discoverControlAgents(agentId, token, fetchImpl = fetch) {
  if (!token || !/^[A-Za-z0-9_-]{1,80}$/.test(agentId || '')) return null;
  const response = await fetchImpl(`http://127.0.0.1:8787/api/mesh/control-center/agents?gateway_id=${encodeURIComponent(agentId)}`, {
    headers: {'X-ProgreTech-Mesh-Local-Token': token}, redirect: 'error', signal: AbortSignal.timeout(17000)
  });
  if (!response.ok) return null;
  const data = await response.json();
  if (!Array.isArray(data.agents) || data.agents.length > 256) return null;
  return data.agents.filter(item => typeof item?.id === 'string' && (item.id === agentId || item.id.startsWith(`${agentId}--`)));
}
