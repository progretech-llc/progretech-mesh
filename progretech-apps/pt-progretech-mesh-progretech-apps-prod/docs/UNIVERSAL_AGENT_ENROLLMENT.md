# Universal Mesh Enrollment — Agent Instructions

You are being asked by your owner to connect yourself to ProgreTech Mesh.

Assumptions:
- You may not contain any ProgreTech components yet.
- Your owner may not have workstation access.
- You must use only permissions and tools you already possess.
- You must not interrupt/reset/cancel current work.
- You must not bypass local policy or security controls.
- Enrollment is bounded; self-service does not mean open-ended self-discovery.

## Procedure
1. Decode the PTM1 enrollment envelope.
2. Read `discovery.protocol_url`.
3. Read `discovery.adapter_catalog_url`.
4. Identify your runtime from self-identification metadata you already have. Compare that name to `runtime_match.names`.
5. If the runtime name is genuinely unknown, run only catalog-declared read-only `identification_probes`: at most one per available adapter and at most three probes total.
6. Do **not** recursively inspect framework internals, scan the filesystem, enumerate unrelated tools/plugins, or search the public web to determine compatibility.
7. Select exactly one adapter whose `status` is `available`. Never try multiple adapters in one enrollment request. If no single adapter matches, stop with `runtime_unknown` or `unsupported_runtime`.
8. Fetch only that adapter's declared install plan/package/helper and verify declared hashes/signatures before installation.
9. Follow the declared install plan exactly using existing authority. Do not invent alternate install strategies, modify unrelated configuration, or escalate privileges.
10. Verified staging and an adapter install explicitly declared `hot-safe` may proceed during the enrollment turn; the enrollment conversation itself is not a reason to wait for idle. Never restart the agent/runtime automatically. If OpenClaw explicitly reports that activation requires reload/restart, stop with `activation_reload_required` and preserve current work.
11. Redeem the active user-controlled enrollment authorization and establish an outbound connection to Mesh.
12. Verify passive monitoring is read-only and keep Mesh conversation/session state independent from existing channels.
13. Retry a failed step at most once, and only when the protocol/install plan explicitly declares a recovery action.
14. Target total enrollment time is **5 minutes**. At **10 minutes of active diagnostic work**, stop and report the smallest blocker. The authorization remains active for a later retry unless the user cancels it or it is successfully redeemed.
15. Report success only after Mesh confirms connection/activation. Installation alone is not success.

## Failure rule
If you cannot complete a step, do not improvise or broaden the search. Stop at the first stable failure boundary and report only the smallest missing permission, capability, compatibility, verification, or transport blocker.


## Reconnect and re-authorization fast path

PTM1 is an authorization envelope, not a command to reinstall on every connection. The agent must check existing Mesh state first. If a compatible adapter and valid reconnect credential already exist, reconnect immediately and skip discovery, runtime identification, package verification, and activation redemption. If the adapter exists but the reconnect credential is missing, expired, or revoked, use the active PTM1 authorization to re-authorize the existing installation and obtain a new reconnect credential. Do not reinstall or rediscover the runtime.

Activation codes are single-use and remain active until the user explicitly cancels the request or the agent successfully redeems it. There is no normal time-based expiry. A cancelled/replayed/used activation ends that attempt immediately; the agent must not continue into discovery or diagnostics.

The PWA may retain non-secret pairing metadata locally so previously paired agents can be presented as reconnectable without turning browser storage into the credential store.

### Existing Mesh listener during an upgrade
A stable local signaling listener already bound by a verified earlier ProgreTech Mesh adapter is not an unrelated port conflict. The new adapter must verify ownership using the existing Mesh-local access credential and reuse the listener during the handoff. Never kill an unknown process merely to claim the port. Unknown ownership remains a fail-closed `port_conflict`.
