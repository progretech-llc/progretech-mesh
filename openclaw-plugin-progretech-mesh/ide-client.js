import {createHash, randomUUID} from 'node:crypto';

export const IDE_ROLE_ALIASES = Object.freeze({
  rend:'main', lyra:'researcher', mak:'coder', progre:'progre',
  imagen:'imagen', codex:'codex', odexi:'codex',
  'rend-code':'coder',
  'rend-research':'researcher',
});
const FIELDS = new Set(['model','messages','stream','temperature','top_p','max_tokens','max_completion_tokens',
  'tools','tool_choice','parallel_tool_calls','response_format','seed','user','stop','presence_penalty','frequency_penalty']);

export async function forwardRoleCompletion(config, body, fetchImpl = fetch, options = {}) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error('ide_invalid_request');
  const agentId = IDE_ROLE_ALIASES[body.model];
  if (!agentId || !Object.hasOwn(config?.agents?.entries || {}, agentId)) throw new Error('ide_role_not_available');
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
