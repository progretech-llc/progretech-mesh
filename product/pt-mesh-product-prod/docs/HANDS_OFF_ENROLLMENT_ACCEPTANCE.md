# Hands-off Enrollment Acceptance

The live Rend acceptance is successful only if all of the following are true:

- Edwin opens Mesh and selects Connect.
- Mesh creates PTM1.
- Edwin sends PTM1 to Rend through the existing Telegram chat.
- No workstation login occurs.
- No ZIP/file attachment is sent by Edwin.
- The baseline recognizer accepts only an owner-authorized direct message.
- Rend downloads the exact package named in PTM1.
- A bad hash is rejected before activation.
- Replayed/used/cancelled or invalid activation is rejected by Mesh.
- Verified staging and the declared hot-safe managed plugin install may occur during the enrollment turn; the enrollment chat itself must not create an idle deadlock.
- Telegram work is not cancelled, reset or replaced.
- Mesh enrollment never automatically restarts the OpenClaw Gateway/runtime. If a reload/restart is explicitly required, the attempt stops with `activation_reload_required`.
- Telegram remains healthy throughout installation/activation; no enrollment-triggered restart is expected.
- Mesh connects outbound using the stored local credential.
- Telegram activity appears in Mesh observation.
- Mesh conversation uses its own Mesh session and does not alter Telegram context.
- Disconnecting/reloading Mesh does not interrupt Rend's Telegram work.
