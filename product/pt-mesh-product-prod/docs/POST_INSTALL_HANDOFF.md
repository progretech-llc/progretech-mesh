# Automatic Post-Install Handoff

The OpenClaw adapter now completes enrollment after managed installation without a second owner instruction.

Flow:

`PTM1 → package verification → pending handoff → hot-safe managed OpenClaw install → plugin startup → activation redeem → signed device credential → outbound Mesh WebSocket → passive activity forwarding`

Local state:

- `~/.progretech-mesh/pending-enrollment.json` — one-time activation material; removed after durable credential persistence.
- `~/.progretech-mesh/device-credential.json` — signed reconnect credential, stored with private permissions.
- `~/.progretech-mesh/connection-status.json` — minimal diagnostic connection state.

On later OpenClaw starts, the adapter reconnects with the saved device credential and does not require re-enrollment.

The adapter forwards passive observation events only. It does not seize Telegram or reuse Telegram conversation context. Mesh conversation remains isolated on the Mesh session path.

## Stable local signaling ownership during upgrades
The local signaling port is a stable Mesh-owned route. During an in-place upgrade, `EADDRINUSE` is not automatically a failure. The candidate adapter must authenticate a read-only `/mesh-local/status` request using the existing local Mesh access credential. If that succeeds, the port is treated as owned by the previously loaded Mesh adapter and is reused during hot handoff; the upgrader must not kill the old listener or bind a second listener. If authenticated ownership cannot be proven, stop with `port_conflict`.
