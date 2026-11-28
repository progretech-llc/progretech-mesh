# PT-2026-048 Gate 1 — User→Agent Ownership + Relay Foundation

Status target: QUALIFIED FOUNDATION

Remote reachability must not precede tenancy. This gate adds explicit user→agent ownership to the existing Mesh relay.

Compatibility mode defaults to `observe`: explicit owner mismatches fail closed immediately, while unowned legacy agents remain temporarily usable. New agents, activations and device credentials carry owner binding. A PTMOWN1 claim flow is added so legacy agents can rotate to owner-bound credentials before `enforce` mode is enabled.

Agent identity remains separate: ownership redemption still requires a valid existing device credential and a verified agent record. CodeSeal + Ed25519 proof remains authoritative for agent identity.
