# RC2 Acceptance Checklist

## Static/preflight
- [x] Universal protocol and website prompt require no preinstalled ProgreTech component.
- [x] Universal protocol requires no workstation access.
- [x] OpenClaw adapter package hash is pinned.
- [x] Bootstrap helper hash is pinned.
- [x] Package/catalog/install-plan pins match.
- [x] Managed installation path only; no direct writes to OpenClaw internals.
- [x] Mesh revocation/expiry stops Mesh only.
- [x] Same-version idempotence and downgrade rejection are present.
- [x] Frontend contains no internal phase/revision labels.

## Live — pending Rend test
- [ ] Generate PTM1 in Mesh.
- [ ] Send the complete website-generated enrollment instruction (including PTM1) to Rend through Telegram.
- [ ] No workstation access required.
- [ ] Without any preinstalled Mesh recognizer, Rend decodes PTM1, reads protocol/catalog discovery, and self-discovers the OpenClaw adapter.
- [ ] Rend downloads/verifies/installs through existing authority.
- [ ] OpenClaw/Telegram remain healthy.
- [ ] Post-install activation redeems automatically.
- [ ] Outbound Mesh connection established.
- [ ] Telegram activity appears in Mesh.
- [ ] Mesh conversation is independent.
- [ ] Mesh refresh/disconnect does not interrupt Telegram.
- [ ] Stored credential reconnect succeeds.
