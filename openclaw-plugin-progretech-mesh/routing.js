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
  if (Object.hasOwn(body, 'target_agent') &&
      (typeof body.target_agent !== 'string' || !Object.hasOwn(aliases, body.target_agent.toLowerCase()))) {
    throw new Error('unknown_agent');
  }
  let requested = String(body.target_agent || body.agent_id || defaultAgent).toLowerCase();
  const command = text.match(/^\/agent\s+([a-z0-9_-]+)\s+([\s\S]+)$/i);
  if (command) [, requested, text] = command;
  else if (/^\/agent(?:\s|$)/i.test(text)) throw new Error("usage: /agent <rend|mak|lyra|progre|imagen|odexi> <message>");
  const agentId = aliases[requested.toLowerCase()];
  if (!agentId || !Object.hasOwn(config?.agents?.entries || {}, agentId)) throw new Error("unknown_agent");
  return { agentId, text };
}
