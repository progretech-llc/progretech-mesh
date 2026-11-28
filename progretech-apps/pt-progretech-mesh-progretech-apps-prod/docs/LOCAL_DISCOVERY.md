# Local discovery after restart

The local web desktop obtains its roster from the authenticated loopback host
bridge. The bridge queries OpenClaw's public agent inventory and maps those
runtime identities into the existing local Mesh bindings. It retries on later
requests, so gateway startup order does not require re-enrollment. An installed
orchestration CLI alone is not a connected agent or a signed cloud identity.

On Linux the supported CLI lookup uses PATH, then the owner's `~/.local/bin`.
This applies to OpenClaw gateway discovery and the existing offline discovery
allowlist (OpenClaw, Hermes and Claude). Python project entrypoints still need
explicit configuration. Discovery does not scan private memories, install
frameworks, start workloads or create cloud identities.

For an existing host bridge running an older release, install
`systemd/rend-control-center.service.d/local-runtime-path.conf` into
`~/.config/systemd/user/rend-control-center.service.d/`, then run
`systemctl --user daemon-reload` and restart `rend-control-center.service`.
This makes the standard user executable directory available after boot without
changing the gateway or its workloads. Preserve other service overrides.

Validate the authenticated `/api/mesh/control-center/agents?gateway_id=rend`
response on the loopback host and `/api/agents` in local Mesh. A host HTTP 502
with `role_discovery_failed` is a discovery failure, not evidence of zero agents.
Never print the local access token in diagnostics. Verify the same identities
return after restarting the monitoring services. Roll back the service change
by removing only this drop-in, reloading systemd and restarting the bridge.
