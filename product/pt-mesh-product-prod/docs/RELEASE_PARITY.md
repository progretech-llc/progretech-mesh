# Mesh release continuity

Web and desktop ship the same Factory and agent interface from this repository.
The 2026-10-02 regression came from desktop feature commits living only on
`releases/mesh-local`, while web deployments continued from older `main` code.

Before a feature update:

1. Fetch both release branches and inspect their divergence. Base web work on
   current `origin/main` and incorporate the current desktop release ancestry.
   Never replace main wholesale with an old checkout or the desktop branch:
   web authentication and persistence changes may be unique to main.
2. Preserve shared login, account-lock checks, owner-bound CodeSeal identities,
   signed enrollment receipt restoration, and release reconnect handling.
3. Run the complete Python suite, authentication pytest cases, adapter and UI
   JavaScript tests. CI rejects web candidates missing current desktop ancestry.
4. Publish one reviewed common source, then promote it to the desktop release
   channel. Do not develop long-lived independent feature baselines.
5. Verify live `/healthz` build IDs and both interfaces. Across a web deployment,
   verify gateway process uptime is unchanged and signed enrollment recovery
   reports the expected roster with no rejected receipts.

Factory and fleet use `/api/status` observations through `MeshRuntime`; absence
of current evidence means unknown, not idle. Terminal direction and status lamp
colors share a classifier. Local shell mode uses the authenticated loopback host;
cloud uses the authenticated gateway. Neither transports the agent's memory into
cloud storage.

Adapter release metadata must agree across main's served package constants,
package.json, all three distribution manifests, and the archive checksum.
Planned WebSocket release reconnect uses normal close 1000. Authentication
rejection codes remain terminal; do not reuse them for a release reconnect.
