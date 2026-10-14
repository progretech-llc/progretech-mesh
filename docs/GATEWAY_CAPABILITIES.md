# Imported OpenClaw agent capabilities

Mesh uses the gateway's exact runtime ID for imported agents. Ordinary chat and
Factory native admission do not require the optional ProgreTech workday scheduler.
The gateway still owns native admission and execution; a successful capability
check does not prove gateway health, a model reply, or task completion.

Scheduler state has three meanings:

| State | Chat admission | Pause/wake controls |
| --- | --- | --- |
| Unmanaged: no scheduler helper, state, or remembered integration | Allowed when the agent configuration is usable | Unavailable; sleeping is unknown |
| Managed: scheduler reports this role | Allowed only when awake | Available |
| Unavailable: configured scheduler cannot be read or previously reported roles disappear | Blocked | Unavailable until restored |

A healthy scheduler may leave custom agents unmanaged. Known local runtime
aliases remain `main → rend`, `researcher → lyra`, and `coder → mak`; their
configured controls remain required. Custom role rows are retained rather than
filtered out. Helper errors also block Codex and Moxy; there is no identity-based
exception to an unavailable configured scheduler.

Mesh remembers successfully observed scheduler role ownership in the local,
mode-0600 `.progretech-mesh/scheduler-capabilities.json`. This contains role names
and a schema version, not credentials, work content, or pause values. It prevents
removing a helper or losing a role row from silently making a managed agent
unmanaged. Existing `.local/state/progretech-workday` state is also evidence of
configuration. Restore the configured integration after a failure; do not delete
its state to work around a pause. Scheduler status retains the existing one-second
cache. Removing an integration intentionally is an administrator migration, not
an automatic recovery operation.

Runtime status exposes `chat_available`, `admission_reason`, `scheduler`, and
`active_context_available`. Factory distinguishes an exact binding from current
admission readiness; a paused or unavailable scheduler does not show a runnable
director merely because it is enrolled. New-chat controls are independent of
optional scheduler controls.

Owner steering requires a fresh, exact active-session observation. A host without
that capability returns `runtime_context_unavailable`; it does not guess a
session, read private history, or launch a replacement turn. Custom runtime IDs
can use the existing observer when it supplies their exact role and session.
Shared context reads are separate from active-session steering. Local model
preload and other workstation-specific integrations remain optional and retain
their existing capability limits.

Validation uses temporary homes and simulated scheduler/gateway responses in
`tests/test_gateway_portability.py`, alongside runtime, office lease, enrollment,
and relay suites. These tests do not start native model turns or alter host
configuration.
