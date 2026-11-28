# Enrollment, communication and factory runtimes

## Add an independently running agent

1. Open **Add signed agent** and enter its name and descriptive role.
2. Import an existing Ed25519 public key and CodeSeal evidence, or choose **Generate identity & download private key**. Keep the private PEM on the agent workstation. Mesh never needs your private key.
3. For a new seal, obtain a personal API token from your verified CodeSeal account. Generate the CodeSeal key in the popup. The browser signs the identity request; the CodeSeal registry checks key possession and issues signed evidence tied to the public key and agent ID. This records identity provenance, not software safety.
4. Save the downloaded public-key/evidence bundle and private key on the agent. The OpenClaw adapter expects `<agent-id>_identity_public.pem`, `<agent-id>_identity_private.pem`, and `<agent-id>_codeseal_evidence.json` under `~/.config/progretech/mesh/identity/`. Extract the public key and `codeseal_evidence` from the bundle into those files. Private files must be owner-readable only.
5. Choose **Verify & enroll**, then **Connect agent**. Copy its enrollment message to the agent and follow the supported adapter instructions. Key generation alone does not connect a runtime.

A CodeSeal key is a PTCS registry seal ID with a signed manifest. A legacy `CS-…` string is not accepted as production evidence. An agent's public identity key is an Ed25519 PUBLIC KEY PEM; it is not an LLM API key, an account password, or the private signing key.

Linked roles such as Lyra and Mak share Rend's gateway identity. They have exact local bindings, separate communication preferences and Mesh conversation sessions. They do not need new independent device credentials.

## Manage

Select an owned agent under **Manage**. The host returns its communication role and configured primary/fallback and permitted communication models. Save a model choice to use an `x-openclaw-model` override for Mesh conversations without rewriting global runtime defaults. The role stays bound to the selected runtime identity; role changes cannot impersonate another agent.

The gateway must have its authenticated Chat Completions endpoint enabled. Messages are submitted through the selected agent's verified host into a separate `mesh-chat` session, independent of Telegram/IDE sessions. This UI conversation path uses the Mesh host relay; file/direct-monitor transports retain their existing behavior. A timeout does not cause an automatic retry because an agent run may still complete.

**Remove from Mesh** persists a host-local enrollment opt-out. Linked roles stop being advertised. Removing a gateway also disables adapter auto-reconnect through its existing revocation marker; its child tiles disappear. Files, runtime, tools, models and memories are preserved. To re-enroll, the host administrator must deliberately re-enable the corresponding `.communication.json` preference and redeem a fresh authorized enrollment to clear the adapter revocation marker. An offline/unreachable host cannot acknowledge a durable removal; Mesh reports that blocker rather than claiming it removed the runtime.

## Local/offline and hosted use

Run Mesh locally with the existing local run instructions and connect the gateway to that local origin. Use the same management UI and host bridge. Local inference can continue without internet after dependencies/models are installed. Hosted Mesh still needs internet and does not itself make remote runtimes offline.

For offline identity verification run CodeSeal locally with its registry database and signing keys intact. Set `APP_ENV=development`, `CODESEAL_VERIFIER_MODE=configured`, `CODESEAL_VERIFY_URL=http://127.0.0.1:<port>/api/v1/verify`, and `CODESEAL_API_URL=http://127.0.0.1:<port>/api/v1`. Only loopback HTTP is allowed outside production. Production CodeSeal remains HTTPS and checks active registry evidence.

## CrewAI and OpenHands

Install factory libraries in separate supported environments, not Mesh's Python 3.14 environment. CrewAI currently requires Python >=3.10,<3.14. Install `crewai[litellm]` in its environment. Install matching `openhands-sdk` and `openhands-tools` versions together in the OpenHands environment. Pin versions after qualifying your chosen runtime/model. Download dependencies before offline operation.

Create `~/.progretech-mesh/factory-runtimes.json` on the host (mode 0600):

```json
{
  "crewai": {"enabled": true, "roles": ["main", "researcher"], "python": "/absolute/crewai-env/bin/python", "workspace": "/absolute/approved/workspace", "model": "ollama/your-installed-model", "base_url": "http://127.0.0.1:11434", "api_key_env": "FACTORY_LOCAL_API_KEY"},
  "openhands": {"enabled": true, "roles": ["coder"], "python": "/absolute/openhands-env/bin/python", "workspace": "/absolute/isolated/task/worktree", "model": "openai/your-installed-model", "base_url": "http://127.0.0.1:your-port/v1", "api_key_env": "FACTORY_LOCAL_API_KEY"}
}
```

Use actual installed model names/ports. Configure credentials only in the host service environment. The web UI cannot supply executables, workspace paths, URLs or credentials. **Check factory setup** reports configuration, not model qualification. **Start factory task** submits a bounded task and returns a job ID; use **Refresh task status**. A host admission lock allows one job at a time. Jobs time out after 30 minutes. CrewAI performs planning/review with two coordinated agents. OpenHands uses its SDK terminal, file editor and task tracker in the explicitly configured workspace and can execute commands/edit files. Only enable it for trusted owners and an isolated task worktree. Job status is agent-role scoped; outputs stay in `~/.progretech-mesh/factory-jobs/<role>/` with owner-only permissions. Host restarts can interrupt running jobs; reconcile interrupted status before retrying.

Official references: [CrewAI](https://github.com/crewaiinc/crewai), [CrewAI LLM configuration](https://docs.crewai.com/en/concepts/llms), [OpenHands](https://github.com/OpenHands/openhands), [OpenHands SDK](https://docs.openhands.dev/sdk/getting-started), [OpenClaw Chat Completions](https://docs.openclaw.ai/gateway/openai-http-api).
