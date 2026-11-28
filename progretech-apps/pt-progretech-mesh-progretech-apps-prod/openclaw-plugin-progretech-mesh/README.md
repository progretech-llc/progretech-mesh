# ProgreTech Mesh — OpenClaw integration prototype

This package targets OpenClaw 2026.9.3 and uses public plugin SDK surfaces discovered on Rend:

- typed `api.on(...)` hooks for passive observation
- `api.registerHttpRoute(...)` for a loopback-only local bridge
- `api.runtime.agent.runEmbeddedAgent(...)` with a stable Mesh-only session id/session key

## Non-interference contract

The observer does not start, stop, reset, restart, reconfigure, or claim ownership of Telegram or another channel. It mirrors activity to an ephemeral local JSONL file under `$XDG_RUNTIME_DIR/progretech-mesh/` (or `/tmp` fallback).

The local conversation bridge uses a stable Mesh-specific session identity and does not reuse the Telegram session key.

## Important status

This is an integration candidate, not yet proven on Rend. Do not claim production channel isolation until the included validation steps pass twice sequentially while Telegram remains active.

The bridge is loopback-only. Set `PROGRETECH_MESH_LOCAL_TOKEN` in both the OpenClaw Gateway environment and the Python Mesh gateway environment to require a shared local bearer-style header.


Offline same-LAN signaling: authenticated local HTTP listener on port 18791; WebRTC remains the session data path.
