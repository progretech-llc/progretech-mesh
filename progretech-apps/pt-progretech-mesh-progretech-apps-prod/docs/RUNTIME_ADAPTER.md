# Mesh v1 Runtime Adapter Contract

## Goal

Mesh should not know how Rend, Lyra, Mak, or a future customer agent internally
implements intelligence.

Mesh speaks a small stable protocol to the local gateway:

```text
message_request
message_response
heartbeat
event
file transfer
approved action
```

The gateway translates `message_request` into the selected local runtime.

## Adapter selection

```text
MESH_RUNTIME_ADAPTER=demo
MESH_RUNTIME_ADAPTER=openclaw
```

## OpenClaw adapter

The first real adapter runs the existing OpenClaw CLI:

```text
openclaw agent exec \
  --model <optional-model> \
  --cwd <agent-workspace> \
  --timeout <seconds> \
  --json \
  "<prompt>"
```

Environment:

```text
OPENCLAW_BIN=~/.openclaw/bin/openclaw
OPENCLAW_CWD=~/Rend
OPENCLAW_MODEL=
OPENCLAW_TIMEOUT=180
```

`OPENCLAW_MODEL` is optional. If omitted, OpenClaw uses its configured/default routing.

## Why the CLI adapter first

It gives Mesh a real Rend integration without coupling the web product to OpenClaw's
internal implementation.

Later, the adapter can be replaced by:

- an OpenClaw local API
- a local message bus
- another agent framework
- a customer-specific runtime

without changing the Mesh browser or relay protocol.

## Security boundary

The runtime adapter receives a user message.

It does not give the Mesh web application a generic operating-system shell.

Any tools OpenClaw itself may use remain controlled by the local agent runtime and its
existing policy/approval model.

## Files

Files sent through Mesh are staged locally first.

The runtime adapter may receive local staged paths as message context, rather than
having Mesh upload the file into a model provider.

## Error handling

Runtime failures return a normal `message_response` carrying generic user-facing text
plus structured runtime metadata.

Detailed runtime errors also appear as structured Mesh events for monitoring.
