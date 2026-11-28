# Architecture Decision — Mesh Does Not Assume Agent Commissioning

Decision:
Mesh treats every agent as externally created. No ProgreTech enrollment component is assumed.

Consequences:
- PTM1 must be understandable/discoverable by an unfamiliar autonomous agent.
- Mesh publishes machine-readable enrollment protocol and adapter catalog endpoints.
- Runtime adapters are installable artifacts, not commissioning prerequisites.
- Self-bootstrap is performed by the agent using existing authority.
- Human workstation access is an exception/failure path, not normal onboarding.
- ProgreTech-owned agents receive no special enrollment shortcut.
- Rend is tested exactly like a third-party agent.

Security:
A prompt does not grant privileges. Agents must not bypass sandbox, operating-system, runtime,
or organizational controls. If self-install is not possible, the agent reports the smallest
missing capability to the owner through the channel they already use.
