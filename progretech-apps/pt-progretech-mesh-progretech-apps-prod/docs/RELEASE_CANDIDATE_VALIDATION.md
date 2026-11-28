# ProgreTech Mesh v1 — Release Candidate Validation

Perform locally before any Cloud Run deployment.

## Non-interference
With Rend actively working through Telegram, connect/refresh/close/reopen Mesh and
restart only the Mesh gateway. Rend's task and Telegram session must continue.

## Connect Agent
Use Connect agent, copy the request into the existing agent chat, and verify the agent
connects without workstation access. Test replay rejection, cancellation, signature failure, and agent mismatch.

## Channel isolation
Generate Telegram, Mesh, and system/tool activity. Verify All / Telegram / Mesh /
System & tools filters and confirm Mesh conversation remains independent.

## Notifications
Verify reply, task-complete, approval, blocker/error, file-ready and reconnect events.
Routine heartbeat must not notify.

## File exchange
Test text, PDF, image, ZIP, sensitive extension approval, oversize rejection,
content-signature mismatch, interruption cleanup, and reverse download.

## Safe actions
Task/terminal snapshots require approval and remain bounded/read-only. No arbitrary
shell is available.

## Guided Training
Run start-to-finish on desktop, phone width, Fold-cover width, and Fold-inner/narrow
tablet width. It must be skippable/restartable and free of developer terminology.

## PWA
Verify manifest, service worker, install prompt where supported, and API cache bypass.

## Deployment gate
Do not deploy merely because local RC passes. Cloud Run, IAM, secrets, OIDC, CodeSeal,
WSS/reconnect, DNS, `mesh.progretech.com`, and production cutover remain a separate
guided activity.
