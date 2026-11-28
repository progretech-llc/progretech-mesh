# Milestone Lesson — Rend IDE / PyCharm Integration

Status: QUALIFIED / CLOSED

## Goal
Make Rend available as a governed coding/engineering assistant from PyCharm installations on the MS-S1 MAX and other trusted computers, without coupling the IDE directly to Ollama or one concrete model.

## Why it mattered
Rend is intended to remain the agent identity and policy/context layer. Direct PyCharm → Ollama would bypass Rend's stable aliases, MemPalace recall, governance, and future routing changes. The IDE integration therefore needed a durable OpenAI-compatible gateway above the local model runtime.

## Starting state
- Rend already owned the qualified local model ladder on the MS-S1 MAX.
- Ollama was healthy on loopback only.
- PyCharm 2026.2 was present.
- No dedicated Rend IDE Gateway existed.
- The Charter required this integration before Lyra/Mak commissioning.

## Path taken
1. Performed read-only discovery of Rend runtime, Control Center, OpenClaw, Ollama, JetBrains state, host networking and candidate gateway roots.
2. Preserved Ollama on `127.0.0.1:11434`; the IDE never connects to Ollama directly.
3. Added `~/Rend/rend-ide-gateway` as a user-scoped service on port `8766`.
4. Implemented `GET /health`, `GET /v1/models`, and `POST /v1/chat/completions`.
5. Added bearer-token authentication and private-network source filtering.
6. Added stable aliases: `rend` → `qwen3.8:27b`, `rend-code` → `qwen3-coder:30b`, `rend-fast` → `qwen3:1.7b`.
7. Added Rend policy/context injection plus bounded MemPalace recall.
8. Qualified local, LAN and Tailscale connectivity.
9. Proved a second computer (ZenBook) could reach the same gateway and complete a real `rend-code` request.
10. Owner configured PyCharm on both ZenBook and MS-S1 MAX and confirmed Rend responded to the two IDE qualification prompts on both machines.

## Acceptance evidence
- Gateway service `rend-ide-gateway.service`: ACTIVE.
- Unauthenticated `/health` → 401.
- Authenticated `/health` → 200.
- `/v1/models` exposes `rend`, `rend-code`, `rend-fast`.
- Local `rend-code` completion → `REND IDE GATEWAY PASS`.
- LAN smoke on `192.168.1.229:8766` → PASS.
- Tailscale endpoint `100.78.55.26:8766` → authenticated HTTP 200.
- ZenBook second-computer completion → `SECOND COMPUTER REND PASS`.
- Owner-witnessed PyCharm acceptance on ZenBook and MS-S1 MAX → PASS.
- Tool calling remained OFF for this initial IDE qualification.

## Security / governance decisions
- Bearer token stored at `~/.config/rend/ide-gateway-token`; never committed to Git.
- Trusted remote clients use the private/Tailscale endpoint, not public internet exposure.
- No unrestricted shell/tool endpoint is exposed.
- PyCharm talks to Rend, not directly to Ollama.
- Stable aliases sit above concrete model versions.
- Git, credential, protected-access, sudo/root, production/release and STOP/CANCEL gates remain in force.

## Outcome
The Rend IDE / PyCharm integration gate is QUALIFIED / CLOSED.

Rend is now available from PyCharm on the MS-S1 MAX, PyCharm on the ZenBook through Tailscale, and future trusted PyCharm installations that can reach the private gateway and hold the bearer token.

## Reusable lessons
- Keep agent identity above the model/provider layer.
- Prove portability with a second physical client, not only localhost.
- A stable OpenAI-compatible contract lets IDEs change independently from the local model ladder.
- Private overlay networking is sufficient for trusted multi-device IDE access; public internet exposure is unnecessary.
- Tool execution should remain separately qualified rather than being implied by successful chat completion.

## Next transition
The pre-arrival Rend IDE dependency is satisfied. Lyra/Mak commissioning remains hardware + owner-start gated; no new PT activity is created by this closeout.
