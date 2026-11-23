# Mesh installation, operations, and recovery

Status: pending buyer and Quality review. Source baseline: `86dc872d71ec2f668174f632092b371f57cf24c0`. These draft instructions are not approval to install into a customer environment. No commercial package, supported buyer version, paid archive, price, support/SLA, or hosted SaaS offer is established by this candidate.

## Install boundary

Use only a future exact package whose source revision, dependencies, integrity record, license, configuration profile, and rollback process have passed the normal release gates. No such buyer package is qualified here. Do not use production credentials or connect real gateways while evaluating this draft.

For an isolated source review on a disposable private host, the current source declares Python 3.12 in its Docker image and starts Gunicorn as the WSGI server. `requirements.txt` contains version ranges, so the following commands are only an illustration for a controlled review environment. They do not produce a reproducible or supported production install:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/gunicorn --bind 127.0.0.1:8080 --workers 1 --threads 80 --timeout 0 main:app
```

Keep the listener on loopback for this isolated review. Do not expose it to a LAN or the Internet. Do not insert real secrets, customer identity maps, databases, or gateway addresses. Quality must determine required environment settings and lock exact supported dependencies before this guide can become operational.

Mesh's Flask server and the native host connector are separate deployment targets. Keep `openclaw-plugin-progretech-mesh/`, the Office Node provider, and the host Python bundle intact; do not treat installing the Flask server as installing or qualifying those connectors. The Dockerfile intentionally runs one worker because live WebSocket and session state is process-local. Do not add replicas or workers without a separately reviewed shared-state design.

## Operations

Before any buyer release, operators need an exact, reviewed configuration matrix. Current source reads selectors including `MESH_ENVIRONMENT`, `MESH_PUBLIC_ORIGIN`, `MESH_AUTH_MODE`, `MESH_FIREBASE_*`, `MESH_OWNER_UID_BINDINGS`, `MESH_ACCOUNT_STORE`, and `MESH_ACCOUNT_DB`. The presence of a selector does not identify a safe value or a supported deployment profile. Choose values only through an authorized buyer-owned configuration process. Keep secrets in the buyer's secret manager or protected runtime injection, not in source, shell history, tickets, screenshots, logs, or this guide.

`mesh_account_store.py` has SQLite and Firestore implementations. The application's default depends on its environment; memory is used in testing. Quality must prove the selected production backend, access controls, durability, backup and restore before recommending one. Account configuration is distinct from process-local live connections, sockets, events and active transfers. Restarting the service cannot restore those live sessions.

For this source baseline, the Cloud Run template is Knative/Google Cloud Run, not Cloud Foundry or SAP BTP qualification. No SAP tenant connector or BTP deployment profile is claimed.

## Recovery

1. Stop changes and record the exact package revision, configuration schema version, storage backend, and time of failure. Never copy secret values into the incident record.
2. Keep the affected service isolated. Do not enroll or reconnect a real gateway as a recovery test.
3. Restore a buyer-owned backup into a separate recovery environment using the selected backend's reviewed procedure. Do not overwrite the only backup or restore unverified configuration into the live service.
4. Confirm the restored account configuration and ownership boundaries with synthetic identities. Treat sockets, active sessions, transient events and transfers as lost; they are process-local, not backup data.
5. Validate authentication, owner separation, connector compatibility, and rollback only in the isolated environment. Preserve the original host's native runtime, permissions, workloads and credentials.
6. Return to service only through the future approved release and recovery procedure. This draft defines no key-rotation command, production rollback command, or buyer support channel.

Do not remove original source charters, notices, roadmap, or connector distributions during installation or recovery. This guide remains pending until exact-package install, configuration, persistence, backup/restore, upgrade/rollback, security and localized-documentation gates pass in Quality.
