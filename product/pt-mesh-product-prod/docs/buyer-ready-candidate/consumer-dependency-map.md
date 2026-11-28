# Mesh source consumer and dependency map

Status: pending Quality review. This is a source-level integration map, not a commercial package manifest, release approval, or buyer support promise.

Baseline: accepted Mesh source `86dc872d71ec2f668174f632092b371f57cf24c0`. The map and candidate interface add no authentication, account, pairing, gateway, connector, hardware, or payment behavior. The candidate must keep the accepted Python/Flask control plane and existing Node/native host paths together.

## Consumers and boundaries

| Consumer | Source paths | Role and boundary |
|---|---|---|
| Browser control plane | `main.py`, `templates/`, `static/` | Flask WSGI app, browser/PWA assets, HTTP routes, session setup, WebSocket routing, live process-local registry. `Dockerfile` starts `main:app`. Keep the accepted single-process live-state constraint; the Dockerfile explicitly runs one Gunicorn worker. |
| Python runtime | `requirements.txt`, `main.py` | Flask, Gunicorn, Werkzeug, Flask-Sock, WebSocket, process inspection, cryptography, Firebase Admin, Pillow and YAML dependencies. The entries are version ranges, not a resolved buyer lock or SBOM. `requirements-office.txt` and `requirements-offline.txt` serve separate build/runtime targets. |
| Durable account configuration | `mesh_account_store.py` | `AccountStore` implements SQLite and Firestore paths. It persists selected owner-scoped enrollment/configuration fields; live connections and activity stay process-local. SQLite path is selected through `MESH_ACCOUNT_DB`; the application chooses `MESH_ACCOUNT_STORE` based on environment when unset. A backend branch in source is not a qualified buyer persistence profile. |
| Existing web identity and ownership | `mesh_firebase_auth.py`, `mesh_owner_access.py`, `mesh_account_security.py`, `mesh_progretech_auth.py` | Existing login, owner-binding and canonical account-status boundaries. `MESH_AUTH_MODE`, `MESH_FIREBASE_*`, and `MESH_OWNER_UID_BINDINGS` are configuration selectors. Do not copy host-specific identity mappings, production adaptation, account records, tokens or credential values into a candidate or guide. No auth changes are part of this task. |
| Host-side Python provider | `mesh_host_distribution.py`, `control_center/*.py`, `gateway/platform*.py`, `offline/` | `host_bundle()` explicitly packages Control Center Python modules, `office/engine.mjs`, the offline package and gateway platform modules, plus a generated host requirements file. Preserve these consumers and their separate host boundary. |
| Node/OpenClaw connector | `openclaw-plugin-progretech-mesh/` | Native extension package, its `index.js`, tests and declared `node-datachannel` dependency. `package.json` declares OpenClaw as a peer dependency. This is a functional host connector, not a server-side asset to drop during Flask distribution. |
| Office provider | `office/engine.mjs`, `office/engine.ts`, `office/package.json` | Separate Node build using the declared `esbuild` tool. Keep it separate from the Flask server image unless a reviewed distribution explicitly includes it. |
| Release and update artifacts | `distribution/`, `scripts/`, release manifests and checksum references | Bootstrap, host bundle, platform updates and historical connector archives have live consumers and integrity bindings. Resolve each artifact by its manifest and source references before any future pruning; filename similarity does not establish interchangeability. |
| Optional desktop/offline surface | `offline/`, `requirements-offline.txt` | Separate offline package and build dependency set. It is not installed by the Flask Dockerfile. Preserve its rights and consumer contract. |
| Verification fixtures | `tests/`, `openclaw-plugin-progretech-mesh/*.test.js` | Python and Node test suites cover distinct control-plane and native connector paths. Quality must select and run them in the actual isolated Quality candidate; no Development test run is claimed here. |
| Original project requirements | `README.md`, `docs/POST_INSTALL_HANDOFF.md`, `docs/The_ProgreTech_Project_Charter.html`, `docs/MESH_TARGET_FEATURES_CHARTER.html`, and the retained roadmap | Keep original source notices, charters and roadmap. The accepted baseline inventory is 2,866 tracked files: 151 server UI/configuration, 72 buyer/roadmap docs, 120 host/native connector files, 57 connector distributions, 111 test files and 2,355 vendor/reference files. The baseline inventory is recorded at `commercial-distribution-inventory.json` (SHA-256 `0f5aa8d4b27752d1117ffc207e600933fdb93325e4ab00250cf29e41a5490644`). This map is not an allowlist and removes no files. |

## Buyer-owned integration contract

`mesh_buyer_interfaces.py` defines structural contracts for an already-verified principal, owner-scoped storage, and configuration. It is intentionally not imported by `main.py` and has no default adapter. `BuyerPrincipal.subject_id` identifies the verified actor; `owner_id` must come from the server's existing trusted owner resolution, never from an untrusted request field. The identity provider does not verify credentials or issue sessions. Storage must authorize every operation using that trusted principal. Configuration separates non-secret settings from secret retrieval; secrets must not be logged, serialized into account records, or copied into source.

The contract is an integration seam for later buyer-specific composition. It does not replace `AccountStore`, `fleet_owner_id`, Firebase login, ProgreTech account status, gateway enrollment or connector behavior. Quality must review typing, authorization boundaries, privacy, compatibility and tests before any production integration.

## Package and hosting boundaries

- The current `requirements.txt` uses ranges. No exact buyer lock, SBOM, signed package, CodeSeal, or commercial source contract is created here.
- Preserve the current source `LICENSE.md` and all third-party notices; do not change rights while mapping consumers.
- The existing `cloudrun/service.template.yaml` is a Knative/Google Cloud Run template. It does not qualify Cloud Foundry or SAP BTP deployment. Any SAP/BTP work needs its own approved scope and evidence.
- No paid archive or buyer guide binding currently exists. Do not infer a sale version, price, hosted SaaS tier, support/SLA, or entitlement from the source baseline.
- Current public `mesh.progretech.com` requires sign-in. This candidate does not change the public site or demonstrate authenticated buyer or native-gateway behavior.

## Next Quality work

Use the committed exact candidate as input. Verify the complete source inventory and charters, inspect private-data and secret boundaries, check the new interface against current identity/storage/configuration code, run the relevant Python and Node suites, and prepare a separate clean-buyer package/configuration/recovery review. All gates remain pending until independently evidenced. No Store activation or Production publication is authorized by this document.
