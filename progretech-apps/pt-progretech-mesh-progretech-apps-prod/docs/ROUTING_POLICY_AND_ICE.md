# Direct-first routing policy

Mesh now has three owner-selectable connection policies.

## Direct preferred
Default. Mesh first attempts direct WebRTC using host and STUN-discovered candidates. If a TURN
service is configured, WebRTC may use it only when the network cannot establish a direct candidate pair.

## Direct only
Mesh supplies host/STUN candidates but removes TURN candidates. If the owner and agent cannot establish
a direct route, the session remains unavailable rather than relaying agent traffic through ProgreTech.

## Relay allowed
Direct candidates are still available and WebRTC's ICE selection chooses the best viable pair. TURN
is available as a fallback when configured.

## Data handling
STUN is NAT discovery and does not carry Mesh conversation content. SDP/ICE negotiation uses Mesh's
ephemeral signaling channel. TURN, when used, carries end-to-end encrypted WebRTC packets; it is not
the default route.

For production, TURN credentials should be short-lived rather than static environment credentials.
The environment-variable credential support in this build is an integration baseline, not the final
credential-vending design.

Adapter version: 0.7.7
Adapter SHA-256: `ffcde913f823ea5986c23a2e445e6cfe4ccb262ae38169ece782db321c7675c3`
Bootstrap SHA-256: `7a309839f409cc67199536b28c08e7659c777c9b1b584e76f668db45b9b877d6`
