const AGENT_NAMES = Object.freeze({
  main: "Rend",
  coder: "Mak",
  researcher: "Lyra",
  progre: "Progre",
  imagen: "Imagen",
  codex: "Odexi",
  moxy: "Moxy",
});

function normalized(text) {
  return String(text || "")
    .trim()
    .toLowerCase()
    .replace(/[!?.,]+$/g, "")
    .replace(/\s+/g, " ");
}

export function quickPresenceIntent(text) {
  const value = normalized(text);
  if (!value || value.length > 120) return null;
  if (/^(hi|hello|hey|good (morning|afternoon|evening))( there)?(?: [a-z][a-z0-9_-]*)?$/.test(value)) {
    return "greeting";
  }
  if (/^(hi|hello|hey)( there)?(?: [a-z][a-z0-9_-]*)?[,:]? (are you (working|busy)( on anything)?|what are you working on|what is your (current )?status)$/.test(value)) {
    return "status";
  }
  if (/^(are you (working|busy)( on anything)?|what are you working on|what is your (current )?status|current status|status)$/.test(value)) {
    return "status";
  }
  return null;
}

export function buildQuickPresenceReply(text, { agentId, activeRuns = 0 } = {}) {
  const intent = quickPresenceIntent(text);
  if (!intent) return null;
  const name = AGENT_NAMES[agentId] || "I";
  if (intent === "greeting") return `Hi Edwin — ${name} is here and ready.`;
  if (activeRuns > 0) {
    return `Yes — I have ${activeRuns} other active ${activeRuns === 1 ? "run" : "runs"} in progress. I’m responsive here too.`;
  }
  return "I’m online and responsive. I don’t have another active run in progress right now.";
}
