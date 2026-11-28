# Direct transport acceptance

Reference live agent: Rend.

Required live evidence:
- hands-off enrollment from the owner's existing agent chat;
- Telegram remains uninterrupted;
- same-LAN direct WebRTC;
- internet peer-to-peer when permitted;
- Direct only never falls back to TURN;
- Relay allowed can use TURN when configured and direct networking is blocked;
- installed PWA shell loads offline;
- owner grants browser local-network permission and the PWA can use its remembered agent-local signaling route on the same LAN;
- Mesh conversation remains isolated from Telegram;
- refresh/disconnect does not interrupt agent work;
- stored credential reconnects without re-enrollment.

A stable failure boundary is useful evidence but is not an acceptance pass.

Adapter 0.7.7 SHA-256: `ffcde913f823ea5986c23a2e445e6cfe4ccb262ae38169ece782db321c7675c3`
Bootstrap SHA-256: `7a309839f409cc67199536b28c08e7659c777c9b1b584e76f668db45b9b877d6`
