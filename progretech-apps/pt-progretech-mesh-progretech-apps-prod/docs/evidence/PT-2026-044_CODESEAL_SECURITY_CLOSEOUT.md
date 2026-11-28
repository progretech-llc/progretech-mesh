# Milestone Lesson — PT-2026-044 CodeSeal / PoP Security Closeout

Status: QUALIFIED / CLOSED

## Goal
Finish the production Mesh agent-identity gate so cloud identity can truthfully claim production readiness.

## Why it mattered
Mesh is the command center for Rend, Lyra and Mak. Production trust needed explicit CodeSeal evidence, a signed reconnect credential, Ed25519 proof-of-possession, replay resistance, restart-safe identity recovery, and a fail-closed cloud contract.

## Starting state
Release automation was already qualified. Rend had an existing production CodeSeal event and keypair, but the cloud identity path still needed fail-closed evidence semantics, complete HTTP tests, a replay design, restart-safe process recovery, and a production credential actually signed by the cloud device secret.

## Path taken
1. Inspected CodeSeal/PoP and Cloud Run behavior.
2. Qualified bounded replay because Cloud Run maxScale=1 and Gunicorn workers=1.
3. Hardened explicit CodeSeal evidence handling and HTTP identity tests.
4. Published through GitHub main → Cloud Build → Artifact Registry → Cloud Run.
5. Made fresh Cloud Run revisions reconstruct ephemeral agent state only after device credential + Ed25519 PoP + CodeSeal verification.
6. Updated OpenClaw 0.7.9 to assert CodeSeal identity before reconnect.
7. Reconciled adapter package SHA metadata.
8. Completed the Charter HTTP negative/positive matrix.
9. Discovered that the existing reconnect credential was a localhost/dev credential (`mesh=http://127.0.0.1:8080`), not a production-cloud credential.
10. Reissued the same Rend device identity under the current production `progretech-mesh-device-secret`, changed the credential target to `https://mesh.progretech.com`, and preserved a local backup.
11. Ran live pre-promotion and post-promotion production CodeSeal/PoP matrices.
12. Promoted `MESH_CODESEAL_READY=1` only after live production acceptance.

## Roadblocks and lessons
- Flask missing in a detached test environment → use the repo venv or disposable test environment.
- Slash-containing Cloud Run annotation was brittle through `gcloud value(...)` → parse service JSON directly.
- `node` absent from the interactive PATH did not mean Node was absent → discover the actual service runtime before changing the host.
- Three regression tests still expected adapter 0.7.8 after a deliberate 0.7.9 bump → update stale version-contract assertions, not working behavior.
- GitHub main advanced during retries → re-fetch authority before retrying patches.
- Fresh Cloud Run revisions lost in-memory agent state → reconstruct ephemeral state from durable cryptographic identity rather than persisting process memory.
- A diagnostic reported a live challenge as successful because it followed the credential's stored `mesh=http://127.0.0.1:8080` target → always print and verify the actual endpoint when claiming a cloud acceptance result.
- Offline HMAC comparison against production secrets correctly revealed that the old reconnect credential was not production-signed.
- Do not rotate secrets just because a credential is stale. Reissue the bounded credential under the current authoritative signing secret.

## Validation evidence
- Security implementation: `86021e062c83596fff9889e6efa140d4040b8f71`
- Restart-safe identity: `f29d58acc2e46950dbd4e2011f965f59ecf4c433`
- Adapter metadata reconciliation: `32745d9e81c06d4a7c16f1199502e79133385df3`
- Complete HTTP matrix: `4983c3abd4f03cdc4d0a63445c76837c1cf0b678`
- Full regression at complete matrix: 158/158 PASS
- Cloud Run maxScale=1
- Gunicorn workers=1
- OpenClaw adapter 0.7.9
- Production reconnect credential targets `https://mesh.progretech.com`
- Live invalid credential, missing evidence, missing proof, bad signature, successful trust update and replay rejection all pass against production.
- Production readiness promoted only after the production live matrix.

## Outcome
PT-2026-044 release automation and cloud CodeSeal/PoP security are qualified and closed.

## Reusable rule
Always distinguish local, staging and production endpoints in identity diagnostics. A successful localhost proof is not production evidence.

## Next transition
The Charter's next required gate is Rend IDE / PyCharm integration before Lyra/Mak commissioning.
