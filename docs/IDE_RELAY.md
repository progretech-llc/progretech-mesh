# Connect a client to an existing OpenClaw agent

Mesh relays requests to the gateway's native agents. Their models, tools and memory stay on the gateway host. Installing Mesh does not require replacing those agents' model providers with Mesh itself.

On the client computer, use an OpenAI-compatible Chat Completions provider with the Base URL and API key from the selected agent's API setup. Preserve existing providers, model defaults and fallbacks unless the owner explicitly chooses to change them. This endpoint is not a direct Claude Code Anthropic Messages endpoint.

Discover the permitted model IDs with authenticated `GET /v1/models`. Use the exact ID returned by Mesh and the same token for `POST /v1/chat/completions`. Do not copy a fixed list of ProgreTech agent names into another user's configuration. Seeing a model in a client catalog is configuration evidence; verify a small actual request separately.

A gateway token lists its intake agent and the current native roles linked through that verified gateway. An imported agent's token remains limited to its own role. IDs are scoped to the gateway so identical native names on different accounts do not collide. The host independently checks the current configured role and trusted local roster before forwarding. Removed and archived roles stop being valid routes. Existing imported `-code` aliases remain bound to the same role; new setup recommends the canonical agent ID.

If no roster is available, setup reports `gateway_roster_unavailable`. Reconnect the gateway and verify its roster before generating setup again. A removed model reports `model_not_allowed`; refresh `/v1/models`. A role removed between discovery and forwarding can report `ide_role_binding_unavailable` or `ide_role_not_available`; do not silently substitute another agent. An expired token must be replaced using that agent's API setup.

The serving agent must keep its actual model provider and fallback assignments. Pointing it back to its own Mesh relay can create recursive routing. The relay credential belongs in the remote client, not as a replacement for the serving agent's inference configuration.
