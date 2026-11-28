// Use the supported authenticated HTTP entry point so OpenClaw owns model
// selection, run admission, timeouts, session persistence and tool policy.
export async function runGatewayConversation(config, {agentId, sessionKey, text}, fetchImpl = fetch) {
  const token = process.env.OPENCLAW_GATEWAY_TOKEN || config?.gateway?.auth?.token;
  if (config?.gateway?.auth?.mode !== "token" || typeof token !== "string" || !token) {
    throw new Error("mesh_gateway_token_auth_required");
  }
  const port = config.gateway.port || 18789;
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("mesh_gateway_port_invalid");
  const seconds = config.agents?.defaults?.timeoutSeconds || 600;
  const response = await fetchImpl(`http://127.0.0.1:${port}/v1/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
      "x-openclaw-session-key": sessionKey,
      "x-openclaw-message-channel": "mesh",
    },
    body: JSON.stringify({model: `openclaw/${agentId}`, stream: false, messages: [{role: "user", content: text}]}),
    signal: AbortSignal.timeout(Math.min(Math.max(seconds, 30), 3600) * 1000 + 15000),
    redirect: "error",
  });
  // Do not echo upstream bodies: they may contain credential or prompt material.
  if (!response.ok) throw new Error(`mesh_gateway_http_${response.status}`);
  const data = await response.json();
  const content = data?.choices?.[0]?.message?.content;
  if (typeof content !== "string" || !content.trim()) throw new Error("mesh_gateway_empty_response");
  return {payloads: [{text: content}]};
}
