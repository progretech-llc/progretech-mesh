# Mesh Plug-and-Monitor Contract

## Product guarantee

Connecting or disconnecting ProgreTech Mesh must not interrupt, reset, pause,
restart, reconfigure, replace, or seize an agent's existing runtime, task, or
conversation.

If Rend is already working from Telegram, Mesh attaches observationally.

## Channel isolation

Existing channels stay independent:

```text
Agent
├── Telegram conversation/session
├── Mesh conversation/session
├── future channel/session
└── system/tool activity
```

A Mesh conversation is not a continuation of the Telegram conversation unless the
agent itself deliberately shares information through its local memory/context model.

Mesh must not silently merge channel transcripts.

## Passive activity model

Mesh can display normalized activity from any source:

```json
{
  "event_type": "processing",
  "channel": "telegram",
  "state": "working",
  "direction": "input",
  "summary": "New Telegram request"
}
```

Other channel values can include:

```text
mesh
telegram
system
tool
scheduler
api
unknown
```

The observation adapter is read-only.

## Current adapter implementation

Phase 1 Rev 2 introduces:

```text
MESH_OBSERVATION_ADAPTER=none
MESH_OBSERVATION_ADAPTER=jsonl
```

`jsonl` reads an append-only local activity feed.

This is intentionally a generic observation contract rather than a guessed OpenClaw
internal hook. Once the real local event/log interface is selected, another adapter
can implement the same contract without changing Mesh.

## Agent-led enrollment

The user should need only:

1. access to `mesh.progretech.com`
2. a direct chat line to the agent

Mesh generates a user-controlled enrollment message that remains active until cancelled or successfully redeemed.

The user sends that message through Telegram or another existing direct channel.

The agent:

1. validates the request
2. applies its local authorization policy
3. runs the signed/local Mesh enrollment helper
4. starts a separate outbound gateway process
5. keeps all current work untouched

The user does not need:

- SSH
- terminal access
- RDP
- filesystem access
- knowledge of the agent's host paths

## Reconnect model

Initial enrollment should establish a local identity/credential suitable for automatic
reconnect in a later hardening phase.

A user should only need to enroll again after revocation, reinstall, ownership
change, or explicit trust reset.
