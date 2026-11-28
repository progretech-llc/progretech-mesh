from __future__ import annotations

from functools import wraps

from flask import jsonify, request, session

from mesh_capability_runtime import all_descriptors, descriptor, invoke


def register_capability_runtime_routes(app) -> None:
    if getattr(app, "_pt_capability_runtime_routes", False):
        return
    app._pt_capability_runtime_routes = True

    def require_session(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("mesh_user"):
                return jsonify(ok=False, error="authentication_required"), 401
            return view(*args, **kwargs)
        return wrapped

    @app.get("/api/capability-runtime")
    @require_session
    def capability_runtime_list():
        return jsonify(ok=True, capabilities=all_descriptors())

    @app.get("/api/capability-runtime/<capability_id>")
    @require_session
    def capability_runtime_detail(capability_id: str):
        item = descriptor(capability_id)
        if not item:
            return jsonify(ok=False, error="capability_not_found"), 404
        return jsonify(ok=True, capability=item)

    @app.post("/api/capability-runtime/<capability_id>/invoke")
    @require_session
    def capability_runtime_invoke(capability_id: str):
        body = request.get_json(silent=True) or {}
        args = body.get("args") or []
        if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
            return jsonify(ok=False, error="invalid_args"), 400

        try:
            proc = invoke(capability_id, args)
        except KeyError:
            return jsonify(ok=False, error="capability_not_found"), 404
        except PermissionError as exc:
            return jsonify(ok=False, error=str(exc)), 409
        except FileNotFoundError as exc:
            return jsonify(ok=False, error=str(exc)), 503
        except Exception as exc:
            return jsonify(ok=False, error=f"runtime_error:{type(exc).__name__}"), 500

        return jsonify(
            ok=proc.returncode == 0,
            returncode=proc.returncode,
            stdout=proc.stdout[-20000:],
            stderr=proc.stderr[-20000:],
        ), (200 if proc.returncode == 0 else 422)
