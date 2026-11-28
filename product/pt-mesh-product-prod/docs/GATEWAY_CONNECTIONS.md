# Gateway connections and saved account setup

The normal OpenClaw flow starts with **Generate connection prompt** on the agent page. The owner supplies a gateway label and authorizes linking, then gives the complete prompt to an agent through its existing chat. Mesh requests the signed identity response and completes CodeSeal verification automatically, even if the owner closes the dialog or navigates to another page. It reports success only after the permanent gateway socket is connected. Manual public-key parameters and signed bundle uploads remain available in Add signed agent.

The prompt includes a SHA-256-pinned portable host bundle and installer. This supplies the local provider previously available only on the reference workstation. The agent installs it using its existing installation authority, with an explicit binding to its actual runtime agent ID. Python venv support, network access to install Flask/psutil, and a supported Node/OpenClaw installation are prerequisites. The Mesh plugin starts the provider on demand; existing port 8787 listeners are left alone. The installer never restarts OpenClaw. Ordinary Mesh chat uses the supported gateway client when the optional HTTP chat API is disabled. The IDE relay requires that API; its prompt directs the agent to enable it through the supported gateway UI while retaining local token authentication. Provider keys and runtime credentials remain on the host.

The provider advertises only supported controls. The portable provider supplies system/model inventory, chat, Factory coordination, chatter, and task/terminal services through the existing host modules. Reference-stack microphone, camera and voice playback controls remain available through an existing compatible provider; installation alone does not create those services or grant their permissions.

Agent fleet, Factory, terminals and Control Center use `/api/status` for transport observations. Host-linked agents follow their owning gateway. The Factory refreshes gateway discovery while open; Control Center follows disconnect/reconnect without a page reload. A working task on the board does not imply a live gateway.

## Durable configuration

`MESH_ACCOUNT_STORE=firestore` is the Cloud Run default (`K_SERVICE` set). It uses the existing default Firestore database and application default credentials. Before deployment, verify that the runtime service account can read/write `mesh_agent_configuration` (typically `roles/datastore.user`). Clients must not have direct access to that collection. Keep one Cloud Run instance and one Gunicorn worker: live socket routing is still process-local.

Outside Cloud Run, the default is SQLite at `instance/accounts.sqlite3`; `MESH_ACCOUNT_DB` can select an existing persistent volume. Both the file and its contents are excluded from Git and container uploads. `MESH_ACCOUNT_STORE=memory` is reserved for tests and explicitly ephemeral deployments.

Only account ownership, public enrollment identity, runtime bindings, labels, role flags and the saved profile are durable. Private keys, reconnect credentials, live activity, chat/terminal content, telemetry and peer connection details are excluded. A restored entry starts offline until its host reconnects. Operational settings and permissions still apply through the host provider; a saved account profile does not authorize workstation operations by itself.

Existing enrolled gateways enter the durable store when they reconnect or the server next handles their configuration. In-memory records lost before this release can still rehydrate through their existing signed reconnect identity. No bulk import of private host data is required.

## Runtime coverage and acceptance

The hosted adapter catalog currently ships OpenClaw support. Hermes discovery in the separate offline desktop registry is not a hosted Hermes gateway adapter; full Hermes enrollment, gateway control and Factory integration are still unimplemented. Do not advertise those as working.

Validation includes ownership and signed enrollment tests, restart persistence for SQLite and Firestore, shared transport projections, gateway package integrity, and desktop/mobile browser checks. The reference OpenClaw gateway was queried read-only and its roster/Factory snapshot were exercised through an isolated portable-provider state directory. No runtime restart, inference turn or production deployment was performed.
