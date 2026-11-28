# ProgreTech Mesh — Direct-First Routing Contract

## Product rule
The owner device and the agent are the normal data endpoints. ProgreTech is not the default conversation pipe.

## Route order
1. **LAN direct** — same-network owner-to-agent path. ProgreTech is not in the data path.
2. **Internet peer-to-peer** — encrypted direct path negotiated with ephemeral signaling. ProgreTech may introduce peers but does not carry conversation data.
3. **Encrypted relay fallback** — optional and owner-controlled for restrictive NAT/firewall/corporate networks.

## Owner policies
- `direct_preferred` (default): direct first; relay only when allowed and necessary.
- `direct_only`: never carry agent session data through ProgreTech.
- `relay_allowed`: direct first, relay permitted as fallback.

## Cloud role
Cloud Mesh may provide authentication, agent discovery, trust/revocation, package distribution, and ephemeral signaling. Relay is optional and must be explicit.

## Offline PWA
An installed PWA on the same LAN as an enrolled agent must be able to reconnect directly without Cloud Mesh once local transport and trust material are available.

## Release gate
No feature expansion takes priority over completing and validating direct transport with a real agent.
