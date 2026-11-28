# Cloud Run Security Checklist

- [ ] development login disabled
- [ ] development seed agents disabled
- [ ] real OIDC provider flow tested
- [ ] real CodeSeal cryptographic verification tested
- [ ] Secret Manager secrets configured
- [ ] least-privilege Cloud Run service identity
- [ ] `/startupz` and `/healthz` succeed
- [ ] production `/readyz` returns 200
- [ ] WebSocket reconnect proven after disconnect/timeout
- [ ] reconnect does not disturb active agent work
- [ ] max instances remains 1
- [ ] operational APIs return `Cache-Control: no-store`
- [ ] service worker bypasses operational APIs
- [ ] arbitrary remote shell remains unavailable
- [ ] upload limits/sensitive-file approval remain enforced
- [ ] custom domain enabled after Cloud Run URL acceptance
