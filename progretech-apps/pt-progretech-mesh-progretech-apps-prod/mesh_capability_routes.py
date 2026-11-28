from functools import wraps
from flask import jsonify, request, session
from mesh_capability_registry import get_record, list_records, record_qualification_check, transition

def register_capability_registry_routes(app):
    if getattr(app, "_pt_capability_registry_routes", False):
        return
    app._pt_capability_registry_routes = True

    def require_session(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("mesh_user"):
                return jsonify(ok=False, error="authentication_required"), 401
            return view(*args, **kwargs)
        return wrapped

    @app.get("/api/capability-registry")
    @require_session
    def capability_registry_list():
        items=list_records()
        return jsonify(ok=True,count=len(items),capabilities=items)

    @app.get("/api/capability-registry/<capability_id>")
    @require_session
    def capability_registry_detail(capability_id):
        record=get_record(capability_id)
        if not record:
            return jsonify(ok=False,error="capability_not_found"),404
        return jsonify(ok=True,capability=record)

    @app.post("/api/capability-registry/<capability_id>/transition")
    @require_session
    def capability_registry_transition(capability_id):
        body=request.get_json(silent=True) or {}
        try:
            record=transition(
                capability_id,
                body.get("target",""),
                reason=str(body.get("reason","")).strip(),
                owner_approved=bool(body.get("owner_approved",False)),
                evidence=body.get("evidence") if isinstance(body.get("evidence"),list) else None,
            )
        except KeyError:
            return jsonify(ok=False,error="capability_not_found"),404
        except ValueError as exc:
            return jsonify(ok=False,error=str(exc)),409
        return jsonify(ok=True,capability=record)

    @app.post("/api/capability-registry/<capability_id>/qualification-check")
    @require_session
    def capability_registry_qualification_check(capability_id):
        body=request.get_json(silent=True) or {}
        try:
            record=record_qualification_check(
                capability_id,
                str(body.get("check","")),
                bool(body.get("passed",False)),
                detail=str(body.get("detail","")).strip(),
                artifact=str(body.get("artifact")).strip() if body.get("artifact") else None,
            )
        except KeyError:
            return jsonify(ok=False,error="capability_not_found"),404
        except ValueError as exc:
            return jsonify(ok=False,error=str(exc)),400
        return jsonify(ok=True,capability=record)
