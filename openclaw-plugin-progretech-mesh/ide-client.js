import {createHash, randomUUID} from 'node:crypto';

const FIELDS = new Set(['model','messages','stream','temperature','top_p','max_tokens','max_completion_tokens',
  'tools','tool_choice','parallel_tool_calls','response_format','seed','user','stop','presence_penalty','frequency_penalty']);

export async function forwardRoleCompletion(config, body, fetchImpl = fetch, options = {}) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error('ide_invalid_request');
  const target = options.target;
  const validId = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(value);
  const runtimeValid = typeof target?.runtime_id === 'string' && /^[A-Za-z0-9_.-]{1,128}$/.test(target.runtime_id);
  const suffix = runtimeValid ? (/^[A-Za-z0-9_-]{1,28}$/.test(target.runtime_id) ? target.runtime_id : 'role_' + createHash('sha256').update(target.runtime_id).digest('hex').slice(0,24)) : '';
  const isHost = target?.agent_id === target?.gateway_id;
  const models = isHost ? [target?.agent_id] : [target?.agent_id, `${target?.agent_id}-code`];
  if (!target || typeof target !== 'object' || Array.isArray(target)
      || Object.keys(target).sort().join(',') !== 'agent_id,gateway_id,runtime_id'
      || !validId(target.agent_id) || !validId(target.gateway_id) || !runtimeValid
      || target.gateway_id !== options.gatewayId
      || (!isHost && target.agent_id !== `${target.gateway_id}--${suffix}`)
      || !models.includes(body.model)) {
    throw new Error('ide_role_binding_invalid');
  }
  const local = Array.isArray(options.agents) && options.agents.find(item =>
    item?.id === target.agent_id && item?.runtime_id === target.runtime_id
    && item.office_worker !== true && item.office_archived !== true);
  if (!local) throw new Error('ide_role_binding_unavailable');
  const agentId = target.runtime_id;
  if (!Object.hasOwn(config?.agents?.entries || {}, agentId)) throw new Error('ide_role_not_available');
  if (Object.keys(body).some(key => !FIELDS.has(key))) throw new Error('ide_unsupported_parameter');
  if (!Array.isArray(body.messages) || !body.messages.length || JSON.stringify(body).length > 1048576) throw new Error('ide_invalid_messages');
  const token = config?.gateway?.auth?.token || process.env.OPENCLAW_GATEWAY_TOKEN;
  if (config?.gateway?.auth?.mode !== 'token' || typeof token !== 'string' || !token) throw new Error('ide_gateway_token_auth_required');
  const port = config.gateway.port || 18789;
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('ide_gateway_port_invalid');
  const user = typeof body.user === 'string' ? body.user : '';
  const session = user ? createHash('sha256').update(user).digest('hex').slice(0,32) : randomUUID();
  const timeoutMs = options.timeoutMs ?? 140000;
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 145000) throw new Error('ide_timeout_invalid');
  let response;
  try {
    response = await fetchImpl(`http://127.0.0.1:${port}/v1/chat/completions`, {
      method:'POST', redirect:'error', signal:AbortSignal.timeout(timeoutMs),
      headers:{'Content-Type':'application/json','Authorization':`Bearer ${token}`,
        'x-openclaw-agent-id':agentId,'x-openclaw-message-channel':'mesh',
        'x-openclaw-session-key':`agent:${agentId}:mesh-api:${session}`},
      body:JSON.stringify({...body, model:`openclaw/${agentId}`, stream:false}),
    });
  } catch (error) {
    throw new Error(error?.name === 'TimeoutError' || error?.name === 'AbortError' ? 'ide_gateway_timeout' : 'ide_gateway_unreachable');
  }
  // Never include an upstream response body, URL, credential, or prompt in errors.
  if (!response.ok) throw new Error(`ide_gateway_http_${response.status}`);
  let completion;
  try { completion = await response.json(); } catch { throw new Error('ide_gateway_invalid_json'); }
  if (!completion || !Array.isArray(completion.choices) || !completion.choices.length || !completion.choices[0]?.message) throw new Error('ide_gateway_invalid_completion');
  return {...completion, model:body.model};
}
