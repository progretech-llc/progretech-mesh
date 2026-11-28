# Universal Enrollment Acceptance — Rend

Rend is deliberately treated as if he were an independently created third-party agent.

Test starting state:
- current Rend installation;
- no Mesh enrollment bootstrap preinstalled;
- no manual Mesh plugin installation;
- no SSH/RDP/terminal session by the owner;
- owner can communicate with Rend through Telegram.

Pass conditions:
- Mesh produces a PTM1 enrollment message.
- Edwin sends only that enrollment message to Rend.
- Rend recognizes the request as an owner instruction.
- Rend discovers the Mesh enrollment protocol from the PTM1 payload.
- Rend uses his already-known runtime identity first; if unavailable, only the catalog-declared bounded read-only probe is permitted.
- Rend identifies OpenClaw as the compatible adapter target.
- Rend fetches the declared Mesh OpenClaw package himself.
- Rend uses OpenClaw's supported managed local/archive plugin installer rather than copying files into OpenClaw internals.
- Rend verifies package integrity before staging.
- Rend uses only his existing local permissions.
- Rend does not interrupt a Telegram-started task.
- The declared hot-safe managed install may occur during the enrollment turn. Mesh does not automatically restart OpenClaw; an explicit reload/restart requirement is reported as `activation_reload_required`.
- Rend redeems the enrollment and connects outbound to Mesh.
- Telegram continues to work.
- Telegram-originated activity appears in Mesh.
- Mesh-originated conversation uses separate Mesh session/context.
- Refresh/disconnect of Mesh does not affect Telegram work.

Automatic failure:
- Edwin must log into Rend's workstation.
- Edwin must run a terminal command.
- Edwin must manually copy/install a Mesh package.
- Enrollment cancels/resets active work.
- Mesh takes control of the Telegram session.
- Package verification is skipped.
- Agent bypasses its own policy/permission model.

A permission prompt inside the agent's existing interaction channel is allowed if the agent's
normal security model requires explicit owner approval. Workstation access is not.
