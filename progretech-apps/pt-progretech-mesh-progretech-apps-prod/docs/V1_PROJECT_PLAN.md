# Mesh v1 Roadmap

| Phase | Target | Status |
|---|---|---|
| 1 of 7 | Passive observation + channel isolation + agent-led enrollment | Complete baseline |
| 2 of 7 | Per-agent PWA/browser notifications | Complete baseline |
| 3 of 7 | Production identity + CodeSeal boundary | Complete baseline |
| 4 of 7 | Customer installation + activation | Complete baseline |
| 5 of 7 | Cloud Run production baseline | Complete baseline; deployment deferred |
| 6 of 7 | Runtime + transfer hardening | Complete baseline |
| **7 of 7** | **Release candidate / customer validation** | **Current** |

## Release completion

After the core UI and workflows are stable, implement the user-facing Guided Training
described in `GUIDED_TRAINING_PLAN.md`.

Guided Training is a release-completion requirement and must not expose internal phase
terminology.


## Direct-first release gate
Direct owner-to-agent communication is now the primary release blocker. LAN direct, internet P2P, route negotiation, and optional relay fallback must be implemented and live-tested before nonessential feature expansion.
