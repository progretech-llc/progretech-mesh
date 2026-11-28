# Mesh v1 Release Checklist

## Identity
- [ ] Development login disabled
- [ ] Production identity provider selected
- [ ] OIDC client configured
- [ ] Session secret stored in Secret Manager
- [ ] Real CodeSeal verification adapter installed

## Cloud Run
- [ ] Dedicated service account
- [ ] Least-privilege IAM
- [ ] HTTPS-only custom domain
- [ ] `mesh.progretech.com` mapped
- [ ] minimum/maximum instances reviewed
- [ ] WebSocket routing strategy validated
- [ ] request timeout validated
- [ ] logs contain no file contents/prompts/secrets

## Gateway
- [ ] bootstrap tested on Windows
- [ ] bootstrap tested on Linux
- [ ] reconnect strategy tested
- [ ] staging cleanup configured
- [ ] gateway auto-start method documented
- [ ] local ownership/offline behavior verified

## File transfer
- [ ] 20 MB default tested
- [ ] 50 MB session cap tested
- [ ] SHA-256 mismatch rejected
- [ ] filename traversal rejected
- [ ] sensitive types require confirmation
- [ ] interrupted transfer cleanup tested
- [ ] reverse download is `no-store`

## Operator actions
- [ ] all allowed actions enumerated
- [ ] unrecognized actions rejected
- [ ] no arbitrary remote shell
- [ ] approval/rejection flow tested

## PWA
- [ ] desktop install
- [ ] Android install
- [ ] phone layout
- [ ] Galaxy Fold cover layout
- [ ] Galaxy Fold inner-display layout
- [ ] offline shell contains no agent data
