# Agent-led Mesh enrollment

The normal Mesh user does not need workstation access and no Mesh component is assumed to exist on the agent before enrollment. The website-generated message is the bootstrap instruction.

## Intended user experience

1. Open Mesh and choose **Connect** for an agent.
2. Mesh generates one user-controlled, self-describing enrollment message containing a `PTM1:` envelope plus plain-language machine instructions.
3. Send the complete message to the agent over an already-authorized direct channel such as Telegram.
4. The agent validates the sender using its existing local owner/policy rules.
5. The agent decodes PTM1 and reads the protocol/catalog URLs declared by Mesh.
6. The agent matches its already-known runtime identity against the bounded catalog; only if unknown may it use catalog-declared read-only identification probes. It selects exactly one available adapter or stops.
7. The agent fetches and verifies only the declared artifacts, then installs/stages them using its existing authority and the runtime's supported mechanism.
8. If the install plan marks the managed install hot-safe, the agent may perform it during the enrollment turn. The agent never automatically restarts the runtime; if activation explicitly requires reload/restart, it reports `activation_reload_required`.
9. The adapter redeems the active user-controlled authorization and connects outbound to Mesh.
10. The agent reports success or the smallest specific blocker through the original chat channel.

## Non-interference

Enrollment must never force a restart, reset, session takeover, or interruption of current work. Staging and an install step explicitly declared hot-safe may occur during the enrollment turn when local policy permits it. Automatic runtime restart is forbidden; explicit reload/restart requirements are reported and left to a separate safe maintenance decision.

## Universal bootstrap rule

There is **no trusted enrollment recognizer/bootstrap prerequisite**. A preinstalled recognizer may exist as an optional convenience on some agents, but v1 acceptance must succeed without one. Rend is tested exactly like an unfamiliar third-party agent.

A prompt does not grant privileges. If the agent lacks network/tool/install authority required by the advertised adapter, it must fail closed and report the minimum missing capability rather than asking the owner to bypass policy.

No arbitrary shell is exposed to the Mesh user.
