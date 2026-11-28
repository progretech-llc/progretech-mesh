# PT-2026-044 — Release Automation Closeout

Status: **QUALIFIED**

## Authoritative source

- Repository: `eabdiel/progretech-mesh`
- Base qualified commit: `714326e275e40610c869219c7cd5b7e79a2a51c9`
- Branch: `main`
- Build config: `cloudbuild.yaml`

## Production path

`GitHub main → Cloud Build trigger → Docker build → Artifact Registry → Cloud Run → mesh.progretech.com`

- Trigger: `progretech-mesh-main-deploy`
- Trigger region: `global`
- Artifact Registry: `us-east1-docker.pkg.dev/progretech-production/cloud-run-source-deploy/progretech-mesh`
- Cloud Run service: `progretech-mesh`
- Cloud Run region: `us-east1`
- Custom domain: `https://mesh.progretech.com`
- HTTP redirect: `http://mesh.progretech.com → HTTPS`

## Qualification evidence

- PT-2026-044 capability/production convergence commit: `12fdcf2ace28891fc1bcaf42373079630a79e584`
- Artifact Registry pipeline commit: `714326e275e40610c869219c7cd5b7e79a2a51c9`
- First qualified trigger-driven build: `d35240a4-6c72-4c53-9e3d-b48ff9db9ab0`
- Trigger-driven build result: **SUCCESS**
- Trigger build commit matched GitHub main: **PASS**
- Cloud Run image matched GitHub main: **PASS**
- HTTPS custom-domain response: **PASS**
- HTTP → HTTPS redirect: **PASS**
- Existing Mesh regression suite at release reconciliation: **135/135 PASS**

## Release governance

GitHub `main` is the authoritative production release source. Normal production deployment must flow through the Cloud Build trigger and existing Artifact Registry / Cloud Run path. Ad-hoc local source deploys are reserved for explicitly approved recovery or qualification work.

This file was created as the final real-push acceptance event for PT-2026-044. The commit containing this file must itself trigger and successfully complete the production deployment before the release-automation gate is considered fully closed.
