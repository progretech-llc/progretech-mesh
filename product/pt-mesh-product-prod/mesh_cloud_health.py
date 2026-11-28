from __future__ import annotations

import os
from datetime import datetime, timezone

from flask import jsonify


def register_cloud_health_routes(app) -> None:
    """Stable unauthenticated platform probes for Cloud Run."""
    if getattr(app, "_pt_cloud_health_routes", False):
        return
    app._pt_cloud_health_routes = True

    @app.get("/api/platform/health")
    def platform_health():
        return jsonify(
            ok=True,
            service="progretech-mesh",
            deployment_tier=os.environ.get("MESH_DEPLOYMENT_TIER", "development"),
            auth_mode=os.environ.get("MESH_AUTH_MODE", "development"),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @app.get("/api/platform/startup")
    def platform_startup():
        return jsonify(
            ok=True,
            started=True,
            service="progretech-mesh",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
