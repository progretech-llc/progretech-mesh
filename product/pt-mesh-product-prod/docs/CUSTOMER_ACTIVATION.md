# Customer Installation + Activation

## Required user access

A normal Mesh user should need only:

1. access to `mesh.progretech.com`
2. a direct existing chat channel to the agent

The user should not need:

- SSH
- RDP
- shell/terminal access
- filesystem access
- administrator access to the agent workstation
- knowledge of where OpenClaw or another runtime is installed

## Enrollment experience

```text
Mesh
  ↓
Connect Agent
  ↓
signed user-controlled enrollment message
  ↓
user sends it to agent through existing chat
  ↓
agent validates local policy
  ↓
agent accepts enrollment
  ↓
agent starts separate outbound Mesh gateway
  ↓
Mesh becomes live
```

The enrollment request is not a generic remote command.

The agent must explicitly recognize it as a Mesh enrollment request and run the known
local enrollment helper only if its local policy allows the action.

## Agent-chat tool

`install/mesh_enrollment_chat_tool.py` exposes:

```python
extract_mesh_enrollment_payload(message_text)
accept_mesh_enrollment(payload, ...)
```

This is deliberately framework-neutral.

Rend/OpenClaw, Lyra, Mak, or a customer agent can expose it through their own approved
tool/skill layer.

Mesh does not assume or fake a particular OpenClaw Telegram hook.

## Reconnect credential

After the one-time activation is redeemed, Mesh issues a signed agent/device
credential.

The agent stores it locally under:

```text
~/.progretech-mesh/credentials/<agent-id>.json
```

The file should be owner-only on platforms that support Unix permissions.

The credential contains no agent conversation history.

It authorizes only the outbound Mesh gateway scope.

## Reconnect supervisor

`install/mesh_gateway_supervisor.py` keeps the separate Mesh gateway alive and
reconnects after network/process interruption.

It does not supervise, restart, pause, or control the AI agent itself.

This separation is essential:

```text
Agent runtime ─────────────── independent
     │
     └──── passive events
              ↓
        Mesh gateway
              ↑
        gateway supervisor
```

If the Mesh gateway crashes, Rend continues working.

If Mesh is unreachable, Rend continues working.

If the supervisor is stopped, Rend continues working.

## Revocation

Mesh exposes a device-revocation endpoint.

The current implementation keeps revocations in process memory because the product has
not yet introduced its production identity registry.

Production requires a small durable trust/credential registry so revocations survive
Cloud Run instance replacement.

That trust metadata is separate from agent operational history and does not violate
the no-cloud-history principle.

## Ownership

The customer owns the agent and local credential.

Mesh is an optional interaction/observation frontend.

ProgreTech should not retain remote control of the customer's agent after activation.
