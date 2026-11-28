# Canonical Mesh Public Origin

Use `MESH_PUBLIC_ORIGIN` for the address agents can actually reach.

Local acceptance example:
`MESH_PUBLIC_ORIGIN=http://192.168.1.50:8080`

Production example:
`MESH_PUBLIC_ORIGIN=https://mesh.progretech.com`

The browser can still open Mesh at `http://127.0.0.1:8080`; agent-facing PTM1 discovery,
package, activation, pairing, and WebSocket URLs use the canonical origin.

`MESH_ENVIRONMENT=production` requires HTTPS. WebSocket URLs derive automatically:
`http -> ws` and `https -> wss`.


## Local acceptance transport policy

For development/local acceptance, Mesh permits plain HTTP/WS only when the canonical origin host is loopback or an RFC1918 private-LAN IPv4 address (127/8, 10/8, 172.16/12, 192.168/16). Public/non-private HTTP is rejected by the agent adapter. Production still requires HTTPS/WSS.
