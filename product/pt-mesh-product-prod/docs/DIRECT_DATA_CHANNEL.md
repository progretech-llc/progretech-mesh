# Direct owner-to-agent data channel

Implemented in this build:
- Browser WebRTC peer + `progretech-mesh` RTCDataChannel.
- OpenClaw WebRTC endpoint using pinned `node-datachannel` 0.33.3.
- Cloud Mesh carries ephemeral SDP/ICE signaling only.
- Same-LAN direct mode uses host ICE candidates only (`iceServers: []`).
- Direct hello/ack, ping/pong, heartbeat request, and one-to-one Mesh messaging.
- Stable isolated Mesh conversation identity remains unchanged.
- SDP/ICE payloads are not persisted into activity history.

Still pending: Internet STUN traversal, optional TURN relay, owner routing policies, offline PWA reconnect, and migration of remaining telemetry/file paths to direct transport.

Adapter 0.7.7 SHA-256: `ffcde913f823ea5986c23a2e445e6cfe4ccb262ae38169ece782db321c7675c3`
Bootstrap SHA-256: `7a309839f409cc67199536b28c08e7659c777c9b1b584e76f668db45b9b877d6`
