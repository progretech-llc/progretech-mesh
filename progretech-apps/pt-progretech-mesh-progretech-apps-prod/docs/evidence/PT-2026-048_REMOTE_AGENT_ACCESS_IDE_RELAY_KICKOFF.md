# PT-2026-048 — Mesh Remote Agent Access & IDE Relay — Kickoff Evidence

Status: AUTHORIZED / ACTIVE

The owner authorized two equal-priority outcomes: remote access to Rend through mesh.progretech.com from anywhere, and PyCharm access from a work computer behind corporate VPN controls.

Priority: build the cloud owner-scoped relay first because it is the shared dependency for both outcomes.

Existing substrate confirmed before implementation: outbound agent WebSocket, signed reconnect credential, browser client WebSocket, correlated request IDs, PTM1 enrollment payload, Ed25519 + CodeSeal identity, Firebase auth, file relay, direct/P2P signaling, and the current threaded single-process Cloud Run contract.

First implementation gate: explicit user→agent ownership + relay enforcement.
