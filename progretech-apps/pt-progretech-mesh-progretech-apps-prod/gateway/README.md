# ProgreTech Mesh Gateway — Phase 6 of 7

The gateway now supports:

- heartbeat and telemetry
- direct/group message transport
- bounded incoming file transfer
- agent-to-user file offer
- safe policy-approved snapshots

## Local file staging

Received files are written under:

```text
.mesh-staging/
```

The gateway verifies:

- filename sanitization
- expected byte length
- SHA-256

before writing the file.

## Safe action boundary

Approved actions currently include only:

```text
request_status
request_task_snapshot
request_terminal_snapshot
```

The gateway does not expose arbitrary shell execution.

## Demo agent-to-user artifact

Mesh can ask the gateway to generate a small demo text artifact.

This proves the reverse file-transfer path without depending on a real AI runtime.

## Production note

Phase 6 uses Base64 file payloads for bounded development transfers.

Phase 7 should replace this with chunked/streamed transfer while keeping the same
policy and identity boundaries.
