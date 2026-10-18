# ProgreTech Mesh

## Connect an existing agent platform

From the agent fleet choose **Connect a computer**, select the platform, name the host and copy its setup prompt to an authorized agent on that host. The agent must have permission to install Python/Node prerequisites, inspect its own platform configuration and start a supervised connector. Private runtime keys and histories stay on the host. Mesh verifies the gateway identity before enabling execution.

Supported routes are OpenClaw's existing native adapter, Hermes profile CLI, OpenCode primary-agent CLI, Open WebUI's `/api` endpoint and OpenAI-compatible `/v1` endpoints such as Ollama. Other platforms require a compatible API; the selector does not claim native support for arbitrary runtimes. An inference-only endpoint does not acquire filesystem or execution tools from Mesh.

Only one gateway can be active per account. A newly verified connection replaces the old host; the old reconnect credential cannot take the slot back. Prior identities and task history remain retained. The connector's explicitly selected prime agent becomes the initial Scrum Master. Fleet/Factory controls can change the Scrum Master among enabled native agents without changing the gateway identity.

The platform bootstrap is advertised with a SHA-256 checksum in the signed-in onboarding instructions. It verifies the host bundle, installs an isolated environment and checks discovery before consuming activation. It prints the exact command and working directory for the host's existing supervisor; the authorized setup agent installs and starts that service. No cloud request can choose an executable, endpoint, secret file, workspace or runtime binding. `--exclude` keeps held profiles visible while denying execution.

Mission Control reports the native roster and configuration. Factory uses the existing host-local persistent board, dependency checks and bounded Scrum workflow. Runtime failure or unconfirmed completion does not mark work successful. Monitoring covers Mesh-owned work; unrelated native sessions are not inferred to be idle or finished. Optional hardware controls are unavailable unless the adapter implements them.

**Copy API relay setup** on an agent card supplies an owner-scoped OpenAI Chat Completions URL, expiring key and exact agent model alias. API adapters forward upstream tool calling; Hermes/OpenCode CLI relays accept text conversations and retain their native tools. Disable client-side tool calling in an IDE when using a CLI agent. The relay does not expose a raw model credential.

Manage and orchestrate agents from your OpenClaw gateway. Monitor each agent, create scoped API relay setups, and coordinate tasks through the Factory Scrum board while execution and data remain on the enrolled host.

A project of **[ProgreTech LLC](https://progretech.com)**, owned and maintained by **Ed Rodriguez**. Third-party components and contributions retain their respective ownership and notices.

[Project website](https://mesh.progretech.com) · [Report an issue](https://github.com/progretech-llc/progretech-mesh/issues) · [Contribute](CONTRIBUTING.md)

<img width="1761" height="900" alt="ProgreTech Mesh agent monitoring dashboard" src="https://github.com/user-attachments/assets/de674b43-4bbb-487e-85bb-ea7617f955c1" />


> Connect an available OpenClaw gateway, import its agents, and manage their work from Mesh. See [Factory workflow](docs/FACTORY_OFFICE.md) for the current workflow.

**ProgreTech Mesh** is an open project exploring how humans can monitor, communicate with, and safely coordinate autonomous AI agents **without taking ownership of the agent runtime away from the user's machine**.

Mesh is designed around a simple principle:

**Connect to the agent. Observe it. Work with it. Don't take it over.**

The agent keeps its own runtime, memory, files, tools, models, tasks, and existing communication channels. Mesh provides a separate operational layer around it.

---

## Why Mesh?

AI agents are becoming increasingly capable of operating independently across local machines, development environments, messaging platforms, and automation systems.

But operating several autonomous agents creates a different problem:

**How do you see what they're doing, communicate with them, exchange artifacts, approve sensitive actions, and understand their health without turning the monitoring system itself into the agent platform?**

Mesh is an experiment in answering that question.

Instead of moving agents into a centralized runtime, Mesh connects to agents where they already operate.

```text
                         ProgreTech Mesh
                               │
                identity / discovery / signaling
                               │
              ┌────────────────┼────────────────┐
              │                │                │
            Rend             Agent B          Agent C
              │
       existing runtime
              │
   ┌──────────┼───────────┐
   │          │           │
 Telegram   Tasks       Tools
   │          │           │
 Memory     Files       Models
```

Mesh is the **control and visibility plane**.

It is not the agent.

---

## Core Principles

### Plug and monitor

Connecting or disconnecting Mesh should never restart, reset, pause, replace, or seize control of an existing agent workload.

### Local ownership

The agent runtime, durable memory, files, tools, credentials, and reconnect identity remain on the owner's machine.

### Independent conversations

A Mesh conversation is separate from Telegram or any other agent communication channel.

Mesh can observe activity across supported channels without merging their conversation histories.

### Direct-first communication

When possible, the owner device communicates directly with the agent.

The intended routing hierarchy is:

```text
Same LAN
   ↓
Direct peer-to-peer
   ↓
Optional encrypted relay
```

Cloud infrastructure can provide identity, discovery, package distribution, and ephemeral signaling without becoming the default conversation pipe.

### Bounded control

Mesh supports explicit, policy-gated actions.

It is deliberately **not an unrestricted remote shell**.

### Ephemeral operational data

Operational conversations, telemetry, task streams, terminal snapshots, and transferred files are intended to remain ephemeral rather than becoming permanent cloud history.

---

## What Mesh Looks Like

Mesh provides a responsive browser/PWA console for a fleet of independently running agents.

Current areas include:

- Agent fleet and identity status
- Gateway connectivity
- Live agent activity
- Heartbeat and telemetry
- Independent Mesh conversations
- Read-only operational snapshots
- Policy-gated approvals
- Bidirectional file exchange
- Per-agent notifications
- Guided Training
- Direct/P2P routing controls
- PWA/mobile/foldable layouts

The live monitor uses a terminal-style stream with explicit traffic direction:

```text
SYS  Gateway connected
SYS  Passive monitoring active

OUT  User → Agent
     Review the current task.

IN   Command acknowledged

IN   Agent → User
     Task completed.

FILE Agent offered artifact
     report.html
```

This makes the communication boundary visible rather than hiding agent operations behind a conventional chat interface.

---

## Agent-Led Enrollment

A major design goal is **zero-workstation onboarding for the owner**.

The user should not need to SSH into the agent machine, open a terminal, install a Mesh client manually, or manipulate the agent filesystem.

Instead:

```text
Open Mesh
    │
    ▼
Choose Connect Agent
    │
    ▼
Mesh generates an enrollment instruction
    │
    ▼
Send it through an existing authorized
conversation with the agent
    │
    ▼
Agent validates the request
    │
    ▼
Agent discovers and verifies its adapter
    │
    ▼
Agent installs/configures it using
its existing authority
    │
    ▼
Agent connects to Mesh
```

Enrollment is bounded and fail-closed.

A successfully enrolled agent receives a durable local reconnect credential so subsequent connections do not require repeating discovery or installation.

---

## Per-agent ProgreTech Control Center

Linked agents have their own Control Center entry in the fleet tile, with agent-local
profiles, role/model discovery, manual setup, voice previews and explicit data permissions.
Roles sharing one workstation keep separate profiles through their verified host gateway.
Setup includes Minimum Requirements and Rend’s dated stack reference.
See [the integration guide](docs/PER_AGENT_CONTROL_CENTER.md) for setup and runtime limits.

## Connect your gateway and use the Factory

An available **OpenClaw gateway is required** to import and run agents in this release. Mesh manages the agents and their work; the gateway host supplies their runtime, tools, files and memory.

1. Sign in to Mesh and enroll your OpenClaw host using **Add signed agent** and the generated setup instructions. Complete the host connection and identity verification.
2. Import the gateway's configured agents into your fleet. Each imported agent has its own monitor, conversation and scoped API relay setup for compatible external tools.
3. Choose a **Scrum Master** from an agent card, or double-click an agent on the Factory canvas. Its yellow pulse identifies the coordinating role.
4. Create an **Intake** task with a clear brief. The Scrum Master assigns or performs the work on the host, records progress, asks for clarification when needed, and reviews completion evidence.
5. Use the separate chatter terminal to enable conversations among available idle agents. Chatter is distinct from task execution and remains subject to host resource availability.

The persistent Factory board supports editing, assignment, comments, dependencies, deletion and card movement. Tasks with active or uncertain execution are protected from destructive changes. See [Factory workflow and limits](docs/FACTORY_OFFICE.md), [agent management](docs/AGENT_MANAGEMENT.md) and [trusted enrollment](docs/TRUSTED_ENROLLMENT_BOOTSTRAP.md).

**Mission Control** at `/mission-control` retains workstation controls. `/factory` uses the pinned Munder Difflin host ledger and OpenClaw native execution; optional CrewAI integration is separate from this default workflow.

## Reference host: Rend

Rend is a reference OpenClaw host used for integration qualification. Mesh connects through its defined adapter and authenticated protocol; it does not take ownership of the underlying agent runtime. Additional runtimes remain future adapter work, not an alternative supported onboarding path in this release.

---

## Adapter Architecture

OpenClaw is the supported gateway today. The following diagram describes potential future adapters, not currently available runtime imports.

```text
                         Mesh Protocol
                              │
              ┌───────────────┼───────────────┐
              │               │               │
          OpenClaw        Runtime B       Runtime C
           Adapter          Adapter         Adapter
              │               │               │
           Agent A          Agent B         Agent C
```

Adapters are responsible for translating runtime-specific capabilities into Mesh concepts such as:

- passive observation
- heartbeat
- runtime status
- isolated conversation
- safe actions
- file exchange
- reconnect lifecycle

Mesh should not require recursive inspection of an unknown agent framework or unrestricted workstation access to discover how it works.

---

## Direct-First Architecture

The long-term architecture separates the control surface from the agent runtime and prefers direct owner-to-agent transport.

```text
OWNER DEVICE / PWA
      │
      ├──────── Same LAN ─────────────────────┐
      │                                       │
      ├──── WebRTC peer-to-peer ──────────────┤
      │          ▲                            │
      │          │ signaling                  │
      │      Mesh service                     │
      │                                       ▼
      └──── Optional encrypted relay ──► LOCAL MESH ADAPTER
                                                │
                            ┌───────────────────┴──────────────────┐
                            │                                      │
                     Passive Observation                 Mesh Conversation
                            │                                      │
                            └───────────────────┬──────────────────┘
                                                ▼
                                         AGENT RUNTIME
```

Mesh currently uses a Flask/PWA architecture with the OpenClaw gateway adapter. The direct data-plane diagram above describes the longer-term architecture, not a claim that every transport is released.

---

## File Exchange

Mesh supports bounded bidirectional file exchange.

### User → Agent

Files are transferred through the authenticated Mesh connection and delivered into the adapter's controlled inbox.

Transfers include:

- file-size limits
- SHA-256 verification
- temporary staging
- atomic completion
- bounded concurrency
- extension/content policy
- no automatic execution

### Agent → User

Agents can offer generated artifacts back through Mesh.

Files remain ephemeral and can be retrieved by the user through the Mesh interface.

Mesh is not intended to become permanent artifact storage.

---

## Security Model

Security boundaries are part of the product architecture rather than an optional hardening phase.

Mesh follows several rules:

- Enrollment must originate from an already-authorized agent conversation.
- Agent packages and helpers must pass declared integrity verification.
- Unknown runtime behavior fails closed.
- Arbitrary remote shell access is not exposed.
- Reconnect credentials remain agent-local.
- Sensitive operational content should not appear in notifications.
- Production identity must use real authentication.
- Production trust claims require real cryptographic verification.

Development identity scaffolding must never be presented as production trust.

---

## Munder Difflin Integration

Mesh may integrate in the future with **Munder Difflin**, an independent open-source project by **Chaitanya Giri**:

https://github.com/chaitanyagiri/munder-difflin

Munder Difflin is not a ProgreTech product and is not maintained or owned by ProgreTech.

Mesh is distributed under the ProgreTech Public Source License in LICENSE.md. Munder Difflin source retains its own MIT license; redistribution must preserve its copyright and license notice.

The intended integration boundary is:

```text
                    Munder Difflin
              third-party visualization/control
                         │
                         ▼
                 ProgreTech Mesh
            policy + identity + live state
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
            Rend       Agent B    Agent C
```

Munder Difflin may consume Mesh topology, health, runtime state, metrics, activity, and timeline information for visualization.

Supervisory actions should flow through Mesh's authenticated and policy-gated interfaces rather than creating a second unrestricted control path into an agent.

This integration is a future requirement and is **not part of the current RC acceptance gate**.

---

## Technology

The current implementation is intentionally lightweight.

| Layer | Technology |
|---|---|
| Backend | Python / Flask |
| Frontend | HTML, CSS, vanilla JavaScript |
| Application | Progressive Web App |
| Realtime gateway | WebSocket |
| Direct data plane | WebRTC / RTCDataChannel |
| NAT traversal | STUN |
| Optional fallback | TURN |
| Reference runtime | OpenClaw |
| Reference adapter | Native OpenClaw plugin |
| Telemetry | psutil |
| Integrity / credentials | Cryptographic + signed credential boundaries |
| Production target | Google Cloud Run |

The architecture is expected to evolve as real multi-agent deployments expose requirements that cannot be learned from mocks.

---

## Project Status

**Current stage: v1 RC2 — live integration and acceptance**

Mesh is actively being developed and tested. It should **not** currently be treated as production-ready software.

Live acceptance with Rend has already demonstrated several important behaviors, including:

- hands-off agent enrollment
- signed local reconnect identity
- automatic reconnect after Mesh becomes unavailable
- passive monitoring
- outbound command delivery and acknowledgement
- isolation from the existing Telegram conversation
- readable bidirectional operational signaling

Current work is focused on completing:

- isolated Mesh conversation acceptance
- bidirectional file-transfer acceptance
- safe-action/snapshot acceptance
- active-task non-interference testing
- same-LAN direct transport
- remote P2P transport
- relay policy behavior
- offline PWA reconnect
- production authentication and trust integration

The project intentionally prioritizes **real-agent acceptance over feature count**.

---

## What Mesh Is Not

Mesh is not:

- a replacement for an agent runtime
- a hosted AI-agent platform
- a Telegram replacement
- an SSH frontend
- unrestricted remote administration
- permanent agent memory
- permanent conversation storage
- a mechanism for bypassing an agent's existing permissions

Those boundaries are intentional.

---

## Repository Structure

```text
progretech-mesh/
├── main.py
├── templates/
├── static/
│   ├── css/
│   ├── js/
│   ├── manifest.webmanifest
│   └── sw.js
│
├── openclaw-plugin-progretech-mesh/
│   ├── index.js
│   ├── package.json
│   └── openclaw.plugin.json
│
├── distribution/
│   ├── adapter packages
│   ├── enrollment protocol
│   ├── adapter catalog
│   └── acceptance manifest
│
├── docs/
│   ├── architecture
│   ├── routing
│   ├── enrollment
│   └── acceptance
│
└── tests/
```

---

## Running Locally

For the fully local desktop edition, see [Mesh Offline](docs/MESH_OFFLINE.md). Its Ubuntu and Windows installers bundle the application runtimes, inference engine and a starter model. Local agent onboarding requires no CodeSeal or signing keys.

Mesh is currently an RC/development project.

A typical development environment uses Python 3.12+.

```bash
git clone https://github.com/progretech-llc/progretech-mesh.git
cd progretech-mesh

python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the repository requirements:

```bash
pip install -r requirements.txt
```

Then start the development server using the configuration appropriate to your environment.

> **Important:** Development authentication, local HTTP allowances, test credentials, and RC enrollment behavior must not be interpreted as production security configuration.

See the project documentation before exposing a development instance outside a trusted test environment.

---

## Contributing

Mesh is being developed in public because agent interoperability, local ownership, monitoring boundaries, and human control are problems worth exploring with the broader community.

Contributions and technical discussion are welcome around areas such as:

- agent runtime adapters
- agent interoperability
- WebRTC and NAT traversal
- local-first architecture
- safe agent supervision
- agent observability
- capability negotiation
- trust and signing
- accessibility
- PWA/mobile UX
- privacy-preserving telemetry
- multi-agent visualization

If you are experimenting with another autonomous-agent runtime and think it could be a useful Mesh adapter target, opening a discussion or issue is especially useful.

Before submitting substantial implementation work, please open an issue describing the proposed change and how it preserves Mesh's security and ownership boundaries.

---

## Community & Research

Mesh is as much an exploration of **how autonomous agents should be operated** as it is a software project.

Some of the questions driving the project are:

- Can independently developed agents expose a common operational interface?
- How much observability can we provide without centralizing agent state?
- Can an agent safely enroll itself without asking its owner to administer the workstation?
- What should an agent control plane be allowed to do?
- How should human approvals cross an agent boundary?
- Can local-first agents remain useful when cloud infrastructure disappears?
- How should a fleet of heterogeneous agents expose capabilities without surrendering autonomy?

If those problems overlap with work you're doing, contributions, experiments, issue reports, architecture discussions, and adapter prototypes are welcome.

---

## Roadmap

The immediate goal is **v1.0 acceptance**, not rapid feature expansion.

Broadly:

**RC2 → live acceptance → production identity/trust → v1.0**

Future work includes broader runtime adapters, stronger visualization and fleet management, closed-PWA notifications, production trust infrastructure, scale testing, and Munder Difflin integration.

The roadmap will evolve based on observed behavior from real autonomous agents rather than assumptions made solely during development.

---

## License

See [`LICENSE.md`](LICENSE.md) for ownership, attribution, redistribution, and modification terms.

Please review the license before redistributing or incorporating ProgreTech Mesh into another product.

---

## ProgreTech

ProgreTech Mesh is developed by **ProgreTech LLC** as part of its work exploring practical autonomous-agent systems, developer tooling, AI-assisted software engineering, and local AI infrastructure.

The project is under active development.

**Issues, technical discussion, adapter experiments, and constructive feedback are welcome.**

---

*Built around a simple idea: the agent can remain autonomous without becoming invisible.*

## Collaboration

Adapter documentation, accessibility, connection diagnostics, and reproducible enrollment failures are useful ways to help. Read [CONTRIBUTING.md](CONTRIBUTING.md) for issue reports, proposed changes, and attribution requirements.

## License and reuse

This repository uses custom ProgreTech source-available terms; see [LICENSE.md](LICENSE.md). Read the permitted uses, attribution, and contribution terms before reusing or submitting code. Public visibility is not an OSI-approved open-source license.

Preserve [third-party notices](packaging/THIRD_PARTY_NOTICES.md), including the separate licenses for bundled runtimes, libraries, model weights, and Munder Difflin. The project license does not replace upstream terms.

## More from ProgreTech

[Open Mesh](https://mesh.progretech.com) (sign-in required). Explore [CodeSeal](https://codeseal.progretech.com) for signed software provenance and [Atlas](https://atlas.progretech.com) for opportunity and evidence research.

Discover the wider portfolio at [progretech.com](https://progretech.com). These links identify related products; they do not imply a bundled integration or shared license.
