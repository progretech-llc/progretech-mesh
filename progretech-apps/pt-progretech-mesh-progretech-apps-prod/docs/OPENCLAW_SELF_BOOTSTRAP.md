# OpenClaw Self-Bootstrap Enrollment

This is the first concrete Universal Agent Enrollment adapter.

The human owner does not install this package. An OpenClaw agent receiving PTM1 is expected to:

1. Inspect PTM1 discovery metadata.
2. Read the universal enrollment protocol and adapter catalog.
3. Identify itself as OpenClaw.
4. Read `/api/enrollment/adapters/openclaw/install-plan`.
5. Download the declared Mesh plugin package.
6. Verify SHA-256 `3e22b589fdb8409cef680e49cd2f34f4a401b9fb04a171a5c9f6f81cbd618271` for the current package.
7. Optionally fetch the helper at `/api/enrollment/adapters/openclaw/bootstrap` and verify helper SHA-256 `7a309839f409cc67199536b28c08e7659c777c9b1b584e76f668db45b9b877d6`.
8. Perform the declared hot-safe managed plugin install after verification; do not wait for generic idle merely because the enrollment chat is active.
9. Use OpenClaw's supported managed plugin installer for the verified local archive:
   `openclaw plugins install <verified-archive> --force --accept-capabilities`
10. Inspect the plugin runtime and probe channels.
11. Complete Mesh activation and outbound connection.

## Why install does not wait for generic idle

OpenClaw's managed plugin installer is the supported route for local/archive plugins. Arbitrary local/archive sources require explicit provenance acknowledgement in noninteractive use, and capability consent is also explicit. For this adapter contract, the managed package install is treated as hot-safe and the helper does not invoke a Gateway/runtime restart. If OpenClaw explicitly reports that a reload/restart is required for activation, enrollment stops with `activation_reload_required` instead of forcing it.

Downloading and verifying the package are read-only. The declared managed install may then proceed during the enrollment turn without a generic idle wait; automatic runtime restart remains prohibited.

## Owner approval

If the agent's normal security policy requires explicit approval before plugin installation, that approval should be requested through the existing owner/agent channel. Mesh does not bypass the policy.

## Acceptance

For Rend, the owner sends only PTM1 through Telegram. Rend must discover and execute this path himself. Any requirement for Edwin to log into Ubuntu or manually run the installation is a failed hands-off enrollment.
