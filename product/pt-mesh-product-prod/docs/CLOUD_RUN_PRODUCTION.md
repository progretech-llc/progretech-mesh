# Cloud Run Production Baseline

Mesh uses a conservative Cloud Run topology while live WebSocket/session routing is
process-local.

## Runtime

```text
execution environment: gen2
request timeout: 3600 seconds
max instances: 1
concurrency: 80
```

Cloud Run WebSockets are still long-running HTTP requests and can be disconnected by
the configured request timeout. Mesh gateways must reconnect automatically.

A reconnect must affect only Mesh transport, never the agent's current task or other
conversation channels.

## Health

```text
/startupz
/healthz
/readyz
```

Production readiness fails closed until real OIDC and real CodeSeal verification are
explicitly configured and tested.

## Secret Manager

Use Secret Manager for:

```text
SECRET_KEY
MESH_ACTIVATION_SECRET
MESH_DEVICE_CREDENTIAL_SECRET
```

Do not commit these values or place them into ordinary deployment environment files.

## Deployment sequence

1. bootstrap Secret Manager secrets
2. deploy as `staging`
3. verify Cloud Run service URL
4. test WSS reconnect behavior
5. configure/test real OIDC
6. configure/test real CodeSeal verification
7. switch deployment tier to `production`
8. attach `mesh.progretech.com`

## Scaling

Do not increase beyond one instance until Mesh has a shared ephemeral routing layer
for gateway/browser connections. Durable transcript/history storage is not an
acceptable substitute.

## Custom domain

Target domain:

```text
mesh.progretech.com
```

Attach it only after the Cloud Run URL passes acceptance.
