# OpenClaw integration candidate

## Purpose

Replace the old `openclaw agent exec` prototype with OpenClaw-native plugin seams discovered on Rend 2026.9.3.

## Passive observation

The local plugin registers typed `api.on(...)` observers for:

- `message_received`
- `message_sent`
- `model_call_started`
- `model_call_ended`
- `after_tool_call`
- `agent_end`

It writes normalized events to an ephemeral local runtime file. It does not restart or mutate the agent, task, Telegram session, or model configuration.

## Mesh conversation isolation

The plugin exposes a loopback-only HTTP bridge. Each Mesh conversation receives a stable Mesh-specific `sessionId` and `sessionKey`, separate from Telegram. Calls use the injected OpenClaw runtime `api.runtime.agent.runEmbeddedAgent(...)`; the Python gateway no longer shells out to `openclaw agent exec` when `MESH_RUNTIME_ADAPTER=openclaw_bridge`.

## Required acceptance on Rend

1. Enable the plugin during a controlled test window.
2. Keep Telegram connected.
3. Start a Telegram task and leave it running.
4. Connect Mesh and verify Telegram input/output/tool/model events appear as Telegram activity.
5. Send two sequential Mesh messages and verify both reuse the same Mesh session identity.
6. Verify the Telegram session key and conversation remain unchanged.
7. Refresh/disconnect Mesh and verify Telegram work continues.
8. Restart only the Mesh local gateway and verify OpenClaw/Telegram are unaffected.

Until those tests pass, this package is an integration candidate rather than a production isolation claim.
