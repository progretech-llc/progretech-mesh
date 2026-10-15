from __future__ import annotations

from dataclasses import dataclass, asdict
from functools import wraps
from typing import Any

from flask import jsonify, redirect, render_template, request, session, url_for


LIFECYCLE = (
    "DISCOVERED",
    "QUARANTINED",
    "INSPECTED",
    "CANDIDATE",
    "QUALIFYING",
    "QUALIFIED",
    "ACTIVE",
    "REJECTED",
    "SUPERSEDED",
    "ROLLED_BACK",
)


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    classification: str
    state: str
    source: str
    intended_use: str
    supported_agents: tuple[str, ...]
    authority_boundary: str
    network: str
    data_egress: str
    filesystem: str
    subprocess: str
    compute: str
    credentials: str
    owner: str = "ProgreTech"
    version: str = "UNPINNED"
    license: str = "TO_VERIFY"
    health: str = "not_checked"
    rollback: str = "not_applicable"
    notes: str = ""

    def public(self) -> dict[str, Any]:
        item = asdict(self)
        item["supported_agents"] = list(self.supported_agents)
        return item


CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        id="secret-broker",
        name="ProgreTech Secret Broker",
        classification="native integrated subsystem candidate",
        state="CANDIDATE",
        source="Freedesktop Secret Service / GNOME Keyring",
        intended_use="Local secret storage and retrieval boundary for future providers without plaintext credential files.",
        supported_agents=("Rend", "Mak", "Lyra"),
        authority_boundary="Stores secrets only. It grants no task, release, model, network or execution authority.",
        network="None",
        data_egress="None",
        filesystem="GNOME Keyring managed storage; no ProgreTech plaintext secret file",
        subprocess="Bounded secret-tool calls through local Secret Service",
        compute="Low",
        credentials="Secrets remain inside local Secret Service",
        version="0.1.0",
        license="ProgreTech internal wrapper; system provider packages",
        rollback="Deactivate adapter; stored provider entries remain under provider control until explicitly deleted.",
        notes="Public/runtime CLI never returns secret values.",
    ),
    Capability(
        id="imap-review",
        name="ProgreTech IMAP Review",
        classification="native integrated subsystem candidate",
        state="CANDIDATE",
        source="ProgreTech native",
        intended_use="Bounded review of configured mailbox content through an explicitly approved IMAP provider.",
        supported_agents=("Rend", "Mak", "Lyra"),
        authority_boundary="Read/review capability only. Registration or qualification grants no mailbox access, sending authority, task authority, or owner approval.",
        network="Explicit IMAP provider connection only after activation",
        data_egress="Mailbox-provider traffic only; no unrelated egress",
        filesystem="Bounded local review state and evidence only",
        subprocess="Future bounded local IMAP adapter through capability runtime",
        compute="Low",
        credentials="Provider credentials must remain behind the Secret Broker boundary",
        version="0.1.0",
        license="ProgreTech internal source",
        rollback="Deactivate capability, revoke provider authorization, and retain only approved evidence.",
        notes="Candidate registration does not imply qualification or activation.",
    ),
    Capability(
        id="webhooks",
        name="ProgreTech Webhook Inbox",
        classification="native integrated subsystem candidate",
        state="CANDIDATE",
        source="ProgreTech native",
        intended_use="Signed local event intake and durable event spool for future external connectors.",
        supported_agents=("Rend", "Mak", "Lyra"),
        authority_boundary="Accepts and records verified events only; cannot execute actions, grant authority, or bypass owner/STOP policy.",
        network="No public listener; local invocation only",
        data_egress="None",
        filesystem="~/.progretech-mesh/webhooks with 0700 root and 0600 secret/inbox",
        subprocess="Bounded local CLI through capability runtime",
        compute="Low",
        credentials="Locally generated HMAC secret only; no external credential required",
        version="0.1.0",
        license="ProgreTech internal source",
        rollback="Deactivate runtime and remove local webhook state after evidence export if needed.",
        notes="Public HTTP ingress remains a separate future adapter/gate.",
    ),
    Capability(
        id="workboard",
        name="ProgreTech Workboard",
        classification="native integrated subsystem candidate",
        state="CANDIDATE",
        source="ProgreTech native",
        intended_use="Shared bounded task-state ledger for Rend now and future Rend/Mak/Lyra handoffs.",
        supported_agents=("Rend", "Mak", "Lyra"),
        authority_boundary="Records task state only; cannot execute work, grant authority, alter routing or override STOP/owner policy.",
        network="None",
        data_egress="None",
        filesystem="~/.progretech-mesh/workboard.json after owner-approved activation",
        subprocess="Bounded local CLI through capability runtime",
        compute="Low",
        credentials="None",
        version="0.1.0",
        license="ProgreTech internal source",
        rollback="Remove runtime adapter and retain/export state evidence as needed.",
        notes="Qualification does not imply activation.",
    ),
    Capability(
        id="rend-host-control",
        name="Rend Host Control Provider",
        classification="integrated subsystem",
        state="CANDIDATE",
        source="~/Rend/control-center",
        intended_use="Expose qualified Rend Control Center functions through the Mesh agent boundary.",
        supported_agents=("Rend",),
        authority_boundary="Agent-local provider only. Mesh requests bounded actions; Rend remains execution authority.",
        network="Mesh adapter transport only",
        data_egress="No new egress",
        filesystem="Rend-local configuration and service state",
        subprocess="Existing bounded Control Center commands",
        compute="Host-local",
        credentials="No credential transfer to Mesh",
        license="ProgreTech internal source",
        rollback="Keep current Control Center source operational until parity is accepted.",
        notes="Convergence target; not a Cloud Run host-control implementation.",
    ),
    Capability(
        id="mattpocock-skills",
        name="mattpocock/skills",
        classification="curated skill",
        state="CANDIDATE",
        source="https://github.com/mattpocock/skills",
        intended_use="Curated engineering disciplines: diagnosis, TDD, review, specification/PRD, planning, domain modeling, handoff and skill authoring.",
        supported_agents=("Rend", "Mak"),
        authority_boundary="Imported workflow guidance cannot override ProgreTech governance, recovery, task or release authority.",
        network="Source acquisition only during quarantine/upgrade",
        data_egress="None required for qualified local use",
        filesystem="Quarantined skill files, then pinned capability library",
        subprocess="Per-skill; default deny until inspected",
        compute="Low",
        credentials="None by default",
        rollback="Retain known-good pinned skill version.",
    ),
    Capability(
        id="firecrawl-anydoc",
        name="Firecrawl anydoc",
        classification="qualified tool candidate",
        state="CANDIDATE",
        source="https://github.com/firecrawl/anydoc",
        intended_use="Preferred local document-to-Markdown normalization for supported office artifacts.",
        supported_agents=("Rend", "Mak", "Lyra"),
        authority_boundary="Normalization only. It does not authorize execution or memory admission.",
        network="Local conversion default",
        data_egress="Hosted OCR forbidden unless explicitly authorized",
        filesystem="Bounded artifact staging and normalized output",
        subprocess="Local converter runtime",
        compute="CPU; workload dependent",
        credentials="None for local mode",
        rollback="Remove adapter / restore prior pinned package.",
    ),
    Capability(
        id="archify",
        name="Archify",
        classification="curated skill / qualified tool candidate",
        state="CANDIDATE",
        source="canonical source to verify during qualification",
        intended_use="Architecture, workflow, sequence, data-flow and lifecycle visualization grounded in source/evidence.",
        supported_agents=("Rend", "Mak", "Lyra"),
        authority_boundary="Generated topology is an artifact, never execution authority.",
        network="Default deny after source acquisition unless qualification proves a need",
        data_egress="Default none",
        filesystem="Bounded project inputs and generated artifacts",
        subprocess="To classify during qualification",
        compute="Low/medium",
        credentials="None expected",
        rollback="Remove adapter and retain prior generated artifacts/evidence.",
    ),
    Capability(
        id="munder-difflin",
        name="Munder Difflin",
        classification="reference / subsystem candidate",
        state="INSPECTED",
        source="https://github.com/chaitanyagiri/munder-difflin",
        intended_use="Reference office/hive patterns: mailboxes, event/blackboard, supervisor routing, lifecycle, approvals and observable office activity.",
        supported_agents=("Rend", "Mak", "Lyra"),
        authority_boundary="Identity, Hindsight, task/recovery contracts and owner authority remain native ProgreTech.",
        network="Reference only unless a bounded subsystem is separately qualified",
        data_egress="None for reference use",
        filesystem="None for reference use",
        subprocess="None for reference use",
        compute="None for reference use",
        credentials="None",
        rollback="Not applicable while reference-only.",
    ),
    Capability(
        id="autonomous-os",
        name="Autonomous OS",
        classification="reference",
        state="DISCOVERED",
        source="canonical source to resolve",
        intended_use="Marketplace/catalog and staged skill-intake patterns for discovery, quarantine, inspection and promotion.",
        supported_agents=("Rend", "Mak", "Lyra"),
        authority_boundary="Discovery source only; installation grants no authority.",
        network="Reference/discovery only",
        data_egress="None required for adopted pattern",
        filesystem="None until a specific skill candidate is quarantined",
        subprocess="None until separately qualified",
        compute="None",
        credentials="None",
        rollback="Not applicable while reference-only.",
    ),
    Capability(
        id="odysseus",
        name="Odysseus",
        classification="reference / selective subsystem candidate",
        state="INSPECTED",
        source="canonical source recorded during PT-2026-044 review",
        intended_use="Model/provider UX, workspaces/tasks, MCP/tool/skill integration, research workflow and adapter ideas.",
        supported_agents=("Rend", "Mak", "Lyra"),
        authority_boundary="Must not replace Hindsight, model-routing authority, factory state, agent identity or Charter governance.",
        network="Reference only unless a bounded adapter is separately qualified",
        data_egress="None for reference use",
        filesystem="None for reference use",
        subprocess="None for reference use",
        compute="None for reference use",
        credentials="None",
        rollback="Not applicable while reference-only.",
    ),
    Capability(
        id="openmontage",
        name="OpenMontage",
        classification="integrated subsystem candidate",
        state="DISCOVERED",
        source="canonical source to verify when representative workload exists",
        intended_use="Specialist creative-production subsystem, primarily for Lyra.",
        supported_agents=("Lyra", "Rend", "Mak"),
        authority_boundary="Outside the core office control plane; provider/API and artifact policy remain explicit.",
        network="Expected provider/network use; must be classified before qualification",
        data_egress="Explicit decision required",
        filesystem="Generated-media artifacts only after qualification",
        subprocess="To classify",
        compute="Workload dependent",
        credentials="Provider-specific; secret broker required",
        rollback="Defer until representative creative workload.",
        notes="Deliberately deferred.",
    ),
)


def _require_mesh_session(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("mesh_user"):
            if request.path.startswith("/api/"):
                return jsonify(ok=False, error="authentication_required"), 401
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def _all_public() -> list[dict[str, Any]]:
    return [cap.public() for cap in CAPABILITIES]


def register_capability_routes(app) -> None:
    if getattr(app, "_pt_capabilities_registered", False):
        return
    app._pt_capabilities_registered = True

    @app.get("/capabilities")
    @_require_mesh_session
    def capabilities_page():
        return render_template(
            "capabilities.html",
            build_id=app.config.get("BUILD_ID", ""),
            version=app.config.get("MESH_VERSION", ""),
            environment=app.config.get("ENVIRONMENT", ""),
            user=session["mesh_user"],
            lifecycle=LIFECYCLE,
        )

    @app.get("/api/capabilities")
    @_require_mesh_session
    def capability_list():
        items = _all_public()
        state = str(request.args.get("state", "")).strip().upper()
        agent = str(request.args.get("agent", "")).strip().lower()
        classification = str(request.args.get("classification", "")).strip().lower()

        if state:
            items = [item for item in items if item["state"] == state]
        if agent:
            items = [
                item for item in items
                if any(agent == name.lower() for name in item["supported_agents"])
            ]
        if classification:
            items = [
                item for item in items
                if classification in item["classification"].lower()
            ]

        return jsonify(
            ok=True,
            lifecycle=list(LIFECYCLE),
            count=len(items),
            capabilities=items,
            authority="catalog_presence_is_not_authorization",
        )

    @app.get("/api/capabilities/summary")
    @_require_mesh_session
    def capability_summary():
        items = _all_public()
        states: dict[str, int] = {}
        for item in items:
            states[item["state"]] = states.get(item["state"], 0) + 1

        return jsonify(
            ok=True,
            total=len(items),
            states=states,
            active=sum(1 for item in items if item["state"] == "ACTIVE"),
            qualified=sum(1 for item in items if item["state"] in {"QUALIFIED", "ACTIVE"}),
            candidates=sum(1 for item in items if item["state"] in {"CANDIDATE", "QUALIFYING"}),
            health_checked=sum(1 for item in items if item["health"] != "not_checked"),
        )

    @app.get("/api/capabilities/<capability_id>")
    @_require_mesh_session
    def capability_detail(capability_id: str):
        for cap in CAPABILITIES:
            if cap.id == capability_id:
                return jsonify(ok=True, capability=cap.public(), lifecycle=list(LIFECYCLE))
        return jsonify(ok=False, error="capability_not_found"), 404
