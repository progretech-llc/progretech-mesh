# Mesh OpenClaw Plugin Package Protocol

## Goal

The user should need only Mesh and an existing authorized direct chat with the agent. Workstation access and preinstalled ProgreTech software are not part of normal enrollment.

## Current OpenClaw adapter

- Package ID: `progretech-mesh-openclaw`
- Version: `0.7.7`
- Archive: `progretech-mesh-openclaw-0.7.7.tgz`
- SHA-256: `ffcde913f823ea5986c23a2e445e6cfe4ccb262ae38169ece782db321c7675c3`
- Minimum OpenClaw contract target: `2026.9.3`

SHA-256 is integrity pinning, not identity/signature verification. CodeSeal package verification remains deliberately unimplemented and must not be represented as active until the real verifier is integrated.

## Universal enrollment package flow

1. Mesh generates a self-describing website enrollment message containing PTM1 v3.
2. The agent validates the current sender using its existing owner/policy model.
3. The agent decodes PTM1 and fetches the advertised universal protocol and adapter catalog.
4. No preinstalled ProgreTech component or PTM1 recognizer is assumed.
5. The agent matches its already-known runtime identity against the catalog first; only if unknown may it use the catalog-declared bounded read-only identification probe. It selects exactly one available adapter or stops.
6. The agent downloads only the package/helper URLs declared by Mesh.
7. Declared SHA-256 values must match exactly before installation or staging.
8. The agent uses only its normal supported runtime installer and authority it already possesses.
9. Verified staging and a declared hot-safe managed install may proceed during enrollment without waiting for generic idle. Mesh never automatically restarts the agent/runtime; an explicit reload/restart requirement is reported as `activation_reload_required`.
10. The installed adapter redeems the active user-controlled authorization and stores the local reconnect credential.
11. Mesh observation remains passive/read-only and Mesh conversation state remains independent from Telegram or other existing channels.
12. The agent reports success or the smallest specific blocker through the original chat channel.

The website-generated enrollment message is the bootstrap instruction. A preinstalled recognizer may exist as an optional optimization, but universal enrollment acceptance must not depend on it.

## Package safety

- Fetch only URLs declared by the decoded PTM1/catalog.
- Reject cancelled, replayed/used, invalid, or agent-mismatched enrollment requests.
- Enforce package size and archive-safety limits.
- Reject unsafe archive paths, links, or device members.
- Verify package identity/version and SHA-256 before managed installation.
- Do not search for substitute packages or mirrors if a declared Mesh resource is unavailable.
- Do not bypass sandbox, OS, runtime, or organizational controls.

## Future CodeSeal gate

PTM1 carries package signature metadata, but `codeseal_verified` remains false. Once real CodeSeal package verification exists:

- package identity/signature must be verified locally before extraction/activation;
- CodeSeal failure must stop enrollment;
- Mesh may then display CodeSeal-verified package/core state.

Until then, no production CodeSeal claim is permitted.
