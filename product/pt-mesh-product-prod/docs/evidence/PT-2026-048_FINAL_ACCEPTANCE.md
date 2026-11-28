# PT-2026-048 — Final Acceptance

Status: QUALIFIED / CLOSED
Date: 2026-09-22

Accepted outcomes:
- explicit owner→agent authorization foundation qualified;
- Rend migrated to an owner-bound Mesh credential;
- remote browser access to `mesh.progretech.com` accepted outside the local LAN through VPN;
- CodeSeal + Ed25519 identity remained verified;
- Cloud Run WebSocket contract fixed at max instances 1 and timeout 3600 seconds;
- transient direct-path negotiation and browser-monitor reconnect behavior hardened;
- OpenAI-compatible IDE relay added at `https://mesh.progretech.com/v1`;
- PTMIDE1 bearer credentials bind IDE access to the authenticated owner and specific agent;
- local Rend IDE Gateway remained the governed model/runtime surface;
- no public exposure of local port 8766 or Ollama;
- work-computer PyCharm acceptance passed using model alias `rend-code`;
- a real Python coding response was returned through the remote Mesh relay.

Key commits:
- ownership foundation: `90725d715a7ad74e98f06f4dcb7c9c039b838e4f`
- Gate 1 closeout: `ee59e3f1e293d8eb2c290ad3e5577784bc42da63`
- owner migration: `295796e09f98f8050898d4c33105b9acec0fed28`
- remote acceptance polish: `f84d7c6294d19a9183726a71983a1e060e6fc8fb`
- IDE relay: `a2a8b1f66411d3df869bc27249151375ffee818c`
- remote session stability: `7e782d503b3e138d7bfa72a055dc4289bf33edc1`

Final human acceptance:
PyCharm on the work computer successfully used `rend-code` through the Mesh HTTPS relay and returned the requested coding result.

Follow-on:
Broader generic-agent/product-hardening tasks and selected OpenClaw plugin candidates are moved to the post-PT-048 qualification queue rather than blocking this owner-scoped remote access / IDE objective.
