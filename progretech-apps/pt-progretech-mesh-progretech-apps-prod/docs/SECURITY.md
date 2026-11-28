# ProgreTech Mesh — Production Security Boundary

## Customer ownership

A customer-owned agent must remain functional without an active connection to
ProgreTech Mesh.

Mesh is:

- an authenticated front end
- an ephemeral relay
- an identity/trust verification surface
- an optional operations console

Mesh is **not**:

- the customer's agent memory
- the agent runtime
- a cloud copy of conversations
- a cloud file repository
- an unrestricted remote shell

## Production authentication

Phase 7 establishes the adapter boundary:

```text
MESH_AUTH_MODE=oidc
MESH_OIDC_ISSUER=https://...
```

The baseline intentionally does not invent provider-specific OIDC behavior without the
real provider/client configuration.

Development login must remain disabled in production:

```text
DEV_AUTH_ENABLED=0
```

## Activation

Activation is one-time and user-lifecycle-bound: it remains valid until explicitly cancelled or successfully redeemed. It is not governed by a normal countdown.

```text
signed agent identity
      ↓
activation code
      ↓
customer bootstrap
      ↓
activation redeem
      ↓
one-time pairing token
      ↓
outbound gateway session
```

Once activation completes, the customer's gateway operates locally.

## CodeSeal

The development `CS-*` verifier remains an adapter, not the final cryptographic
CodeSeal service.

Production must replace it with the real CodeSeal verification contract before the
service claims cryptographic CodeSeal trust.

## File transfers

Production transport now uses:

- browser multipart upload
- bounded chunks from Mesh to the gateway
- bounded chunks from gateway to Mesh
- SHA-256 verification
- filename sanitization
- per-file and per-session limits
- sensitive-file confirmation
- `Cache-Control: no-store` on downloads

No service-worker cache is used for file APIs.

## Remote actions

Only explicitly enumerated action types are accepted.

No arbitrary `exec`, shell, PowerShell, bash, or SSH action is exposed by Mesh.
