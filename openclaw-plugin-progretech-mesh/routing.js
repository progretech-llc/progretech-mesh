const aliases = Object.freeze({
  rend: "main", main: "main", mak: "coder", coder: "coder",
  lyra: "researcher", researcher: "researcher", progre: "progre", imagen: "imagen", codex: "codex", odexi: "codex",
});

// Mesh owns authenticated ingress; this adapter only selects configured roles.
// Never turn an arbitrary request field into a workspace path or model override.
export function meshConversationBody(body, enrolledAgent, transport) {
  return {
    agent_id: enrolledAgent || body?.agent_id || 'rend',
    ...(Object.hasOwn(body || {}, 'target_agent') ? {target_agent: body.target_agent} : {}),
    text: body?.text, room: body?.room || 'direct', sender: body?.sender || 'Mesh user', transport,
  };
}

export function resolveMeshTarget(body, config, defaultAgent = "rend") {
  if (typeof body?.text !== "string" || !body.text.trim()) throw new Error("empty_message");
  if (body.text.length > 32000) throw new Error("message_too_long");
  let text = body.text.trim();
  const entries = config?.agents?.entries || {};
  const configured = value => typeof value === 'string' && /^[A-Za-z0-9_.-]{1,128}$/.test(value)
    ? (Object.hasOwn(entries, value) ? value : Object.hasOwn(aliases, value.toLowerCase()) ? aliases[value.toLowerCase()] : null) : null;
  if (Object.hasOwn(body, 'target_agent') && !configured(body.target_agent)) {
    throw new Error('unknown_agent');
  }
  let requested = String(body.target_agent || body.agent_id || defaultAgent);
  const command = text.match(/^\/agent\s+([A-Za-z0-9_.-]{1,128})\s+([\s\S]+)$/);
  if (command) [, requested, text] = command;
  else if (/^\/agent(?:\s|$)/i.test(text)) throw new Error("usage: /agent <configured-agent-id> <message>");
  const agentId = configured(requested);
  if (!agentId || !Object.hasOwn(config?.agents?.entries || {}, agentId)) throw new Error("unknown_agent");
  return { agentId, text };
}
