from __future__ import annotations

import os
from typing import Any
from flask import jsonify, request, session

AUTH_MODE = "firebase-email-link"

def firebase_selected() -> bool:
    return os.environ.get("MESH_AUTH_MODE", "development").strip().lower() == AUTH_MODE

def firebase_client_config() -> dict[str, str]:
    return {
        "apiKey": os.environ.get("MESH_FIREBASE_API_KEY", "").strip(),
        "authDomain": os.environ.get("MESH_FIREBASE_AUTH_DOMAIN", "").strip(),
        "projectId": os.environ.get("MESH_FIREBASE_PROJECT_ID", "").strip(),
        "appId": os.environ.get("MESH_FIREBASE_APP_ID", "").strip(),
    }

def firebase_client_ready() -> bool:
    cfg = firebase_client_config()
    return all(cfg.get(k) for k in ("apiKey", "authDomain", "projectId", "appId"))

def firebase_admin_ready() -> bool:
    if os.environ.get("MESH_FIREBASE_AUTH_READY", "0") != "1":
        return False
    try:
        import firebase_admin  # noqa: F401
    except Exception:
        return False
    return bool(os.environ.get("MESH_FIREBASE_PROJECT_ID", "").strip())

def verify_firebase_id_token(id_token: str) -> dict[str, Any]:
    if not firebase_selected():
        raise PermissionError("firebase_auth_not_selected")
    if not firebase_client_ready():
        raise RuntimeError("firebase_client_not_configured")
    try:
        import firebase_admin
        from firebase_admin import auth
    except Exception as exc:
        raise RuntimeError("firebase_admin_unavailable") from exc
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            options={"projectId": os.environ.get("MESH_FIREBASE_PROJECT_ID", "").strip()}
        )
    decoded = auth.verify_id_token(id_token, check_revoked=True)
    email = str(decoded.get("email") or "").strip().lower()
    if not email:
        raise PermissionError("firebase_email_missing")
    if decoded.get("email_verified") is not True:
        raise PermissionError("firebase_email_not_verified")
    return decoded

def register_firebase_auth_routes(app) -> None:
    if getattr(app, "_pt_firebase_auth_routes", False):
        return
    app._pt_firebase_auth_routes = True

    @app.get("/api/auth/firebase/config")
    def firebase_config_route():
        if not firebase_selected():
            return jsonify(ok=False, error="firebase_auth_not_selected"), 404
        if not firebase_client_ready():
            return jsonify(ok=False, error="firebase_client_not_configured"), 503
        return jsonify(ok=True, config=firebase_client_config())

    @app.post("/api/auth/firebase/session")
    def firebase_session_route():
        if not firebase_selected():
            return jsonify(ok=False, error="firebase_auth_not_selected"), 404
        body = request.get_json(silent=True) or {}
        id_token = str(body.get("idToken") or "").strip()
        if not id_token:
            return jsonify(ok=False, error="firebase_id_token_required"), 400
        try:
            decoded = verify_firebase_id_token(id_token)
        except PermissionError:
            app.logger.exception("firebase_token_verification_failed: permission")
            return jsonify(ok=False, error="firebase_token_verification_failed"), 401
        except RuntimeError:
            app.logger.exception("firebase_token_verification_failed: runtime")
            return jsonify(ok=False, error="firebase_token_verification_failed"), 503
        except Exception:
            app.logger.exception("firebase_token_verification_failed")
            return jsonify(ok=False, error="firebase_token_verification_failed"), 401

        uid = str(decoded.get("uid") or decoded.get("sub") or "").strip()
        email = str(decoded.get("email") or "").strip().lower()
        if not uid or not email:
            return jsonify(ok=False, error="firebase_identity_incomplete"), 401

        session.clear()
        session["mesh_user"] = {
            "id": uid,
            "display_name": email.split("@", 1)[0],
            "email": email,
            "auth_source": AUTH_MODE,
        }
        return jsonify(ok=True, user={"id": uid, "email": email})
