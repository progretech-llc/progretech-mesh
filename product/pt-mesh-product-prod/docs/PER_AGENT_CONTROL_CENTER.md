# ProgreTech Control Center in Mesh

The fleet tile links to `/agents/<enrolled-id>/control-center` for an owned,
verified linked agent. The page explains requirements and data before enabling
actions. Offline agents can still read setup guidance. Operational profiles and
grants persist on the agent host, not in the Mesh registry or browser storage.

## Agent scope and shared devices

Role, user-supplied model access, stack choice, workstation status and voice
preferences belong to the selected agent. Discovery reports runtime primary and
fallback models separately from manual declarations and installed host models.
Declarations do not change OpenClaw instructions or model routing.

Voice settings are saved per agent and used by tuned previews without dispatching
the legacy global `voice.settings` action. Continuous speech still requires a
runtime consumer of these profiles. Audio routing, listening, vision and office
chatter are shared workstation controls; the interface labels this effect and
requires saved grants plus a local advertised capability. Mutations also use the
existing host lock. Readiness does not start devices or install models.

## Multiple roles on one workstation

An administrator-approved local binding maps a Mesh ID to a runtime ID. A host
may advertise linked roles in its own namespace, such as `rend--researcher` and
`rend--coder`. These get independent fleet tiles and profiles, using their host's
authenticated gateway. They do not obtain independent CodeSeal credentials or
pretend to have separate workstations. Independent agents retain normal enrollment.

The gateway reads a token-authenticated local roster on connect and explicit
heartbeat refresh. The cloud accepts only a verified, owned gateway's bounded
namespace. It cannot replace other enrollments or owners. Parent revocation and
disconnect block child controls. The adapter accepts only its own ID or its own
child namespace; the host then enforces exact local bindings. Browser-supplied
runtime IDs, URLs and commands are rejected.

Linked role tiles currently expose Control Center; conversation and live-monitor
enrollment remain the host's existing surfaces. Retiring a local binding removes
its advertised tile on the next successful roster update, without deleting its
local saved profile.

## Reference host integration

`control_center.provider` is portable: supply trusted bindings, a sanitized
discovery callback, an execution callback and qualified capabilities. Implement
only controls the user's runtime supports. `control_center.rend_bridge` connects
this contract to the existing loopback `factory_host` implementation.

For Rend, the local administrator or an agent acting within its existing
installation authority creates `~/.progretech-mesh/control-center-bindings.json`:

```json
{
  "rend": "main",
  "rend--researcher": "researcher",
  "rend--coder": "coder"
}
```

Replace `rend` with the actual enrolled gateway ID, preserving the `--` namespace
for shared roles. Names are not authority; a randomly assigned enrollment ID must
not be silently inferred from a display name. The host validates each runtime
against live OpenClaw configuration before execution.

The reviewed service entry point is `python -m control_center.run_rend`, from this
repository with the existing host's dependencies and configured interpreter. It
imports the existing host bridge, installs the extension, and binds **127.0.0.1:8787**.
Use it as the existing service's entry point rather than starting a second bridge
on the same port. Keep the current local token file and host authentication.
Installation and service restart are release actions; this task does not perform
them. Agents need not ask their owner to SSH or enter credentials: an authorized
adapter/setup workflow can create these local bindings and install the provider.

After activation, reconnect the adapter or request a heartbeat. Load each profile,
grant profile storage and inventory, then save. Missing metadata can be supplied
manually. Additional grants reveal qualified controls; choosing ProgreTech's stack
only identifies the stack and offers a reference voice, without changing runtime
software. Outside users can implement the same provider protocol for their stack.

## Permissions and data

Profile storage, inventory, speaker, workstation, microphone and camera grants
are agent-local. Grants are enforced by the host; disabling a browser button is
not the authorization boundary. New profile data requires the storage grant.
An unchanged existing profile can revoke all grants. Revocation blocks subsequent
requests but does not stop an already-running service; stop it first.

Cloud controls require the signed-in owner, a verified connected gateway,
same-origin POST, bounded payloads and typed actions. Responses are correlated to
gateway and random request ID, and pending state is removed after completion or
timeout. Timed-out mutations are never retried automatically. The PWA bypasses
cache for agent pages and operational APIs.

The loopback provider requires the existing local token. It stores profiles with
0600 files and atomic replacement under `~/.progretech-mesh/agent-profiles/`.
There is one host provider process; its lock does not coordinate separate
processes. Profile retention/deletion is local-owner controlled. Responses are
in-memory on Mesh, subject to the pre-existing single-process relay architecture.

## Validation and release

Run the repository's Python tests with its configured interpreter and
`node --test --test-isolation=none openclaw-plugin-progretech-mesh/control-center.test.js`.
Tests cover ownership, origin, response correlation, binding isolation, local
token auth, consent, revocation, typed profiles and independent voice persistence.
Browser verification uses synthetic agents and providers; it does not certify
microphone, camera, audio playback or real-agent acceptance.

The dirty local checkout differs from production, which still serves revision
`progretech-mesh-00035-mav` (read from Cloud Run on 2026-09-30). Release this feature
as an overlay to that source, preserving `/factory`, owner enforcement and the
existing adapter routing. Do not deploy the dirty working directory wholesale.
Repackage the updated adapter with fresh version/integrity metadata as part of
release. Validate host extension and cloud ownership together before directing
production traffic, with rollback to the prior revision and host entry point.
