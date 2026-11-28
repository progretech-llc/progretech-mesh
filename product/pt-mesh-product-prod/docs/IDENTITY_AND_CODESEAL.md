# Production Identity + CodeSeal Boundary

## User identity

Mesh supports:

```text
MESH_AUTH_MODE=development
MESH_AUTH_MODE=oidc
```

Development mode exists only for local development.

Production deployment must use the real configured identity provider.

The provider-specific OIDC redirect/callback implementation must not be guessed or
faked before the real issuer/client configuration is available.

## Agent identity

Mesh now separates development identity scaffolding from the production CodeSeal
verifier boundary.

```text
MESH_AGENT_IDENTITY_MODE=development
MESH_AGENT_IDENTITY_MODE=codeseal
```

Development mode:

- can identify known development agents
- can support local testing
- is not cryptographic CodeSeal verification
- must not be displayed as "CodeSeal Verified"

Production CodeSeal mode:

- fails closed while unconfigured
- must cryptographically verify the agent/package identity
- must bind the verified identity to the expected Mesh agent
- must reject expired/revoked/invalid assertions
- must not silently downgrade to development verification

## UI language

Until real CodeSeal cryptographic verification is installed, the frontend uses:

```text
Identity verified
```

rather than:

```text
CodeSeal Verified
```

The latter should only appear when the production verifier has actually succeeded.

## Enrollment

Agent-led enrollment remains single-use, user-controlled, and agent-bound.

Production enrollment must combine:

1. authenticated Mesh user
2. signed/user-controlled enrollment request
3. agent-local authorization
4. cryptographically verified agent identity
5. outbound gateway connection

None of these steps may restart or take over the running agent.

## Remaining production dependencies

This build establishes the integration boundaries but intentionally does not fabricate:

- an OIDC client/secret/redirect configuration
- CodeSeal public keys/trust roots
- a CodeSeal SDK/API contract
- revocation endpoint semantics

Those require the actual production provider configuration.

## Production verifier contract (PT-2026-044)

The production adapter now targets the actual CodeSeal Registry API contract:

- `POST https://codeseal.progretech.com/api/v1/verify`
- evidence fields: `manifest`, `registry_signature`, `registry_public_key`
- CodeSeal verifies Ed25519 signature validity, known registry key, and exact registry-record match
- Mesh additionally requires `manifest.mesh_identity` to bind `agent_id`, `agent_name`, and the expected Mesh `public_key`
- optional `expires_at` and `revoked` fields are enforced locally
- any network, malformed-response, mismatch, expiry, revocation, unknown-key, or non-matching-record condition fails closed

Installing this adapter does not by itself set `MESH_CODESEAL_READY=1`. A real agent identity evidence record must be issued through CodeSeal and pass live verification before readiness promotion.

## PT-2026-044 production identity replay contract

The current Cloud Run deployment intentionally uses a bounded process-local
identity challenge store. This is qualified only while **both** deployment
invariants remain true:

- Cloud Run `maxScale = 1`
- Gunicorn `--workers 1`

The single process may serve concurrent threads; `LIVE_LOCK` serializes challenge
state mutation. The challenge TTL remains short (60 seconds by default), and
consumed challenges are removed immediately.

This is a bounded design, not a general horizontally scalable replay solution.
Increasing Cloud Run above one instance or Gunicorn above one worker invalidates
this qualification and requires a shared atomic replay-state backend before
CodeSeal readiness may remain enabled.

`MESH_IDENTITY_REPLAY_MODE=single-process-bounded` records this operational
contract. `MESH_CODESEAL_READY=1` must not be set until the live production
acceptance suite confirms the verifier, HTTP identity path, CodeSeal evidence,
and these deployment invariants together.


## Shared account security locks

Enable `PROGRETECH_SECURITY_ENFORCED=1` and mount the separate read-only
`PROGRETECH_SECURITY_STATUS_TOKEN` in production. Authenticated browser requests
validate the canonical subject and session version against CodeSeal's
`POST /auth/sso/account-status` endpoint; only the current request memoizes a
response. Locked or version-revoked cookies are cleared. Status outages and
malformed/mismatched responses fail closed. Shared SSO userinfo supplies the
session version. `PROGRETECH_SECURITY_STATUS_FETCH(subject)` is a test-fixture
Flask-config callable and must not be configured for production.

Legacy Firebase email-link and local development human sessions cannot establish
canonical lock status and must sign in using ProgreTech shared login when this
security setting is enabled. Shared login still maps the broker-verified email to
an existing verified Firebase UID so ownership remains intact. New legacy human
session issuance is disabled under enforcement. Existing machine credentials,
robot identities and signed gateway connections remain separately authenticated.
Browser WebSocket deliveries recheck status before every private send in a fresh
app context; an already-open connection cannot continue receiving private events
after lock, revocation or broker failure. An idle stream closes when its next
private delivery is attempted. No account authorization is cached across sends.

A lock requires support-assisted identity verification at support@progretech.com.
An active account whose billing remains on hold can still use already-valid Mesh
access; billing resumption is a separate, explicit support action.
