# Runtime + Transfer Hardening

Mesh transfer behavior is now bounded, sequence-checked, hash-verified, and ephemeral.

## Browser to agent

Uploads spool to a temporary file rather than retaining the full transfer as a list of
chunks in Flask memory. Mesh validates size, extension policy, selected binary magic
signatures, and SHA-256 before relaying 256 KiB chunks.

The temporary relay file is deleted on success or failure.

## Agent to browser

Reverse transfers spool into a temporary OS file instead of a full Flask bytearray.

Chunk order, declared size, SHA-256, and supported binary signatures are checked before
the artifact becomes downloadable.

Ready artifacts expire and downloaded artifacts are deleted after the response closes.

## Resource defaults

- 20 MiB per file
- 50 MiB per browser session
- 3 active transfers per agent
- 15 minute incomplete-transfer TTL
- 30 minute ready-download TTL
- 256 KiB chunk size

## Failure isolation

Malformed or interrupted transfers clean their partial files and must not restart,
pause, reconfigure, or otherwise interfere with the agent runtime.

No arbitrary shell capability is introduced.
