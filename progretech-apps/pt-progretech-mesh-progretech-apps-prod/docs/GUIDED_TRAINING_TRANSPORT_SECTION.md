# Guided Training — Connection routing

Explain in owner language:
1. Mesh tries direct first.
2. Same-network connections can stay entirely local. Supporting browsers ask permission before a public PWA can contact a local device.
3. Across networks, STUN helps endpoints discover a direct path but does not carry the conversation.
4. Restrictive networks may require an encrypted TURN relay.
5. Direct only disables relay. Direct preferred is the default. Relay allowed permits fallback.
6. Offline PWA operation still requires a real network path to the agent; same-LAN is the supported offline path.
7. The app should always show one of: Direct local, Direct internet, Encrypted relay, or Unavailable.
