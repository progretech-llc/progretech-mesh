from __future__ import annotations

import re
import hashlib
import ipaddress
import json
import os
import secrets
import socket
import threading
import time
import base64
import binascii
import hmac
import tempfile
import mimetypes
from pathlib import Path
from datetime import datetime, timezone
from functools import wraps
from typing import Any

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    send_file,
    session,
    url_for,
)
from flask_sock import Sock
from werkzeug.middleware.proxy_fix import ProxyFix
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from mesh_progretech_auth import register_progretech_auth
from mesh_firebase_auth import register_firebase_auth_routes, firebase_client_ready, firebase_admin_ready
from mesh_owner_access import fleet_owner_id, owner_uid_bindings
from mesh_cloud_health import register_cloud_health_routes
from mesh_ownership import (
    OWNERSHIP_CLAIM_TTL_SECONDS,
    can_access as ownership_can_access,
    consume_claim as consume_ownership_claim,
    issue_claim as issue_ownership_claim,
    ownership_mode,
    visible as ownership_visible,
)

from mesh_capabilities import register_capability_routes
from mesh_capability_routes import register_capability_registry_routes
from mesh_capability_runtime_routes import register_capability_runtime_routes
from mesh_factory_control import factory_relay, register_factory_routes
from mesh_agent_management import register_management_routes
from mesh_control_center import control_relay, register_control_center_routes, register_gateway_agents
from gateway.identity.codeseal import CodeSealIdentityVerifier


BUILD_ID = "v1-rc2-private-lan-acceptance-20260913"

def _validated_http_origin(origin: str) -> str:
    value = str(origin or "").strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("invalid_mesh_public_origin")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("invalid_mesh_public_origin")
    return value


def _is_loopback_or_unspecified(hostname: str) -> bool:
    value = str(hostname or "").strip().strip("[]").lower()
    if value in {"localhost", "0.0.0.0", "::", ""}:
        return True
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


def detect_local_lan_ipv4() -> str | None:
    """Best-effort local IPv4 discovery without sending application traffic."""
    candidates: list[str] = []

    # Ask the OS which interface it would use for an external route. UDP connect
    # does not transmit application data and works even when the destination is not reached.
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        candidates.append(str(probe.getsockname()[0]))
    except OSError:
        pass
    finally:
        probe.close()

    try:
        _host, _aliases, addresses = socket.gethostbyname_ex(socket.gethostname())
        candidates.extend(addresses)
    except OSError:
        pass

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if address.version != 4 or address.is_loopback or address.is_unspecified:
            continue
        if address.is_private:
            return candidate

    for candidate in candidates:
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if address.version == 4 and not address.is_loopback and not address.is_unspecified:
            return candidate
    return None


def mesh_public_origin() -> str:
    configured = str(os.environ.get("MESH_PUBLIC_ORIGIN", "")).strip()
    environment = str(os.environ.get("MESH_ENVIRONMENT", "development")).strip().lower()

    if configured:
        origin = _validated_http_origin(configured)
        if environment == "production" and urlparse(origin).scheme != "https":
            raise ValueError("production_mesh_public_origin_requires_https")
        return origin

    if environment == "production":
        raise ValueError("production_mesh_public_origin_required")

    requested = _validated_http_origin(request.host_url)
    parsed = urlparse(requested)
    if not _is_loopback_or_unspecified(parsed.hostname or ""):
        return requested

    lan_ip = detect_local_lan_ipv4()
    if not lan_ip:
        raise ValueError("local_agent_reachable_origin_unavailable")

    port = parsed.port
    netloc = f"{lan_ip}:{port}" if port else lan_ip
    return f"{parsed.scheme}://{netloc}"


def websocket_origin_from_http(origin: str) -> str:
    parsed = urlparse(_validated_http_origin(origin))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}"


PAIR_TOKEN_TTL_SECONDS = 600
DEVICE_CREDENTIAL_TTL_SECONDS = int(os.environ.get("MESH_DEVICE_CREDENTIAL_TTL_SECONDS", str(60 * 60 * 24 * 365)))
REVOKED_DEVICE_IDS: set[str] = set()

MAX_WS_FILE_CHUNK = 256 * 1024
MAX_FILE_BYTES = int(os.environ.get("MESH_MAX_FILE_BYTES", str(20 * 1024 * 1024)))
MAX_SESSION_FILE_BYTES = int(os.environ.get("MESH_MAX_SESSION_FILE_BYTES", str(50 * 1024 * 1024)))
TRANSFER_TTL_SECONDS = int(os.environ.get("MESH_TRANSFER_TTL_SECONDS", "900"))
FILE_OFFER_TTL_SECONDS = int(os.environ.get("MESH_FILE_OFFER_TTL_SECONDS", "1800"))
MAX_ACTIVE_TRANSFERS_PER_AGENT = int(os.environ.get("MESH_MAX_ACTIVE_TRANSFERS_PER_AGENT", "3"))
TRANSFER_TEMP_ROOT = Path(os.environ.get("MESH_TRANSFER_TEMP_ROOT") or tempfile.gettempdir()) / "progretech-mesh-transfers"

SAFE_FILE_EXTENSIONS = {
    ".txt", ".md", ".json", ".yaml", ".yml", ".csv", ".log",
    ".html", ".htm", ".css", ".js", ".py", ".xml", ".pdf",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".zip", ".tar", ".gz"
}
SENSITIVE_FILE_EXTENSIONS = {".exe", ".msi", ".bat", ".cmd", ".ps1", ".sh", ".dll", ".so", ".dylib"}

OPENCLAW_PLUGIN_PACKAGE_VERSION = "0.10.1-continuity.1"
OPENCLAW_PLUGIN_PACKAGE_FILENAME = "progretech-mesh-openclaw-0.10.1-continuity.1.tgz"
UNIVERSAL_ENROLLMENT_PROTOCOL_FILENAME = "universal-agent-enrollment-v1.json"
AGENT_ADAPTER_CATALOG_FILENAME = "agent-adapter-catalog-v1.json"
OPENCLAW_SELF_BOOTSTRAP_PLAN_FILENAME = "openclaw-self-bootstrap-plan-v1.json"
OPENCLAW_SELF_BOOTSTRAP_FILENAME = "openclaw-self-bootstrap-v1.sh"

def openclaw_plugin_package_path() -> Path:
    override = os.environ.get("MESH_OPENCLAW_PLUGIN_PACKAGE_PATH")
    if override:
        return Path(override).expanduser().resolve()
    return (Path(__file__).resolve().parent / "distribution" / OPENCLAW_PLUGIN_PACKAGE_FILENAME).resolve()

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def distribution_file(name: str) -> Path:
    return (Path(__file__).resolve().parent / "distribution" / name).resolve()



# Live operational state is deliberately ephemeral and process-local.
DEV_AGENT_REGISTRY: dict[str, dict[str, Any]] = {}
PAIRING_TOKENS: dict[str, dict[str, Any]] = {}
GATEWAY_SOCKETS: dict[str, Any] = {}
CLIENT_SOCKETS: dict[str, list[Any]] = {}
EVENT_BUFFERS: dict[str, list[dict[str, Any]]] = {}
FILE_OFFERS: dict[str, dict[str, Any]] = {}
FILE_DOWNLOAD_EXPECTED: dict[str, dict[str, Any]] = {}
ACTIVE_UPLOAD_TRANSFERS: dict[str, dict[str, Any]] = {}
ACTION_REQUESTS: dict[str, dict[str, Any]] = {}
SESSION_FILE_TOTALS: dict[str, int] = {}
ACTIVATION_CODES: dict[str, dict[str, Any]] = {}
IDE_PENDING: dict[str, dict[str, Any]] = {}
IDE_TOKEN_TTL_SECONDS = int(os.environ.get("MESH_IDE_TOKEN_TTL_SECONDS", "604800"))
IDE_REQUEST_TIMEOUT_SECONDS = int(os.environ.get("MESH_IDE_REQUEST_TIMEOUT_SECONDS", "150"))
LIVE_LOCK = threading.RLock()

# PT044_IDENTITY_POP_NONCE_V1
IDENTITY_CHALLENGE_TTL_SECONDS = int(os.environ.get("MESH_IDENTITY_CHALLENGE_TTL_SECONDS", "60"))
IDENTITY_CHALLENGES: dict[str, dict[str, Any]] = {}


# Direct-transport signaling state is ephemeral and exists only to introduce peers.
DIRECT_SIGNAL_SESSIONS: dict[str, dict[str, Any]] = {}
DIRECT_SIGNAL_TTL_SECONDS = int(os.environ.get("MESH_DIRECT_SIGNAL_TTL_SECONDS", "120"))



def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def unix_now() -> int:
    return int(time.time())


def verify_runtime_agent_identity(payload: dict[str, Any], name: str, public_key: str, codeseal_key: str = "") -> dict[str, Any]:
    identity_mode = os.environ.get("MESH_AGENT_IDENTITY_MODE", "development").strip().lower()
    if identity_mode == "codeseal":
        result = CodeSealIdentityVerifier().verify({
            "agent_id": str(payload.get("agent_id") or "").strip(),
            "agent_name": name,
            "public_key": public_key,
            "codeseal_evidence": payload.get("codeseal_evidence"),
        })
        return {
            "state": "verified" if result.ok else "invalid",
            "valid": bool(result.ok),
            "reason": "codeseal_registry_verified" if result.ok else (result.error or "codeseal_verification_failed"),
            "provider": result.provider,
            "metadata": result.metadata,
        }
    return verify_codeseal(name, public_key, codeseal_key)


def fingerprint_for(agent_name: str, public_key: str, codeseal_key: str) -> str:
    payload = f"{agent_name.strip()}|{public_key.strip()}|{codeseal_key.strip()}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest().upper()
    return ":".join(digest[i:i + 4] for i in range(0, 32, 4))


def verify_codeseal(agent_name: str, public_key: str, codeseal_key: str) -> dict[str, Any]:
    if not agent_name.strip() or not public_key.strip():
        return {"state": "invalid", "valid": False, "reason": "missing_identity_material"}

    normalized = codeseal_key.strip().upper()
    if normalized.startswith("CS-REVOKED"):
        return {"state": "revoked", "valid": False, "reason": "development_revocation_marker"}
    if normalized.startswith("CS-"):
        return {"state": "verified", "valid": True, "reason": "development_codeseal_adapter"}
    return {"state": "unsigned", "valid": False, "reason": "no_recognized_codeseal_signature"}


def seed_development_registry() -> None:
    if DEV_AGENT_REGISTRY:
        return

    examples = [
        {
            "id": "rend",
            "owner_id": "local-edwin",
            "name": "Rend",
            "role": "Primary workstation agent",
            "public_key": "mesh-dev-rend-public-key",
            "codeseal_key": "CS-REND-DEV-001",
            "state": "offline",
            "task": "Awaiting gateway",
            "phase": "Connect the local gateway to establish live transport",
            "progress": 0,
            "model": "Unknown",
            "runtime": "—",
        },
        {
            "id": "lyra",
            "owner_id": "local-edwin",
            "name": "Lyra",
            "role": "Content & coordination agent",
            "public_key": "mesh-dev-lyra-public-key",
            "codeseal_key": "CS-LYRA-DEV-001",
            "state": "offline",
            "task": "Awaiting gateway",
            "phase": "Not connected",
            "progress": 0,
            "model": "Unknown",
            "runtime": "—",
        },
        {
            "id": "mak",
            "owner_id": "local-edwin",
            "name": "Mak",
            "role": "Development agent",
            "public_key": "mesh-dev-mak-public-key",
            "codeseal_key": "CS-MAK-DEV-001",
            "state": "offline",
            "task": "Awaiting gateway",
            "phase": "Not connected",
            "progress": 0,
            "model": "Unknown",
            "runtime": "—",
        },
    ]

    for item in examples:
        verification = verify_codeseal(item["name"], item["public_key"], item["codeseal_key"])
        DEV_AGENT_REGISTRY[item["id"]] = {
            **item,
            "fingerprint": fingerprint_for(item["name"], item["public_key"], item["codeseal_key"]),
            "trust_state": verification["state"],
            "trust_valid": verification["valid"],
            "trust_reason": verification["reason"],
            "enrolled_at": utcnow(),
            "transport": "not-connected",
            "last_heartbeat": None,
            "telemetry": {},
        }


def _identity_signing_payload(agent_id: str, device_id: str, challenge_id: str,
                              nonce: str, expires_at: int) -> str:
    return (
        "progretech-mesh-identity-v1"
        f"|{agent_id}|{device_id}|{challenge_id}|{nonce}|{expires_at}"
    )


def _expire_identity_challenges() -> None:
    now = unix_now()
    with LIVE_LOCK:
        expired = [
            cid for cid, item in IDENTITY_CHALLENGES.items()
            if item.get("expires_at", 0) < now or item.get("used")
        ]
        for cid in expired:
            IDENTITY_CHALLENGES.pop(cid, None)


def issue_identity_challenge(agent_id: str, device_id: str) -> dict[str, Any]:
    _expire_identity_challenges()
    challenge_id = secrets.token_urlsafe(18)
    nonce = secrets.token_urlsafe(32)
    expires_at = unix_now() + IDENTITY_CHALLENGE_TTL_SECONDS
    item = {
        "challenge_id": challenge_id,
        "agent_id": agent_id,
        "device_id": device_id,
        "nonce": nonce,
        "expires_at": expires_at,
        "used": False,
    }
    item["signing_payload"] = _identity_signing_payload(
        agent_id, device_id, challenge_id, nonce, expires_at
    )
    with LIVE_LOCK:
        IDENTITY_CHALLENGES[challenge_id] = item
    return dict(item)


def consume_identity_challenge(agent_id: str, device_id: str, challenge_id: str) -> tuple[bool, str, dict[str, Any] | None]:
    now = unix_now()
    with LIVE_LOCK:
        item = IDENTITY_CHALLENGES.get(challenge_id)
        if not item:
            return False, "identity_challenge_not_found", None
        if item.get("used"):
            return False, "identity_challenge_replayed", None
        if item.get("expires_at", 0) < now:
            IDENTITY_CHALLENGES.pop(challenge_id, None)
            return False, "identity_challenge_expired", None
        if item.get("agent_id") != agent_id:
            return False, "identity_challenge_agent_mismatch", None
        if item.get("device_id") != device_id:
            return False, "identity_challenge_device_mismatch", None
        item["used"] = True
        consumed = dict(item)
        IDENTITY_CHALLENGES.pop(challenge_id, None)
        return True, "ok", consumed


def verify_identity_proof(public_key_pem: str, signing_payload: str, signature_b64: str) -> tuple[bool, str]:
    try:
        key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        if not isinstance(key, Ed25519PublicKey):
            return False, "identity_public_key_not_ed25519"
        signature = base64.b64decode(signature_b64, validate=True)
        key.verify(signature, signing_payload.encode("utf-8"))
        return True, "ok"
    except InvalidSignature:
        return False, "identity_signature_invalid"
    except (ValueError, TypeError, binascii.Error):
        return False, "identity_signature_malformed"


def append_event(agent_id: str, event: dict[str, Any]) -> None:
    event = {
        "timestamp": event.get("timestamp") or utcnow(),
        "type": event.get("type", "event"),
        "message": event.get("message", ""),
        "payload": event.get("payload", {}),
    }
    with LIVE_LOCK:
        buffer = EVENT_BUFFERS.setdefault(agent_id, [])
        buffer.append(event)
        del buffer[:-100]


def broadcast_to_clients(agent_id: str, message: dict[str, Any]) -> None:
    payload = json.dumps(message)
    dead: list[Any] = []
    with LIVE_LOCK:
        clients = list(CLIENT_SOCKETS.get(agent_id, []))

    for ws in clients:
        try:
            ws.send(payload)
        except (OSError, RuntimeError):
            dead.append(ws)

    if dead:
        with LIVE_LOCK:
            current = CLIENT_SOCKETS.get(agent_id, [])
            CLIENT_SOCKETS[agent_id] = [ws for ws in current if ws not in dead]


def update_from_gateway(agent_id: str, message: dict[str, Any]) -> None:
    if message.get("type") == "factory_control_response":
        factory_relay.resolve(agent_id, message)
        return

    record = DEV_AGENT_REGISTRY.get(agent_id)
    if not record:
        return

    msg_type = message.get("type", "event")
    if msg_type == "control_center_response":
        control_relay.resolve(agent_id, message)
        return
    if msg_type == "control_center_roster":
        payload = message.get("payload")
        if not register_gateway_agents(agent_id, payload, DEV_AGENT_REGISTRY):
            return
        record['gateway_enrollment_restore_version'] = 1 if payload.get('enrollment_restore_version') == 1 else 0
        receipts = payload.get('enrollment_receipts', [])
        if isinstance(receipts, list) and len(receipts) <= 256:
            from mesh_gateway_receipts import restore_receipt
            from mesh_gateway_agents import public_bytes
            candidates = {item['id'] for item in record.get('identified_agents', [])}
            restored_count = rejected_count = 0
            for receipt in receipts:
                try:
                    independently_enrolled = {key: value for key, value in DEV_AGENT_REGISTRY.items()
                                              if not value.get('gateway_linked')}
                    restored = restore_receipt(receipt, agent_id, record, device_credential_secret(),
                                               candidates, verify_runtime_agent_identity, independently_enrolled)
                    with LIVE_LOCK:
                        if (DEV_AGENT_REGISTRY.get(agent_id) is not record or record.get('owner_id') != restored['owner_id']
                                or not any(item['id'] == restored['id'] for item in record.get('identified_agents', []))):
                            continue
                        previous = DEV_AGENT_REGISTRY.get(restored['id'])
                        if previous and not (previous.get('gateway_linked')
                                             and previous.get('control_center_gateway') == agent_id
                                             and previous.get('owner_id') == record['owner_id']):
                            continue
                        key = public_bytes(restored['public_key'])
                        if any(other.get('public_key') and public_bytes(other['public_key']) == key
                               for other in DEV_AGENT_REGISTRY.values()):
                            continue
                        DEV_AGENT_REGISTRY[restored['id']] = restored
                        restored_count += 1
                except ValueError as exc:
                    if str(exc) != 'gateway_enrollment_already_present':
                        rejected_count += 1
                    continue
            record['enrollment_recovery'] = {'cached': len(receipts), 'restored': restored_count, 'rejected': rejected_count}
            if restored_count or rejected_count:
                app.logger.warning('Gateway enrollment recovery: restored=%s rejected=%s cached=%s', restored_count, rejected_count, len(receipts))
            register_gateway_agents(agent_id, payload, DEV_AGENT_REGISTRY)
        return
    now = utcnow()

    if msg_type == "heartbeat":
        payload = message.get("payload", {})
        # Connectivity heartbeats must not erase role-specific observed work.
        activity = record.get('activity') or {}
        heartbeat_state = payload.get("state", record.get("state", "online"))
        if activity.get('source'):
            heartbeat_state = record.get('state', 'unknown')
        record.update(
            state=heartbeat_state,
            task=payload.get("task", record.get("task", "Connected")),
            phase=payload.get("phase", record.get("phase", "Live gateway connected")),
            progress=max(0, min(100, int(payload.get("progress", record.get("progress", 0)) or 0))),
            model=payload.get("model", record.get("model", "Unknown")),
            runtime=payload.get("runtime", record.get("runtime", "—")),
            transport="connected",
            last_heartbeat=now,
            telemetry=payload.get("telemetry", {}),
            capability_provider=payload.get("capability_provider"),
        )
        append_event(agent_id, {
            "type": "heartbeat",
            "message": payload.get("message", "Heartbeat received"),
            "payload": payload,
        })
    elif msg_type == "event":
        append_event(agent_id, message)
    elif msg_type == "terminal":
        append_event(agent_id, message)
    elif msg_type == "agent_activity":
        payload = message.get("payload", {})
        channel = str(payload.get("channel", "system"))
        direction = payload.get("direction")
        state = str(payload.get("state", "active"))
        summary = message.get("message") or payload.get("summary") or "Agent activity"

        append_event(agent_id, {
            "type": "agent_activity",
            "message": summary,
            "payload": {
                **payload,
                "channel": channel,
                "direction": direction,
                "state": state,
                "read_only": True,
            },
        })
        broadcast_to_clients(agent_id, {
            "type": "agent_activity",
            "agent_id": agent_id,
            "timestamp": message.get("timestamp") or utcnow(),
            "message": summary,
            "payload": {
                **payload,
                "channel": channel,
                "direction": direction,
                "state": state,
                "read_only": True,
            },
        })
    elif msg_type == "file_offer_start":
        cleanup_expired_transfer_state()
        payload = message.get("payload", {})
        offer_id = str(payload.get("offer_id") or secrets.token_urlsafe(10))
        filename = sanitize_filename(payload.get("filename", "agent-output"))
        size = int(payload.get("size", 0) or 0)
        classification = classify_file(filename)

        if active_reverse_transfer_count(agent_id) >= MAX_ACTIVE_TRANSFERS_PER_AGENT:
            append_event(agent_id, {
                "type": "file",
                "message": f"Rejected file offer: {filename}",
                "payload": {"severity": "error", "reason": "too_many_active_transfers"},
            })
        elif size <= 0 or size > MAX_FILE_BYTES:
            append_event(agent_id, {
                "type": "file",
                "message": f"Rejected file offer: {filename}",
                "payload": {"severity": "error", "reason": "invalid_size"},
            })
        elif not classification["allowed"] and not classification["sensitive"]:
            append_event(agent_id, {
                "type": "file",
                "message": f"Rejected file offer: {filename}",
                "payload": {"severity": "error", "reason": "file_type_not_allowed"},
            })
        else:
            temp_path = transfer_temp_dir() / f"offer-{offer_id}.part"
            temp_path.write_bytes(b"")
            FILE_DOWNLOAD_EXPECTED[offer_id] = {
                "agent_id": agent_id,
                "filename": filename,
                "size": size,
                "mime": payload.get("mime", "application/octet-stream"),
                "sha256": payload.get("sha256"),
                "classification": classification,
                "created_at": utcnow(),
                "created_epoch": time.time(),
                "temp_path": str(temp_path),
                "received": 0,
                "next_index": 0,
                "hasher": hashlib.sha256(),
                "first_bytes": bytearray(),
            }
            broadcast_to_clients(agent_id, {
                "type": "file_offer_start",
                "agent_id": agent_id,
                "file": {
                    "id": offer_id,
                    "filename": filename,
                    "size": size,
                    "mime": payload.get("mime", "application/octet-stream"),
                    "classification": classification,
                },
            })

    elif msg_type == "file_offer_chunk":
        payload = message.get("payload", {})
        offer_id = str(payload.get("offer_id", ""))
        encoded = str(payload.get("content_base64", ""))
        index = int(payload.get("index", 0) or 0)
        meta = FILE_DOWNLOAD_EXPECTED.get(offer_id)

        if meta is not None:
            try:
                chunk = base64.b64decode(encoded, validate=True)
                if index != meta["next_index"]:
                    raise ValueError("chunk_sequence_mismatch")
                if len(chunk) > MAX_WS_FILE_CHUNK:
                    raise ValueError("chunk_too_large")
                if meta["received"] + len(chunk) > meta["size"]:
                    raise ValueError("transfer_overflow")

                if len(meta["first_bytes"]) < 64:
                    meta["first_bytes"].extend(chunk[: 64 - len(meta["first_bytes"])])

                with Path(meta["temp_path"]).open("ab") as handle:
                    handle.write(chunk)

                meta["hasher"].update(chunk)
                meta["received"] += len(chunk)
                meta["next_index"] += 1

                broadcast_to_clients(agent_id, {
                    "type": "file_offer_progress",
                    "agent_id": agent_id,
                    "file": {
                        "id": offer_id,
                        "filename": meta["filename"],
                        "received": meta["received"],
                        "size": meta["size"],
                    },
                })
            except (OSError, ValueError, TypeError, KeyError, binascii.Error) as exc:
                try:
                    Path(meta["temp_path"]).unlink(missing_ok=True)
                except OSError:
                    pass
                FILE_DOWNLOAD_EXPECTED.pop(offer_id, None)
                append_event(agent_id, {
                    "type": "file",
                    "message": f"Agent file transfer failed: {meta['filename']}",
                    "payload": {"severity": "error", "reason": str(exc)},
                })

    elif msg_type == "file_offer_end":
        payload = message.get("payload", {})
        offer_id = str(payload.get("offer_id", ""))
        meta = FILE_DOWNLOAD_EXPECTED.get(offer_id)
        if meta is not None:
            digest = meta["hasher"].hexdigest()
            mime_ok, mime_details = validate_mime_claim(
                meta["filename"], meta["mime"], bytes(meta["first_bytes"])
            )
            verified = (
                meta["received"] == meta["size"]
                and (not meta.get("sha256")
                     or digest.lower() == str(meta["sha256"]).lower())
                and mime_ok
            )

            if verified:
                record = {
                    "id": offer_id,
                    "agent_id": meta["agent_id"],
                    "filename": meta["filename"],
                    "size": meta["size"],
                    "mime": meta["mime"],
                    "sha256": digest,
                    "classification": meta["classification"],
                    "created_at": meta["created_at"],
                    "created_epoch": meta["created_epoch"],
                    "temp_path": meta["temp_path"],
                    "status": "ready",
                    "mime_validation": mime_details,
                }
                FILE_OFFERS[offer_id] = record
                FILE_DOWNLOAD_EXPECTED.pop(offer_id, None)

                append_event(agent_id, {
                    "type": "file_offer",
                    "message": f"Agent offered file: {meta['filename']}",
                    "payload": {
                        "offer_id": offer_id,
                        "filename": meta["filename"],
                        "size": meta["size"],
                        "sha256": digest,
                        "severity": "info",
                    },
                })
                broadcast_to_clients(agent_id, {
                    "type": "file_offer_ready",
                    "agent_id": agent_id,
                    "file": {
                        key: value for key, value in record.items()
                        if key not in {"temp_path", "created_epoch"}
                    },
                })
            else:
                try:
                    Path(meta["temp_path"]).unlink(missing_ok=True)
                except OSError:
                    pass
                FILE_DOWNLOAD_EXPECTED.pop(offer_id, None)
                append_event(agent_id, {
                    "type": "file",
                    "message": f"Agent file verification failed: {meta['filename']}",
                    "payload": {
                        "severity": "error",
                        "reason": "verification_failed",
                        "mime_validation": mime_details,
                    },
                })

    elif msg_type == "file_offer_cancel":
        payload = message.get("payload", {})
        offer_id = str(payload.get("offer_id", ""))
        meta = FILE_DOWNLOAD_EXPECTED.pop(offer_id, None)
        if meta:
            try:
                Path(meta["temp_path"]).unlink(missing_ok=True)
            except OSError:
                pass
            append_event(agent_id, {
                "type": "file",
                "message": f"Agent cancelled file transfer: {meta['filename']}",
                "payload": {"severity": "warn"},
            })
    elif msg_type == "ide_chat_response":
        resolve_ide_pending(agent_id, message)
        append_event(agent_id, {
            "type": "ide_relay",
            "message": "IDE relay response completed",
            "payload": {
                "severity": "info",
                "request_id": message.get("request_id"),
                "ok": bool((message.get("payload") or {}).get("ok", True)),
            },
        })
        return
    elif msg_type in {"mesh_direct_signal", "mesh_local_route"}:
        # Ephemeral connection metadata only. Never persist SDP/ICE or local access credentials.
        broadcast_to_clients(agent_id, {"type":"gateway_message","agent_id":agent_id,"message":message,"agent":public_agent(record)})
        return
    elif msg_type == "command_ack":
        payload = message.get("payload", {})
        action_id = payload.get("action_id")
        action = ACTION_REQUESTS.get(str(action_id)) if action_id else None
        if action and action.get("status") in {"approved", "dispatched", "approved_waiting_for_gateway"}:
            action["status"] = "acknowledged"
            action["acknowledged_at"] = utcnow()
        append_event(agent_id, {
            "type": "delivery",
            "message": message.get("message", "Mesh command acknowledged by agent adapter"),
            "payload": {**payload, "severity": "info"},
        })
        broadcast_to_clients(agent_id, {
            "type": "command_ack",
            "agent_id": agent_id,
            "message": message,
            "action": action,
        })
    elif msg_type == "action_result":
        payload = message.get("payload", {})
        action_id = payload.get("action_id")
        action = ACTION_REQUESTS.get(str(action_id))
        if action:
            action["status"] = payload.get("status", "completed")
            action["completed_at"] = utcnow()
        append_event(agent_id, message)
        broadcast_to_clients(agent_id, {
            "type": "action_result",
            "agent_id": agent_id,
            "message": message,
            "action": action,
        })
    else:
        append_event(agent_id, {
            "type": msg_type,
            "message": message.get("message", f"{msg_type} received"),
            "payload": message.get("payload", {}),
        })

    broadcast_to_clients(agent_id, {
        "type": "gateway_message",
        "agent_id": agent_id,
        "message": message,
        "agent": public_agent(record),
    })


def public_agent(record: dict[str, Any]) -> dict[str, Any]:
    public = {
        key: value
        for key, value in record.items()
        if key not in {"codeseal_key", "owner_id"}
    }
    public["gateway_agent"] = not record.get("control_center_gateway")
    public["control_center_available"] = bool(record.get("owner_id")) and record.get("trust_state") == "verified"
    if record.get("control_center_gateway"):
        host = DEV_AGENT_REGISTRY.get(record["control_center_gateway"], {})
        linked = record["control_center_gateway"] in GATEWAY_SOCKETS and host.get("trust_state") == "verified"
        if record.get("gateway_enrollment"):
            linked = linked and any(item['id'] == record['id'] for item in host.get('identified_agents', []))
            public["task"] = "Gateway live" if linked else "Gateway offline"
            activity = {"working": "Working", "idle": "Idle", "paused": "Paused", "blocked": "Needs attention"}.get(record.get("state"), "Activity unknown")
            public["phase"] = f"Connected through {host.get('name') or record['control_center_gateway']} · {activity}" if linked else "Waiting for the host gateway to reconnect"
        public["transport"] = "connected" if linked else "not-connected"
        public["control_center_available"] = public["control_center_available"] and host.get("trust_state") == "verified"
        if record.get("gateway_enrollment"):
            public["control_center_available"] = public["control_center_available"] and linked
    with LIVE_LOCK:
        latest = next(iter(reversed(EVENT_BUFFERS.get(record['id'], []))), None)
    if latest:
        payload = latest.get('payload') or {}
        public['last_event'] = {'type': latest.get('type'), 'timestamp': latest.get('timestamp'),
                                'payload': {k: payload[k] for k in ('direction', 'severity') if isinstance(payload.get(k), str)}}
    host_id = record.get('control_center_gateway')
    host = DEV_AGENT_REGISTRY.get(host_id, {}) if host_id else {}
    public['identity_alias'] = bool(host_id and host.get('runtime_id') and record['id'] == host_id+'--'+host['runtime_id'])
    public["owner_bound"] = bool(str(record.get("owner_id") or "").strip())
    public["ownership_state"] = "owned" if public["owner_bound"] else "legacy-unowned"
    return public



def send_gateway_message(agent_id: str, message: dict[str, Any]) -> tuple[bool, str | None]:
    with LIVE_LOCK:
        gateway = GATEWAY_SOCKETS.get(agent_id)

    if gateway is None:
        return False, "gateway_not_connected"

    try:
        gateway.send(json.dumps(message))
        return True, None
    except (OSError, RuntimeError):
        return False, "gateway_send_failed"




def file_extension(filename: str) -> str:
    name = str(filename or "").strip().lower()
    dot = name.rfind(".")
    return name[dot:] if dot >= 0 else ""


def sanitize_filename(filename: str) -> str:
    name = os.path.basename(str(filename or "").strip())
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "._- ()")
    safe = safe.strip(" .")
    return safe[:180] or "mesh-file"


def classify_file(filename: str) -> dict[str, Any]:
    ext = file_extension(filename)
    return {
        "extension": ext,
        "sensitive": ext in SENSITIVE_FILE_EXTENSIONS,
        "allowed": ext in SAFE_FILE_EXTENSIONS or ext == "",
    }


def session_file_key() -> str:
    user = session.get("mesh_user") or {}
    return str(user.get("id") or "anonymous")


def session_file_total() -> int:
    return SESSION_FILE_TOTALS.get(session_file_key(), 0)


def add_session_file_bytes(size: int) -> None:
    key = session_file_key()
    SESSION_FILE_TOTALS[key] = SESSION_FILE_TOTALS.get(key, 0) + size


def transfer_temp_dir() -> Path:
    TRANSFER_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    return TRANSFER_TEMP_ROOT


def detect_content_signature(first_bytes: bytes) -> str | None:
    head = first_bytes[:32]
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head.startswith(b"PK\x03\x04"):
        return "application/zip"
    if head.startswith(b"\x1f\x8b"):
        return "application/gzip"
    return None


def validate_mime_claim(filename: str, claimed_mime: str, first_bytes: bytes) -> tuple[bool, dict[str, str | None]]:
    extension_guess = mimetypes.guess_type(filename)[0]
    signature = detect_content_signature(first_bytes)
    claimed = (claimed_mime or "application/octet-stream").split(";", 1)[0].strip().lower()
    reliable = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".zip": "application/zip",
        ".gz": "application/gzip",
    }
    expected = reliable.get(file_extension(filename))
    ok = True
    if expected and signature != expected:
        ok = False
    if signature and claimed not in ("application/octet-stream", signature):
        aliases = {
            "application/x-zip-compressed": "application/zip",
            "application/x-gzip": "application/gzip",
        }
        ok = aliases.get(claimed, claimed) == signature
    return ok, {
        "claimed": claimed,
        "extension_guess": extension_guess,
        "signature": signature,
        "expected": expected,
    }


def _expire_temp_entries(entries: dict[str, dict], ttl_seconds: int, now: float) -> None:
    for entry_id, meta in list(entries.items()):
        created = float(meta.get("created_epoch") or 0)
        if not created or now - created <= ttl_seconds:
            continue
        try:
            Path(meta["temp_path"]).unlink(missing_ok=True)
        except OSError:
            pass
        entries.pop(entry_id, None)


def cleanup_expired_transfer_state() -> None:
    now = time.time()
    _expire_temp_entries(FILE_DOWNLOAD_EXPECTED, TRANSFER_TTL_SECONDS, now)
    _expire_temp_entries(FILE_OFFERS, FILE_OFFER_TTL_SECONDS, now)


def active_reverse_transfer_count(agent_id: str) -> int:
    return sum(
        1 for meta in FILE_DOWNLOAD_EXPECTED.values()
        if meta.get("agent_id") == agent_id
    )


def decode_data_url_payload(value: str) -> bytes:
    if not value or "," not in value:
        raise ValueError("invalid_data_url")
    header, encoded = value.split(",", 1)
    if ";base64" not in header:
        raise ValueError("base64_required")
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid_base64") from exc


def issue_action_request(agent_id: str, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    action_id = secrets.token_urlsafe(10)
    record = {
        "id": action_id,
        "agent_id": agent_id,
        "action_type": action_type,
        "payload": payload,
        "status": "pending",
        "created_at": utcnow(),
        "approved_at": None,
        "completed_at": None,
    }
    ACTION_REQUESTS[action_id] = record
    append_event(agent_id, {
        "type": "approval",
        "message": f"Approval requested: {action_type}",
        "payload": {"action_id": action_id, **payload},
    })
    broadcast_to_clients(agent_id, {
        "type": "approval_request",
        "agent_id": agent_id,
        "action": record,
    })
    return record




def production_auth_mode() -> str:
    return os.environ.get("MESH_AUTH_MODE", "development").strip().lower()



def app_secret_key() -> str:
    """Return the Flask/session signing secret without depending on an app context."""
    return os.environ.get("SECRET_KEY", "dev-only-change-me")


def device_credential_secret() -> bytes:
    value = os.environ.get("MESH_DEVICE_CREDENTIAL_SECRET") or os.environ.get(
        "MESH_ACTIVATION_SECRET"
    ) or app_secret_key()
    return str(value).encode("utf-8")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def ide_token_secret() -> bytes:
    value = os.environ.get("MESH_IDE_TOKEN_SECRET") or os.environ.get(
        "MESH_DEVICE_CREDENTIAL_SECRET"
    ) or app_secret_key()
    return str(value).encode("utf-8")


def issue_ide_token(owner_id: str, agent_id: str) -> dict[str, Any]:
    issued_at = unix_now()
    expires_at = issued_at + IDE_TOKEN_TTL_SECONDS
    payload = {
        "v": 1,
        "owner_id": str(owner_id or "").strip(),
        "agent_id": str(agent_id or "").strip(),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "scope": "mesh-ide",
        "jti": secrets.token_urlsafe(16),
    }
    encoded = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        ide_token_secret(), encoded.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return {
        "token": f"PTMIDE1.{encoded}.{signature}",
        "issued_at": issued_at,
        "expires_at": expires_at,
        "agent_id": payload["agent_id"],
    }


def validate_ide_token(token: str) -> tuple[bool, str, dict[str, Any] | None]:
    value = str(token or "").strip()
    parts = value.split(".")
    if len(parts) != 3 or parts[0] != "PTMIDE1":
        return False, "ide_token_invalid", None
    encoded, supplied = parts[1], parts[2]
    expected = hmac.new(
        ide_token_secret(), encoded.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        return False, "ide_token_signature_invalid", None
    try:
        payload = json.loads(_b64url_decode(encoded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "ide_token_payload_invalid", None
    if payload.get("scope") != "mesh-ide":
        return False, "ide_token_scope_invalid", None
    if int(payload.get("expires_at") or 0) < unix_now():
        return False, "ide_token_expired", None
    agent_id = str(payload.get("agent_id") or "").strip()
    owner_id = str(payload.get("owner_id") or "").strip()
    if not agent_id or not owner_id:
        return False, "ide_token_binding_invalid", None
    record = DEV_AGENT_REGISTRY.get(agent_id)
    if not record:
        return False, "agent_not_found", None
    if str(record.get("owner_id") or "").strip() != owner_id:
        return False, "ide_owner_mismatch", None
    if record.get("trust_state") != "verified":
        return False, "verified_agent_required", None
    return True, "ok", payload


def ide_bearer_token() -> str:
    header = str(request.headers.get("Authorization") or "").strip()
    if not header.lower().startswith("bearer "):
        return ""
    return header[7:].strip()


def ide_models(agent_id: str) -> list[str]:
    models = [agent_id, f"{agent_id}-code"]
    if agent_id == "rend":
        models.extend([
            "rend-research",
            "lyra", "mak", "progre", "imagen", "codex", "odexi",
        ])
    return models


def resolve_ide_pending(agent_id: str, message: dict[str, Any]) -> bool:
    request_id = str(message.get("request_id") or (message.get("payload") or {}).get("request_id") or "").strip()
    if not request_id:
        return False
    with LIVE_LOCK:
        pending = IDE_PENDING.get(request_id)
        if not pending or pending.get("agent_id") != agent_id:
            return False
        pending["response"] = message
        pending["completed_at"] = utcnow()
        event = pending.get("event")
    if event:
        event.set()
    return True


def dispatch_ide_chat(agent_id: str, body: dict[str, Any]) -> tuple[bool, str, dict[str, Any] | None]:
    request_id = secrets.token_urlsafe(18)
    event = threading.Event()
    pending = {
        "request_id": request_id,
        "agent_id": agent_id,
        "event": event,
        "response": None,
        "created_at": utcnow(),
        "created_epoch": time.time(),
    }
    with LIVE_LOCK:
        IDE_PENDING[request_id] = pending

    ok, error = send_gateway_message(agent_id, {
        "type": "ide_chat_request",
        "request_id": request_id,
        "timestamp": utcnow(),
        "payload": {
            "request_id": request_id,
            "openai": body,
        },
    })
    if not ok:
        with LIVE_LOCK:
            IDE_PENDING.pop(request_id, None)
        return False, error or "gateway_send_failed", None

    completed = event.wait(timeout=IDE_REQUEST_TIMEOUT_SECONDS)
    with LIVE_LOCK:
        final = IDE_PENDING.pop(request_id, None) or pending
    if not completed:
        return False, "ide_request_timeout", None
    response = final.get("response")
    if not isinstance(response, dict):
        return False, "ide_response_missing", None
    return True, "ok", response


def openai_error(message: str, status: int = 400, error_type: str = "invalid_request_error"):
    return jsonify(error={
        "message": message,
        "type": error_type,
        "param": None,
        "code": message,
    }), status


def issue_device_credential(agent_id: str, owner_id: str | None = None) -> dict[str, Any]:
    issued_at = unix_now()
    expires_at = issued_at + DEVICE_CREDENTIAL_TTL_SECONDS
    device_id = secrets.token_urlsafe(18)

    payload = {
        "v": 1,
        "agent_id": agent_id,
        "owner_id": str(owner_id or "").strip() or None,
        "device_id": device_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "scope": "mesh-gateway",
        "mode": "plug-and-monitor",
    }
    encoded = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        device_credential_secret(),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "credential": f"PTMDC1.{encoded}.{signature}",
        "device_id": device_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }


def validate_device_credential(agent_id: str, credential: str) -> tuple[bool, str, dict[str, Any] | None]:
    try:
        prefix, encoded, signature = credential.split(".", 2)
        if prefix != "PTMDC1":
            return False, "device_credential_prefix_invalid", None

        expected = hmac.new(
            device_credential_secret(),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False, "device_credential_signature_invalid", None

        payload = json.loads(_b64url_decode(encoded).decode("utf-8"))
    except (ValueError, binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        return False, "device_credential_malformed", None

    if payload.get("agent_id") != agent_id:
        return False, "device_credential_agent_mismatch", None
    if payload.get("scope") != "mesh-gateway":
        return False, "device_credential_scope_invalid", None
    if payload.get("mode") != "plug-and-monitor":
        return False, "device_credential_mode_invalid", None
    if int(payload.get("expires_at", 0)) < unix_now():
        return False, "device_credential_expired", None
    if str(payload.get("device_id", "")) in REVOKED_DEVICE_IDS:
        return False, "device_credential_revoked", None

    return True, "ok", payload


def activation_secret() -> bytes:
    value = os.environ.get("MESH_ACTIVATION_SECRET", "")
    if not value:
        value = os.environ.get("SECRET_KEY", "dev-only-change-me")
    return value.encode("utf-8")


def activation_signature(agent_id: str, code: str, issued_at: int) -> str:
    # Enrollment authorization is user-lifecycle-bound, not clock-bound.
    # issued_at is signed for audit/context; validity ends only on cancel or redeem.
    payload = f"{agent_id}|{code}|{issued_at}".encode("utf-8")
    return hmac.new(activation_secret(), payload, hashlib.sha256).hexdigest()


def issue_activation_code(agent_id: str, owner_id: str | None = None) -> dict[str, Any]:
    # Reuse an existing active request for this agent. Opening/reloading the PWA must
    # not silently invalidate a user-controlled enrollment session.
    for existing in ACTIVATION_CODES.values():
        if (
            existing.get("agent_id") == agent_id
            and str(existing.get("owner_id") or "") == str(owner_id or "")
            and not existing.get("used")
            and not existing.get("cancelled")
        ):
            return existing

    code = secrets.token_urlsafe(18)
    issued_at = unix_now()
    signature = activation_signature(agent_id, code, issued_at)
    record = {
        "agent_id": agent_id,
        "owner_id": str(owner_id or "").strip() or None,
        "code": code,
        "issued_at": issued_at,
        "signature": signature,
        "used": False,
        "cancelled": False,
        "lifecycle": "until_cancelled_or_redeemed",
    }
    ACTIVATION_CODES[code] = record
    return record


def validate_activation_code(agent_id: str, code: str, signature: str) -> tuple[bool, str]:
    record = ACTIVATION_CODES.get(code)
    if not record:
        return False, "activation_code_not_found"
    if record.get("cancelled"):
        return False, "activation_code_cancelled"
    if record.get("used"):
        return False, "activation_code_used"
    if record["agent_id"] != agent_id:
        return False, "activation_agent_mismatch"

    expected = activation_signature(agent_id, code, int(record["issued_at"]))
    if not hmac.compare_digest(expected, signature):
        return False, "activation_signature_invalid"
    return True, "ok"




def deployment_tier() -> str:
    return os.environ.get("MESH_DEPLOYMENT_TIER", "development").strip().lower()


def production_configuration_status() -> dict[str, Any]:
    tier = deployment_tier()
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    secret_key = os.environ.get("SECRET_KEY", "")
    activation_secret_value = os.environ.get("MESH_ACTIVATION_SECRET", "")
    device_secret = os.environ.get("MESH_DEVICE_CREDENTIAL_SECRET", "")
    auth_mode = os.environ.get("MESH_AUTH_MODE", "development").strip().lower()
    identity_mode = os.environ.get("MESH_AGENT_IDENTITY_MODE", "development").strip().lower()
    codeseal_mode = os.environ.get("CODESEAL_VERIFIER_MODE", "unconfigured").strip().lower()

    add("session_secret", bool(secret_key) and secret_key != "dev-only-change-me",
        "SECRET_KEY must be supplied from production secret storage.")
    add("activation_secret", bool(activation_secret_value),
        "MESH_ACTIVATION_SECRET must be independently configured.")
    add("device_credential_secret", bool(device_secret),
        "MESH_DEVICE_CREDENTIAL_SECRET must be independently configured.")
    add("development_auth_disabled", os.environ.get("DEV_AUTH_ENABLED", "1") == "0",
        "DEV_AUTH_ENABLED must be 0 outside development.")
    add("development_agents_disabled", os.environ.get("DEV_SEED_AGENTS", "1") == "0",
        "DEV_SEED_AGENTS must be 0 outside development.")
    add("firebase_email_link_selected", auth_mode in ("firebase-email-link", "progretech-shared"),
        "Production user authentication uses the shared ProgreTech broker or qualified Firebase email-link mode.")
    add("firebase_client_configured", (auth_mode == "progretech-shared" or firebase_client_ready()),
        "Firebase public web configuration must be supplied for passwordless sign-in.")
    add("firebase_admin_ready", (auth_mode == "progretech-shared" or firebase_admin_ready()),
        "Set MESH_FIREBASE_AUTH_READY=1 only after Firebase Admin verification and a real email-link sign-in are tested.")
    add("codeseal_selected", identity_mode == "codeseal",
        "Production agent identity must use CodeSeal mode.")
    add("codeseal_verifier_configured", codeseal_mode == "configured",
        "Real cryptographic CodeSeal verification must be configured.")
    add("codeseal_adapter_ready", os.environ.get("MESH_CODESEAL_READY", "0") == "1",
        "Set MESH_CODESEAL_READY=1 only after real signature verification is tested.")

    required = checks if tier == "production" else []
    return {
        "deployment_tier": tier,
        "ready": all(item["ok"] for item in required),
        "checks": checks,
    }


# noinspection PyShadowingNames

def _expire_direct_signal_sessions() -> None:
    now = unix_now()
    with LIVE_LOCK:
        expired = [
            signal_id for signal_id, value in DIRECT_SIGNAL_SESSIONS.items()
            if int(value.get("expires_at", 0)) <= now
        ]
        for signal_id in expired:
            DIRECT_SIGNAL_SESSIONS.pop(signal_id, None)



def _csv_env(name: str) -> list[str]:
    raw = str(os.environ.get(name, "")).strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _transport_policy(value: str | None) -> str:
    candidate = str(value or "direct_preferred").strip().lower()
    if candidate not in {"direct_preferred", "direct_only", "relay_allowed"}:
        raise ValueError("invalid_transport_policy")
    return candidate


def _ice_servers_for_policy(policy: str) -> list[dict[str, Any]]:
    resolved = _transport_policy(policy)
    servers: list[dict[str, Any]] = []

    stun_urls = _csv_env("MESH_STUN_URLS")
    if not stun_urls:
        # Public STUN is used only for NAT discovery; it does not carry Mesh session data.
        stun_urls = ["stun:stun.l.google.com:19302"]
    servers.append({"urls": stun_urls})

    if resolved != "direct_only":
        turn_urls = _csv_env("MESH_TURN_URLS")
        turn_username = str(os.environ.get("MESH_TURN_USERNAME", "")).strip()
        turn_credential = str(os.environ.get("MESH_TURN_CREDENTIAL", "")).strip()
        if turn_urls and turn_username and turn_credential:
            servers.append({
                "urls": turn_urls,
                "username": turn_username,
                "credential": turn_credential,
            })

    return servers


def _relay_available() -> bool:
    return bool(
        _csv_env("MESH_TURN_URLS")
        and str(os.environ.get("MESH_TURN_USERNAME", "")).strip()
        and str(os.environ.get("MESH_TURN_CREDENTIAL", "")).strip()
    )


def direct_transport_contract() -> dict[str, Any]:
    return {
        "routing_policy": "direct_preferred",
        "principle": "owner_and_agent_are_the_data_endpoints",
        "paths": [
            {"id": "lan_direct", "priority": 1, "data_via_progretech": False},
            {"id": "internet_p2p", "priority": 2, "data_via_progretech": False},
            {"id": "encrypted_relay", "priority": 3, "data_via_progretech": True, "optional": True},
        ],
        "signaling": {
            "progretech_may_introduce_peers": True,
            "signaling_is_ephemeral": True,
            "signaling_is_not_agent_conversation_data": True,
        },
        "owner_controls": ["direct_preferred", "direct_only", "relay_allowed"],
        "routing": {
            "stun_supported": True,
            "turn_supported": True,
            "relay_configured": _relay_available(),
            "default_policy": "direct_preferred",
            "offline_same_lan_supported": True,
            "cloud_signaling_required_for_same_lan_reconnect": False,
        },
        "release_gate": "direct transport must pass live agent acceptance before feature expansion",
    }

def create_app() -> Flask:
    owner_uid_bindings()  # Reject invalid administrator access configuration at startup.
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    sock = Sock(app)

    environment = os.environ.get("APP_ENV", "development").lower()
    dev_auth_default = "1" if environment == "development" else "0"
    dev_seed_default = "1" if environment == "development" else "0"

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        ENVIRONMENT=environment,
        MESH_VERSION=os.environ.get("MESH_VERSION", "1.18.3-e2e-stability"),
        BUILD_ID=os.environ.get("BUILD_ID", BUILD_ID),
        DEV_AUTH_ENABLED=os.environ.get("DEV_AUTH_ENABLED", dev_auth_default) == "1",
        DEV_SEED_AGENTS=os.environ.get("DEV_SEED_AGENTS", dev_seed_default) == "1",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=environment == "production",
    )

    register_capability_routes(app)
    register_capability_registry_routes(app)
    register_capability_runtime_routes(app)

    if app.config["DEV_SEED_AGENTS"]:
        seed_development_registry()

    if os.environ.get("TRUST_PROXY_HEADERS", "1") == "1":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    register_firebase_auth_routes(app)
    register_progretech_auth(app)
    register_cloud_health_routes(app)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), payment=(), usb=(), local-network=(self), loopback-network=(self)",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' https://www.gstatic.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "connect-src 'self' http: https: ws: wss: https://identitytoolkit.googleapis.com https://securetoken.googleapis.com; "
            "media-src 'self' blob:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none';",
        )
        if request.is_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        if request.path.startswith("/api/") or request.path.startswith("/ws/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def require_session(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("mesh_user"):
                if request.path.startswith("/api/"):
                    return jsonify(ok=False, error="authentication_required"), 401
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    def current_mesh_user_id() -> str:
        return fleet_owner_id(session.get("mesh_user"))

    management_send=send_gateway_message
    if os.environ.get('MESH_LOCAL_CONTROL_CENTER')=='1':
        if environment=='production' or not app.config['DEV_AUTH_ENABLED']:
            raise ValueError('local_host_requires_local_development_auth')
        from mesh_local_host import LocalHost
        local_host=LocalHost()
        management_send=local_host.send
        @app.before_request
        def local_host_only():
            if request.remote_addr not in {'127.0.0.1','::1'} or request.host.split(':')[0] not in {'127.0.0.1','localhost'}:
                return jsonify(ok=False,error='loopback_required'),403
            if request.headers.get('Sec-Fetch-Site')=='cross-site':
                return jsonify(ok=False,error='same_origin_required'),403
            local_host.refresh(DEV_AGENT_REGISTRY,GATEWAY_SOCKETS)

    from mesh_local_updates import register_local_updates
    register_local_updates(app, require_session)

    from mesh_office import register_office_routes
    register_office_routes(app, require_session, current_mesh_user_id, DEV_AGENT_REGISTRY, GATEWAY_SOCKETS, management_send)
    register_management_routes(app, require_session, current_mesh_user_id, DEV_AGENT_REGISTRY, GATEWAY_SOCKETS, management_send)
    @app.get('/agents/<agent_id>/task-board')
    @require_session
    def agent_task_board(agent_id):
        record=DEV_AGENT_REGISTRY.get(agent_id)
        if not record or record.get('owner_id') != current_mesh_user_id():abort(404)
        return render_template('task_board.html',agent=record,build_id=BUILD_ID)

    register_factory_routes(app, require_session, current_mesh_user_id, DEV_AGENT_REGISTRY, GATEWAY_SOCKETS, management_send)
    register_control_center_routes(app, require_session, current_mesh_user_id,
                                   DEV_AGENT_REGISTRY, GATEWAY_SOCKETS, management_send)

    @app.before_request
    def restrict_linked_role_credentials():
        parts = request.path.split("/")
        if len(parts) >= 4 and parts[1:3] == ["api", "agents"]:
            record = DEV_AGENT_REGISTRY.get(parts[3], {})
            if record.get("control_center_gateway") and parts[4:] not in (["control-center"], ["management"], ["message"], ["office"]):
                return jsonify(ok=False, error="linked_role_uses_host_identity"), 409


    @app.before_request
    def enforce_session_agent_ownership():
        user = session.get("mesh_user")
        if not user:
            return None
        view_args = request.view_args or {}
        agent_id = str(view_args.get("agent_id") or "").strip()
        if not agent_id:
            return None
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return None
        allowed, _reason = ownership_can_access(record, current_mesh_user_id())
        if not allowed:
            if request.path.startswith("/api/"):
                return jsonify(ok=False, error="agent_not_found"), 404
            abort(404)
        return None

    @app.after_request
    def apply_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), payment=(), usb=(), local-network=(self), loopback-network=(self)",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' https://www.gstatic.com; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self' http: https: ws: wss: https://identitytoolkit.googleapis.com https://securetoken.googleapis.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none';",
        )
        if response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    @app.get("/login")
    def login():
        if session.get("mesh_user"):
            return redirect(url_for("index"))

        auth_mode = production_auth_mode()
        return render_template(
            "login.html",
            dev_auth_enabled=app.config["DEV_AUTH_ENABLED"],
            environment=app.config["ENVIRONMENT"],
            version=app.config["MESH_VERSION"],
            build_id=app.config["BUILD_ID"],
            auth_mode=auth_mode,
        )

    @app.post("/login/dev")
    def login_dev():
        if not app.config["DEV_AUTH_ENABLED"]:
            abort(404)
        session.clear()
        session["mesh_user"] = {
            "id": "local-edwin",
            "display_name": "Edwin",
            "auth_source": "local-development",
        }
        target = request.args.get("next") or url_for("index")
        if not target.startswith("/"):
            target = url_for("index")
        return redirect(target)

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @require_session
    def index():
        return render_template(
            "index.html",
            version=app.config["MESH_VERSION"],
            environment=app.config["ENVIRONMENT"],
            build_id=app.config["BUILD_ID"],
            user=session["mesh_user"],
        )

    @app.get("/healthz")
    def healthz():
        return jsonify(
            ok=True,
            service="progretech-mesh",
            version=app.config["MESH_VERSION"],
            build=app.config["BUILD_ID"],
            timestamp=utcnow(),
        )

    @app.get("/startupz")
    def startupz():
        return jsonify(ok=True, started=True, service="progretech-mesh", timestamp=utcnow())

    @app.get("/readyz")
    def readyz():
        status = production_configuration_status()
        code = 200 if status["ready"] else 503
        return jsonify(
            ok=status["ready"],
            ready=status["ready"],
            deployment_tier=status["deployment_tier"],
            failed_checks=[
                item["name"] for item in status["checks"] if not item["ok"]
            ] if status["deployment_tier"] == "production" else [],
        ), code

    @app.get("/api/product/contract")
    @require_session
    def product_contract():
        return jsonify(
            ok=True,
            product="ProgreTech Mesh",
            integration_mode="plug-and-monitor",
            channel_isolation=True,
            supported_activity_filters=["all", "telegram", "mesh", "system"],
            guided_training=True,
            guided_training_storage="browser-local",
            workstation_access_required_for_user=False,
            cloud_operational_history=False,
            arbitrary_remote_shell=False,
            pwa=True,
        )

    @app.get("/api/activation/contract")
    @require_session
    def activation_contract():
        return jsonify(
            ok=True,
            user_workstation_access_required=False,
            enrollment_delivery="existing-agent-chat",
            agent_led_setup=True,
            reconnect="signed-local-device-credential",
            integration_mode="plug-and-monitor",
            observation="read-only",
            channel_isolation=True,
            credential_storage="agent-local",
            operational_history_storage="none",
            revocation_supported=True,
            production_revocation_registry_required=True,
        )

    @app.get("/api/identity/contract")
    @require_session
    def identity_contract():
        auth_mode = os.environ.get("MESH_AUTH_MODE", "development").strip().lower()
        agent_identity_mode = os.environ.get(
            "MESH_AGENT_IDENTITY_MODE", "development"
        ).strip().lower()
        codeseal_configured = (
            os.environ.get("CODESEAL_VERIFIER_MODE", "unconfigured").strip().lower()
            == "configured"
        )
        codeseal_ready = os.environ.get("MESH_CODESEAL_READY", "0").strip() == "1"
        replay_mode = os.environ.get(
            "MESH_IDENTITY_REPLAY_MODE", "unconfigured"
        ).strip().lower()
        replay_qualified = replay_mode == "single-process-bounded"

        return jsonify(
            ok=True,
            user_auth={
                "mode": auth_mode,
                "production_ready": auth_mode == "oidc",
                "provider_specific_callback_configured": False,
            },
            agent_identity={
                "mode": agent_identity_mode,
                "production_ready": (
                    agent_identity_mode == "codeseal"
                    and codeseal_configured
                    and codeseal_ready
                    and replay_qualified
                ),
                "cryptographic_verification": (
                    agent_identity_mode == "codeseal" and codeseal_configured
                ),
                "fail_closed": agent_identity_mode == "codeseal",
                "codeseal_ready": codeseal_ready,
                "replay_protection": {
                    "mode": replay_mode,
                    "qualified": replay_qualified,
                    "challenge_ttl_seconds": IDENTITY_CHALLENGE_TTL_SECONDS,
                    "storage": "process-local",
                    "required_cloud_run_max_instances": 1,
                    "required_gunicorn_workers": 1,
                },
            },
            trust_rule=(
                "Development identity must never be represented as production "
                "cryptographic CodeSeal verification."
            ),
        )

    @app.get("/api/notifications/contract")
    @require_session
    def notification_contract():
        return jsonify(
            ok=True,
            preference_storage="browser-local",
            browser_notifications=True,
            background_web_push=False,
            sensitive_content_in_notifications=False,
            default_categories={
                "reply": True,
                "task_complete": True,
                "approval_required": True,
                "error_blocker": True,
                "file_ready": True,
                "gateway_offline": True,
                "gateway_reconnected": True,
                "progress": False,
                "routine_status": False,
            },
        )

    @app.get("/api/runtime/contract")
    @require_session
    def runtime_contract():
        return jsonify(
            ok=True,
            protocol="mesh-message-v1",
            gateway_runtime_selection="MESH_RUNTIME_ADAPTER",
            supported_adapters=["demo", "openclaw"],
            observation_adapters=["none", "jsonl"],
            message_types=["message_request", "message_response"],
            file_context="local staged paths may be supplied to the runtime adapter",
            integration_mode="plug-and-monitor",
            channel_isolation=True,
            passive_observation=True,
        )

    @app.get("/api/auth/status")
    def auth_status():
        mode = production_auth_mode()
        return jsonify(
            ok=True,
            mode=mode,
            configured=(
                app.config["DEV_AUTH_ENABLED"]
                if mode == "development"
                else bool(os.environ.get("MESH_OIDC_ISSUER"))
            ),
            oidc_issuer=os.environ.get("MESH_OIDC_ISSUER") if mode == "oidc" else None,
        )




    @app.get("/api/ownership/contract")
    @require_session
    def ownership_contract():
        return jsonify(
            ok=True,
            mode=ownership_mode(),
            explicit_owner_binding=True,
            legacy_unowned_access=(ownership_mode() == "observe"),
            claim_ttl_seconds=OWNERSHIP_CLAIM_TTL_SECONDS,
            claim_delivery="existing-agent-chat",
            claim_rotation="new owner-bound device credential",
        )

    @app.post("/api/ownership/claims")
    @require_session
    def create_ownership_claim():
        body = request.get_json(silent=True) or {}
        agent_id = str(body.get("agent_id") or "").strip()
        if agent_id:
            record = DEV_AGENT_REGISTRY.get(agent_id)
            if record:
                current_owner = str(record.get("owner_id") or "").strip()
                if current_owner and current_owner != current_mesh_user_id():
                    return jsonify(ok=False, error="agent_not_found"), 404
                if current_owner == current_mesh_user_id():
                    return jsonify(ok=False, error="ownership_already_bound"), 409
        claim = issue_ownership_claim(current_mesh_user_id(), agent_id or None)
        payload = f"PTMOWN1:{claim['code']}"
        return jsonify(
            ok=True,
            claim_code=claim["code"],
            claim_payload=payload,
            agent_id=agent_id or None,
            expires_at=claim["expires_at"],
            instructions=(
                "Send the PTMOWN1 payload to the already-enrolled agent. "
                "The agent must redeem it using its existing Mesh device credential."
            ),
        ), 201

    @app.post("/api/ownership/redeem")
    def redeem_ownership_claim():
        body = request.get_json(silent=True) or {}
        agent_id = str(body.get("agent_id") or "").strip()
        credential = str(body.get("device_credential") or "").strip()
        claim_code = str(body.get("claim_code") or "").strip()
        if not agent_id or not credential or not claim_code:
            return jsonify(ok=False, error="ownership_redeem_fields_required"), 400

        valid, reason, device_payload = validate_device_credential(agent_id, credential)
        if not valid:
            return jsonify(ok=False, error=reason), 401

        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record or record.get("trust_state") != "verified":
            return jsonify(ok=False, error="verified_agent_required"), 403

        ok, reason, claim = consume_ownership_claim(claim_code, agent_id)
        if not ok:
            return jsonify(ok=False, error=reason), 403

        existing_owner = str(record.get("owner_id") or "").strip()
        new_owner = str((claim or {}).get("owner_id") or "").strip()
        if existing_owner and existing_owner != new_owner:
            return jsonify(ok=False, error="ownership_already_bound"), 409

        if existing_owner:
            return jsonify(ok=False, error="ownership_already_bound"), 409

        old_device_id = str((device_payload or {}).get("device_id") or "").strip()
        record["owner_id"] = new_owner
        rotated = issue_device_credential(agent_id, owner_id=new_owner)
        record["identity_device_id"] = rotated["device_id"]
        if old_device_id:
            REVOKED_DEVICE_IDS.add(old_device_id)

        append_event(agent_id, {
            "type": "ownership_bound",
            "message": "Agent ownership bound to authenticated Mesh user",
            "payload": {
                "severity": "info",
                "event_class": "identity",
                "owner_bound": True,
                "device_rotated": True,
            },
        })
        return jsonify(
            ok=True,
            agent_id=agent_id,
            owner_bound=True,
            device_credential=rotated["credential"],
            device_id=rotated["device_id"],
            device_credential_expires_at=rotated["expires_at"],
            reconnect_mode="signed-device-credential",
        )

    @app.get("/api/ide/contract")
    @require_session
    def ide_contract():
        return jsonify(
            ok=True,
            protocol="openai-compatible",
            base_url=f"{mesh_public_origin()}/v1",
            bearer_scheme="PTMIDE1",
            token_ttl_seconds=IDE_TOKEN_TTL_SECONDS,
            request_timeout_seconds=IDE_REQUEST_TIMEOUT_SECONDS,
            streaming="single-completion SSE compatibility",
            transport="HTTPS -> owner-scoped Mesh gateway -> OpenClaw role agent",
        )

    @app.post("/api/agents/<agent_id>/ide/token")
    @require_session
    def create_ide_token(agent_id: str):
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return jsonify(ok=False, error="agent_not_found"), 404
        allowed, _reason = ownership_can_access(record, current_mesh_user_id())
        if not allowed or str(record.get("owner_id") or "").strip() != current_mesh_user_id():
            return jsonify(ok=False, error="agent_not_found"), 404
        if record.get("trust_state") != "verified":
            return jsonify(ok=False, error="verified_agent_required"), 403
        issued = issue_ide_token(current_mesh_user_id(), agent_id)
        return jsonify(
            ok=True,
            agent_id=agent_id,
            api_key=issued["token"],
            base_url=f"{mesh_public_origin()}/v1",
            expires_at=issued["expires_at"],
            models=ide_models(agent_id),
            recommended_model=f"{agent_id}-code",
        ), 201

    @app.get("/v1/models")
    def openai_models():
        valid, reason, payload = validate_ide_token(ide_bearer_token())
        if not valid:
            return openai_error(reason, 401, "authentication_error")
        agent_id = str((payload or {}).get("agent_id") or "")
        now = unix_now()
        return jsonify(
            object="list",
            data=[
                {"id": model, "object": "model", "created": now, "owned_by": f"mesh:{agent_id}"}
                for model in ide_models(agent_id)
            ],
        )

    @app.post("/v1/chat/completions")
    def openai_chat_completions():
        valid, reason, payload = validate_ide_token(ide_bearer_token())
        if not valid:
            return openai_error(reason, 401, "authentication_error")
        agent_id = str((payload or {}).get("agent_id") or "")
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record or record.get("transport") != "connected":
            return openai_error("gateway_not_connected", 503, "service_unavailable")

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return openai_error("invalid_request", 400)
        model = str(body.get("model") or "").strip()
        if model not in ide_models(agent_id):
            return openai_error("model_not_allowed", 400)
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            return openai_error("messages_required", 400)

        requested_stream = bool(body.get("stream"))
        relay_body = dict(body)
        relay_body["stream"] = False

        ok, error, response = dispatch_ide_chat(agent_id, relay_body)
        if not ok:
            status = 504 if error == "ide_request_timeout" else 502
            return openai_error(error, status, "upstream_error")

        response_payload = (response or {}).get("payload") or {}
        if not response_payload.get("ok", True):
            return openai_error(str(response_payload.get("error") or "agent_ide_relay_failed"), 502, "upstream_error")
        completion = response_payload.get("completion")
        if not isinstance(completion, dict):
            return openai_error("invalid_agent_completion", 502, "upstream_error")

        if not requested_stream:
            return jsonify(completion)

        try:
            choice = (completion.get("choices") or [])[0]
            assistant_message = choice.get("message") or {}
            delta = {"role": "assistant"}
            if assistant_message.get("content") is not None:
                delta["content"] = assistant_message["content"]
            if assistant_message.get("tool_calls"):
                delta["tool_calls"] = [{**tool, "index": index} for index, tool in enumerate(assistant_message["tool_calls"])]
            finish_reason = str(choice.get("finish_reason") or "stop")
        except (IndexError, TypeError, AttributeError):
            return openai_error("invalid_agent_completion", 502, "upstream_error")

        chunk_id = str(completion.get("id") or f"chatcmpl-{secrets.token_urlsafe(12)}")
        created = int(completion.get("created") or unix_now())
        chunk_model = str(completion.get("model") or model)
        first = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": chunk_model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        }
        last = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": chunk_model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
        }
        data = (
            f"data: {json.dumps(first, separators=(',', ':'))}\n\n"
            f"data: {json.dumps(last, separators=(',', ':'))}\n\n"
            "data: [DONE]\n\n"
        )
        return Response(data, status=200, mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        })

    @app.get("/api/enrollment/protocol")
    def universal_agent_enrollment_protocol():
        path = distribution_file(UNIVERSAL_ENROLLMENT_PROTOCOL_FILENAME)
        if not path.is_file():
            return jsonify(ok=False, error="enrollment_protocol_unavailable"), 503
        try:
            protocol = json.loads(path.read_text(encoding="utf-8"))
            origin = mesh_public_origin()
        except (OSError, json.JSONDecodeError, ValueError):
            return jsonify(ok=False, error="enrollment_protocol_unavailable"), 503
        protocol["endpoints"] = {
            "protocol": f"{origin}/api/enrollment/protocol",
            "adapter_catalog": f"{origin}/api/enrollment/adapters",
        }
        response = jsonify(protocol)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/enrollment/adapters")
    def universal_agent_adapter_catalog():
        path = distribution_file(AGENT_ADAPTER_CATALOG_FILENAME)
        package = openclaw_plugin_package_path()
        helper = distribution_file(OPENCLAW_SELF_BOOTSTRAP_FILENAME)
        if not path.is_file() or not package.is_file() or not helper.is_file():
            return jsonify(ok=False, error="adapter_catalog_unavailable"), 503
        try:
            catalog = json.loads(path.read_text(encoding="utf-8"))
            origin = mesh_public_origin()
        except (OSError, json.JSONDecodeError, ValueError):
            return jsonify(ok=False, error="adapter_catalog_unavailable"), 503
        for adapter in catalog.get("adapters", []):
            if adapter.get("id") != "openclaw":
                continue
            adapter.setdefault("package", {})["version"] = OPENCLAW_PLUGIN_PACKAGE_VERSION
            adapter["package"]["sha256"] = sha256_file(package)
            adapter["package"]["url"] = (
                f"{origin}/api/distribution/openclaw/progretech-mesh/"
                f"{OPENCLAW_PLUGIN_PACKAGE_VERSION}/package"
            )
            bootstrap = adapter.setdefault("self_bootstrap", {})
            bootstrap["plan_url"] = f"{origin}/api/enrollment/adapters/openclaw/install-plan"
            bootstrap["helper_url"] = f"{origin}/api/enrollment/adapters/openclaw/bootstrap"
            bootstrap["helper_sha256"] = sha256_file(helper)
        response = jsonify(catalog)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/enrollment/adapters/openclaw/install-plan")
    def openclaw_self_bootstrap_plan():
        path = distribution_file(OPENCLAW_SELF_BOOTSTRAP_PLAN_FILENAME)
        if not path.is_file():
            return jsonify(ok=False, error="openclaw_install_plan_unavailable"), 503
        response = send_file(path, mimetype="application/json", as_attachment=False, conditional=True)
        response.headers["Cache-Control"] = "public, max-age=300"
        return response

    @app.get("/api/enrollment/adapters/openclaw/bootstrap")
    def openclaw_self_bootstrap_helper():
        path = distribution_file(OPENCLAW_SELF_BOOTSTRAP_FILENAME)
        if not path.is_file():
            return jsonify(ok=False, error="openclaw_bootstrap_unavailable"), 503
        response = send_file(path, mimetype="text/x-shellscript", as_attachment=False, conditional=True)
        response.headers["Cache-Control"] = "public, max-age=300"
        response.headers["X-Mesh-SHA256"] = sha256_file(path)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/api/distribution/openclaw/progretech-mesh")
    def openclaw_plugin_distribution_metadata():
        package = openclaw_plugin_package_path()
        if not package.is_file():
            return jsonify(ok=False, error="plugin_package_unavailable"), 503
        return jsonify(
            ok=True,
            package_id="progretech-mesh-openclaw",
            version=OPENCLAW_PLUGIN_PACKAGE_VERSION,
            filename=package.name,
            sha256=sha256_file(package),
            signature={
                "mode": os.environ.get("MESH_CODESEAL_PACKAGE_MODE", "unconfigured"),
                "codeseal_verified": False,
            },
        )

    @app.get("/api/distribution/openclaw/progretech-mesh/<version>/package")
    def download_openclaw_plugin_distribution(version: str):
        if version != OPENCLAW_PLUGIN_PACKAGE_VERSION:
            return jsonify(ok=False, error="plugin_version_not_found"), 404
        package = openclaw_plugin_package_path()
        if not package.is_file():
            return jsonify(ok=False, error="plugin_package_unavailable"), 503
        response = send_file(
            package,
            mimetype="application/gzip",
            as_attachment=True,
            download_name=package.name,
            conditional=True,
        )
        response.headers["Cache-Control"] = "public, max-age=300, immutable"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.post("/api/agents/<agent_id>/enrollment-message")
    @require_session
    # noinspection DuplicatedCode
    def create_agent_enrollment_message(agent_id: str):
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return jsonify(ok=False, error="agent_not_found"), 404
        if str(record.get("owner_id") or "").strip() != current_mesh_user_id():
            return jsonify(ok=False, error="agent_not_found"), 404
        if record.get("trust_state") != "verified":
            return jsonify(ok=False, error="verified_identity_required"), 403

        activation = issue_activation_code(agent_id, current_mesh_user_id())
        try:
            mesh_origin = mesh_public_origin()
        except ValueError as exc:
            ACTIVATION_CODES.pop(activation["code"], None)
            return jsonify(ok=False, error=str(exc)), 503

        package = openclaw_plugin_package_path()
        if not package.is_file():
            return jsonify(ok=False, error="plugin_package_unavailable"), 503

        package_sha256 = sha256_file(package)
        package_url = (
            f"{mesh_origin}/api/distribution/openclaw/progretech-mesh/"
            f"{OPENCLAW_PLUGIN_PACKAGE_VERSION}/package"
        )

        server_now = unix_now()

        envelope = {
            "type": "PROGRETECH_MESH_CONNECT_OR_ENROLL",
            "version": 5,
            "mesh": mesh_origin,
            "discovery": {
                "protocol_url": f"{mesh_origin}/api/enrollment/protocol",
                "adapter_catalog_url": f"{mesh_origin}/api/enrollment/adapters",
                "preinstalled_progretech_component_required": False,
                "workstation_access_required": False,
                "agent_self_bootstrap_preferred": True,
                "runtime_hints": {
                    "openclaw": {
                        "install_plan_url": (
                            f"{mesh_origin}/api/enrollment/adapters/openclaw/install-plan"
                        ),
                        "bootstrap_helper_url": (
                            f"{mesh_origin}/api/enrollment/adapters/openclaw/bootstrap"
                        ),
                        "bootstrap_helper_sha256": sha256_file(distribution_file(OPENCLAW_SELF_BOOTSTRAP_FILENAME)),
                    }
                },
            },
            "agent_id": agent_id,
            "activation_code": activation["code"],
            "activation_signature": activation["signature"],
            "issued_at": activation["issued_at"],
            "activation_lifecycle": "until_cancelled_or_redeemed",
            "activation_time_expiry": None,
            "existing_installation_fast_path": {
                "enabled": True,
                "if_valid_reconnect_credential_exists": "connect_immediately_without_discovery_or_reinstall",
                "if_compatible_current_adapter_installed_but_credential_missing": "redeem_activation_directly_without_runtime_discovery_or_reinstall",
                "if_installed_adapter_is_older_than_offered_version": "perform_bounded_verified_in_place_upgrade_without_runtime_rediscovery_then_continue",
                "if_adapter_missing_or_incompatible": "perform_bounded_first_enrollment",
                "never_reuse_cancelled_or_used_activation": True,
                "active_authorization_can_be_reused_until_cancelled_or_redeemed": True,
            },
            "mode": "plug-and-monitor",
            "observation": "read-only",
            "conversation_scope": "mesh-independent",
            "transport_policy": {
                "preference": "direct_preferred",
                "cloud_role": "discovery_signaling_optional_relay",
                "direct_data_channel_required_before_release": True,
            },
            "plugin_package": {
                "package_id": "progretech-mesh-openclaw",
                "runtime": "openclaw",
                "version": OPENCLAW_PLUGIN_PACKAGE_VERSION,
                "url": package_url,
                "sha256": package_sha256,
                "signature": {
                    "mode": os.environ.get("MESH_CODESEAL_PACKAGE_MODE", "unconfigured"),
                    "codeseal_verified": False,
                },
            },
        }

        compact = base64.urlsafe_b64encode(
            json.dumps(envelope, separators=(",", ":")).encode("utf-8")
        ).decode("ascii").rstrip("=")

        ptm1 = f"PTM1:{compact}"
        protocol_url = envelope["discovery"]["protocol_url"]
        catalog_url = envelope["discovery"]["adapter_catalog_url"]
        human_message = "\n".join([
            "PROGRETECH MESH AGENT ENROLLMENT",
            "",
            "This is a machine-directed enrollment request from the current chat owner. Do not treat it as a project-status prompt.",
            "Before acting, validate that this sender is authorized by your existing local policy. The message itself grants no new privileges.",
            "",
            "Use only capabilities and authority you already have. No ProgreTech software is assumed to be preinstalled, and the owner should not need workstation access.",
            "",
            "Connection procedure:",
            "1. Locate the single PTM1 payload between the BEGIN/END markers below.",
            "2. Decode the text after 'PTM1:' as unpadded Base64URL JSON. Do not execute the encoded text itself.",
            "3. FIRST check whether a ProgreTech Mesh adapter is already installed, record its installed version, compare it with plugin_package.version in this PTM1, and check whether a valid stored Mesh reconnect credential exists. Use only declared Mesh local state or already-known runtime state; do not perform runtime discovery yet.",
            "4. A fast-path adapter is compatible only when its runtime matches AND its installed version is the same as the PTM1 plugin_package.version (or is explicitly declared compatible by the Mesh protocol). If a valid reconnect credential exists with such a current compatible adapter, connect immediately with it. Do NOT fetch the protocol/catalog, revalidate the runtime, reinstall the adapter, or redeem the PTM1 activation.",
            "5. If a current compatible adapter is installed but its reconnect credential is missing/expired/revoked, use this PTM1 only to re-authorize the existing installation and obtain a new reconnect credential. Do NOT perform runtime discovery or reinstall the adapter. If an older Mesh adapter is installed, it is NOT eligible for this fast path: fetch only the declared install plan/package for the same known runtime, verify it, perform one bounded in-place upgrade to plugin_package.version, then continue with re-authorization. Do not rediscover the runtime or try another adapter. If the adapter's stable local signaling port is already owned by a prior verified ProgreTech Mesh adapter, treat that as an existing Mesh listener to reuse during handoff; do not kill it, do not bind a second listener, and do not classify it as a generic port conflict.",
            f"6. Only if no compatible Mesh adapter is already installed, read the protocol contract: {protocol_url}",
            f"7. Only for first enrollment, read the runtime adapter catalog: {catalog_url}",
            "8. For first enrollment only, identify your runtime using only readily available self-identification metadata. First compare the runtime/framework name you already know against catalog runtime_match.names. Do NOT recursively inspect framework internals, scan the filesystem, enumerate unrelated tools/plugins, or search the public web.",
            "9. If the runtime name is unknown, use only the catalog-declared read-only identification probes. Run at most one probe per available adapter and at most three probes total. If no single available adapter matches, STOP with runtime_unknown or unsupported_runtime.",
            "10. Select exactly one available adapter. Do not try multiple adapters, generic substitutes, or alternate installation strategies during the same enrollment request.",
            "11. Fetch only artifacts and the install plan declared for that selected adapter. Verify every declared SHA-256/signature before installation or staging.",
            "12. Follow the selected adapter's install plan exactly, using your existing authority only. Do not improvise framework changes, privilege escalation, configuration rewrites, or unrelated diagnostics.",
            "13. Do not interrupt, restart, reset, replace, or reconfigure current work or existing conversations. Verified package staging and a declared hot-safe managed adapter install may proceed during this enrollment turn when the install plan explicitly says it does not restart the agent/runtime. Do not wait for generic idle merely because this enrollment conversation is active. If the runtime explicitly reports that a reload/restart is required, do not force it; STOP and report activation_reload_required.",
            "14. Keep Mesh observation read-only and Mesh conversation state independent from Telegram or any other existing channel.",
            "15. Redeem the active user-controlled authorization only after verification succeeds, connect outbound to Mesh, and preserve automatic reconnect locally.",
            "16. Retry a failed step at most once, and only when the protocol/install plan explicitly gives a recovery action. Never repeat exploratory commands in a loop.",
            "17. Enrollment target is 5 minutes. If not connected within 10 minutes of active work, STOP the current diagnostic attempt and report the smallest specific blocker. The authorization itself remains valid until the user cancels it or it is successfully redeemed, so a later retry does not require a new payload unless the user cancelled it.",
            "18. If activation validation fails for cancellation, replay/use, signature, audience/agent mismatch, or policy rejection, STOP immediately. Do not fetch discovery resources, install, diagnose, or retry that PTM1.",
            "19. At the first stable success/failure boundary, STOP. Report success or only the smallest specific missing capability/approval/verification error.",
            "",
            "Do not summarize the Mesh project, continue unrelated tasks, or ask the owner to manually install Mesh unless your environment truly cannot perform the required step.",
            "",
            "--- BEGIN PROGRETECH MESH ENROLLMENT ---",
            ptm1,
            "--- END PROGRETECH MESH ENROLLMENT ---",
        ])

        return jsonify(
            ok=True,
            agent_id=agent_id,
            request_id=activation["code"],
            issued_at=activation["issued_at"],
            server_time=server_now,
            activation_lifecycle="until_cancelled_or_redeemed",
            activation_time_expiry=None,
            active=True,
            enrollment_message=human_message,
            enrollment_payload=ptm1,
            protocol_url=protocol_url,
            adapter_catalog_url=catalog_url,
            preinstalled_progretech_component_required=False,
            payload_prefix="PTM1:",
            delivery="existing-agent-chat",
            user_workstation_access_required=False,
            advertised_origin=mesh_origin,
            routing_policy="direct_preferred",
        )

    @app.post("/api/agents/<agent_id>/enrollment/<request_id>/cancel")
    @require_session
    # noinspection DuplicatedCode
    def cancel_agent_enrollment(agent_id: str, request_id: str):
        activation = ACTIVATION_CODES.get(request_id)
        if (not activation or activation.get("agent_id") != agent_id
                or str(activation.get("owner_id") or "") != current_mesh_user_id()):
            return jsonify(ok=False, error="enrollment_not_found"), 404
        if activation.get("used"):
            return jsonify(ok=False, error="enrollment_already_used"), 409
        activation["cancelled"] = True
        activation["cancelled_at"] = unix_now()
        return jsonify(ok=True, cancelled=True, agent_id=agent_id, request_id=request_id)

    @app.post("/api/agents/<agent_id>/activation-code")
    @require_session
    # noinspection DuplicatedCode
    def create_activation_code(agent_id: str):
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return jsonify(ok=False, error="agent_not_found"), 404
        if record.get("trust_state") != "verified":
            return jsonify(ok=False, error="verified_identity_required"), 403

        activation = issue_activation_code(agent_id, current_mesh_user_id())
        return jsonify(
            ok=True,
            agent_id=agent_id,
            code=activation["code"],
            signature=activation["signature"],
            issued_at=activation["issued_at"],
            activation_lifecycle="until_cancelled_or_redeemed",
            bootstrap_command=(
                f'python install/mesh_agent_bootstrap.py '
                f'--mesh "{mesh_public_origin()}" '
                f'--agent "{agent_id}" '
                f'--activation-code "{activation["code"]}" '
                f'--activation-signature "{activation["signature"]}"'
            ),
        )

    @app.post("/api/agents/<agent_id>/identity/challenge")
    def create_agent_identity_challenge(agent_id: str):
        payload = request.get_json(silent=True) or {}
        credential = str(payload.get("device_credential", "")).strip()

        if not credential:
            return jsonify(ok=False, error="device_credential_required"), 401

        valid_device, reason, device_payload = validate_device_credential(agent_id, credential)
        if not valid_device:
            return jsonify(ok=False, error=reason), 401

        device_id = str((device_payload or {}).get("device_id", "")).strip()
        if not device_id:
            return jsonify(ok=False, error="device_id_missing"), 401

        challenge = issue_identity_challenge(agent_id, device_id)
        return jsonify(
            ok=True,
            challenge_id=challenge["challenge_id"],
            signing_payload=challenge["signing_payload"],
            expires_at=challenge["expires_at"],
            algorithm="Ed25519",
        )


    @app.post("/api/agents/<agent_id>/identity/assert")
    def assert_agent_identity(agent_id: str):
        payload = request.get_json(silent=True) or {}
        credential = str(payload.get("device_credential", "")).strip()
        public_key = str(payload.get("public_key", "")).strip()
        codeseal_evidence = payload.get("codeseal_evidence")
        challenge_id = str(payload.get("challenge_id", "")).strip()
        signature = str(payload.get("signature", "")).strip()

        if not credential:
            return jsonify(ok=False, error="device_credential_required"), 401

        valid_device, reason, device_payload = validate_device_credential(agent_id, credential)
        if not valid_device:
            return jsonify(ok=False, error=reason), 401

        device_id = str((device_payload or {}).get("device_id", "")).strip()
        if not public_key or not codeseal_evidence:
            return jsonify(ok=False, error="codeseal_identity_required"), 400
        if not challenge_id or not signature:
            return jsonify(ok=False, error="identity_proof_required"), 400

        record = DEV_AGENT_REGISTRY.get(agent_id)
        identity_binding = (
            ((codeseal_evidence or {}).get("manifest") or {}).get("mesh_identity")
            if isinstance(codeseal_evidence, dict) else None
        )
        identity_binding = identity_binding if isinstance(identity_binding, dict) else {}
        asserted_name = str(
            identity_binding.get("agent_name")
            or identity_binding.get("name")
            or agent_id
        ).strip()
        agent_name = str((record or {}).get("name") or asserted_name or agent_id).strip()

        challenge_ok, challenge_reason, challenge = consume_identity_challenge(
            agent_id, device_id, challenge_id
        )
        if not challenge_ok:
            return jsonify(ok=False, error=challenge_reason), 409

        proof_ok, proof_reason = verify_identity_proof(
            public_key,
            challenge["signing_payload"],
            signature,
        )
        if not proof_ok:
            append_event(agent_id, {
                "type": "identity_proof_rejected",
                "message": "Ed25519 identity proof rejected",
                "payload": {
                    "reason": proof_reason,
                    "severity": "warn",
                    "event_class": "identity",
                    "device_id": device_id,
                },
            })
            return jsonify(ok=False, error=proof_reason), 403

        verification = verify_runtime_agent_identity(
            {"agent_id": agent_id, "codeseal_evidence": codeseal_evidence},
            agent_name,
            public_key,
            "",
        )
        if verification["state"] in {"invalid", "revoked"} or not verification["valid"]:
            append_event(agent_id, {
                "type": "identity_assertion_rejected",
                "message": "CodeSeal identity assertion rejected",
                "payload": {
                    "reason": verification["reason"],
                    "severity": "warn",
                    "event_class": "identity",
                    "device_id": device_id,
                },
            })
            return jsonify(ok=False, error="agent_identity_rejected", verification=verification), 403

        if record is None:
            record = {
                "id": agent_id,
                "name": agent_name,
                "role": "ProgreTech Agent",
                "state": "offline",
                "task": "Awaiting gateway",
                "phase": "Identity rehydrated; awaiting live transport",
                "progress": 0,
                "model": "Unknown",
                "runtime": "—",
                "transport": "not-connected",
                "last_heartbeat": None,
                "telemetry": {},
                "enrolled_at": utcnow(),
                "fingerprint": fingerprint_for(agent_name, public_key, ""),
            }
            with LIVE_LOCK:
                DEV_AGENT_REGISTRY[agent_id] = record

        device_owner = str((device_payload or {}).get("owner_id") or "").strip()
        existing_owner = str(record.get("owner_id") or "").strip()
        if existing_owner and device_owner and existing_owner != device_owner:
            return jsonify(ok=False, error="agent_owner_mismatch"), 403

        record.update(
            owner_id=(device_owner or existing_owner or None),
            public_key=public_key,
            codeseal_key="",
            codeseal_evidence=codeseal_evidence,
            trust_state=verification["state"],
            trust_valid=verification["valid"],
            trust_reason=verification["reason"],
            verified_at=utcnow(),
            identity_proof="ed25519-challenge",
            identity_device_id=device_id,
        )
        append_event(agent_id, {
            "type": "identity_assertion_verified",
            "message": "CodeSeal identity + Ed25519 proof verified",
            "payload": {
                "provider": verification.get("provider", "codeseal"),
                "proof": "ed25519-challenge",
                "severity": "info",
                "event_class": "identity",
                "device_id": device_id,
            },
        })
        return jsonify(
            ok=True,
            agent_id=agent_id,
            trust_state=record["trust_state"],
            trust_valid=record["trust_valid"],
            trust_reason=record["trust_reason"],
            provider=verification.get("provider", "codeseal"),
            identity_proof="ed25519-challenge",
            device_id=device_id,
        )


    @app.post("/api/activation/redeem")
    def redeem_activation_code():
        payload = request.get_json(silent=True) or {}
        agent_id = str(payload.get("agent_id", "")).strip()
        code = str(payload.get("activation_code", "")).strip()
        signature = str(payload.get("activation_signature", "")).strip()

        valid, reason = validate_activation_code(agent_id, code, signature)
        if not valid:
            return jsonify(ok=False, error=reason), 403

        activation = ACTIVATION_CODES[code]
        activation["used"] = True

        token = secrets.token_urlsafe(32)
        expires_at = unix_now() + PAIR_TOKEN_TTL_SECONDS
        with LIVE_LOCK:
            PAIRING_TOKENS[token] = {
                "agent_id": agent_id,
                "expires_at": expires_at,
                "used": False,
            }

        mesh_origin = mesh_public_origin()
        ws_base = websocket_origin_from_http(mesh_origin)
        ws_url = f"{ws_base}/ws/gateway/{agent_id}?token={token}"

        owner_id = str(activation.get("owner_id") or "").strip() or None
        device = issue_device_credential(agent_id, owner_id=owner_id)
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if record is not None and owner_id:
            existing_owner = str(record.get("owner_id") or "").strip()
            if existing_owner and existing_owner != owner_id:
                return jsonify(ok=False, error="ownership_conflict"), 409
            record["owner_id"] = owner_id

        return jsonify(
            ok=True,
            agent_id=agent_id,
            pairing_token=token,
            pairing_expires_in=PAIR_TOKEN_TTL_SECONDS,
            websocket_url=ws_url,
            device_credential=device["credential"],
            device_id=device["device_id"],
            device_credential_expires_at=device["expires_at"],
            reconnect_mode="signed-device-credential",
        )

    @app.post("/api/agents/<agent_id>/devices/<device_id>/revoke")
    @require_session
    # noinspection DuplicatedCode
    def revoke_agent_device(agent_id: str, device_id: str):
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return jsonify(ok=False, error="agent_not_found"), 404

        REVOKED_DEVICE_IDS.add(device_id)

        with LIVE_LOCK:
            gateway = GATEWAY_SOCKETS.get(agent_id)
        if gateway is not None:
            try:
                gateway.close()
            except (OSError, RuntimeError):
                pass

        append_event(agent_id, {
            "type": "device_revoked",
            "message": "Mesh device access revoked",
            "payload": {
                "device_id": device_id,
                "severity": "warn",
                "event_class": "identity",
            },
        })

        return jsonify(ok=True, agent_id=agent_id, device_id=device_id, revoked=True)

    @app.get("/api/transport/contract")
    @require_session
    def transport_contract():
        return jsonify(ok=True, contract=direct_transport_contract())

    @app.get("/api/transport/acceptance")
    @require_session
    def transport_acceptance():
        return jsonify(
            ok=True,
            required_checks=[
                "hands_off_enrollment",
                "telegram_uninterrupted",
                "same_lan_direct",
                "internet_p2p",
                "direct_only_blocks_relay",
                "relay_fallback_when_allowed",
                "offline_pwa_shell",
                "offline_same_lan_reconnect",
                "mesh_conversation_isolated",
                "refresh_disconnect_does_not_interrupt_agent",
                "credential_reconnect",
            ],
            live_agent_required=True,
            reference_agent="rend",
        )

    @app.get("/api/transport/config")
    @require_session
    def transport_config():
        try:
            policy = _transport_policy(request.args.get("policy"))
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400

        ice_servers = _ice_servers_for_policy(policy)
        return jsonify(
            ok=True,
            policy=policy,
            ice_servers=ice_servers,
            relay_available=_relay_available(),
            signaling="ephemeral",
            default_route="direct",
        )

    @app.post("/api/agents/<agent_id>/transport/signal")
    @require_session
    def create_transport_signal(agent_id: str):
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return jsonify(ok=False, error="agent_not_found"), 404
        payload = request.get_json(silent=True) or {}
        signal_type = str(payload.get("type", "")).strip()
        if signal_type not in {"offer", "answer", "ice_candidate", "route_probe"}:
            return jsonify(ok=False, error="unsupported_signal_type"), 400

        signal_id = secrets.token_urlsafe(18)
        expires_at = unix_now() + DIRECT_SIGNAL_TTL_SECONDS
        entry = {
            "id": signal_id,
            "agent_id": agent_id,
            "type": signal_type,
            "payload": payload.get("payload", {}),
            "created_at": utcnow(),
            "expires_at": expires_at,
        }
        _expire_direct_signal_sessions()
        with LIVE_LOCK:
            DIRECT_SIGNAL_SESSIONS[signal_id] = entry

        # Signaling may pass through Mesh, but agent conversation/telemetry payloads do not.
        gateway_delivered = False
        if record.get("transport") == "connected":
            gateway_delivered, _reason = send_gateway_message(agent_id, {
                "type": "mesh_direct_signal",
                "signal": entry,
            })

        return jsonify(
            ok=True,
            signal_id=signal_id,
            expires_at=expires_at,
            gateway_delivered=gateway_delivered,
            data_path="signaling_only",
        )

    @app.get("/api/agents/<agent_id>/transport/signals/<signal_id>")
    @require_session
    def get_transport_signal(agent_id: str, signal_id: str):
        _expire_direct_signal_sessions()
        with LIVE_LOCK:
            entry = DIRECT_SIGNAL_SESSIONS.get(signal_id)
        if not entry or entry.get("agent_id") != agent_id:
            return jsonify(ok=False, error="signal_not_found"), 404
        return jsonify(ok=True, signal=entry)

    @app.get("/api/session")
    @require_session
    def api_session():
        return jsonify(ok=True, user=session["mesh_user"], retention="none")

    @app.get("/how-it-works")
    def how_it_works():
        return render_template("how_it_works.html")

    @app.get("/api/status")
    @require_session
    def api_status():
        agents = [public_agent(a) for a in DEV_AGENT_REGISTRY.values() if ownership_visible(a, current_mesh_user_id())]
        agents = [a for a in agents if not a.get("identity_alias") and not a.get("office_archived")]
        return jsonify(
            server_time=unix_now(),
            session={
                "active": True,
                "retention": "off",
                "transport": "live-gateway",
            },
            fleet={
                "connected": sum(1 for a in agents if a["transport"] == "connected" and (not a.get("control_center_gateway") or a.get("gateway_enrollment"))),
                "verified": sum(1 for a in agents if a["trust_state"] == "verified" and (not a.get("control_center_gateway") or a.get("gateway_enrollment"))),
                "signed_total": sum(1 for a in agents if not a.get("control_center_gateway") or a.get("gateway_enrollment")),
                "linked": sum(1 for a in agents if a.get("control_center_gateway") and not a.get("gateway_enrollment")),
                "total": len(agents),
            },
            agents=[a for a in agents if not a.get("identity_alias") and not a.get("office_archived")],
        )

    @app.get("/api/agents")
    @require_session
    def list_agents():
        agents = [public_agent(a) for a in DEV_AGENT_REGISTRY.values() if ownership_visible(a, current_mesh_user_id())]
        agents = [a for a in agents if not a.get("identity_alias") and not a.get("office_archived")]
        agents.sort(key=lambda a: (a["name"].lower(), a["id"]))
        return jsonify(ok=True, storage="ephemeral-in-process", agents=agents)

    @app.post("/api/agents/enroll")
    @require_session
    def enroll_agent():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict): return jsonify(ok=False, error="invalid_enrollment"), 400
        name = str(payload.get("name", "")).strip()
        role = str(payload.get("role", "ProgreTech Agent")).strip() or "ProgreTech Agent"
        public_key = str(payload.get("public_key", "")).strip()
        codeseal_key = str(payload.get("codeseal_key", "")).strip()
        codeseal_evidence = payload.get("codeseal_evidence")

        if not name or not public_key:
            return jsonify(ok=False, error="name_and_public_key_required"), 400

        from mesh_gateway_agents import enrollment_binding
        try:
            binding = enrollment_binding(payload, current_mesh_user_id(), DEV_AGENT_REGISTRY, GATEWAY_SOCKETS)
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        if binding:
            from mesh_agent_management import same_origin
            if not same_origin(): return jsonify(ok=False, error="same_origin_required"), 403
            if (os.environ.get('APP_ENV') == 'production'
                    and DEV_AGENT_REGISTRY[binding['control_center_gateway']].get('gateway_enrollment_restore_version') != 1):
                return jsonify(ok=False, error='gateway_enrollment_adapter_update_required'), 409
        verification = verify_runtime_agent_identity(payload, name, public_key, codeseal_key)
        if binding and (verification.get("provider") != "codeseal" or verification.get("valid") is not True):
            return jsonify(ok=False, error="independent_codeseal_identity_required"), 400
        if verification["state"] in {"invalid", "revoked"}:
            return jsonify(ok=False, error="agent_identity_rejected", verification=verification), 400

        identity = ((codeseal_evidence or {}).get("manifest") or {}).get("mesh_identity", {}) if isinstance(codeseal_evidence, dict) else {}
        agent_id = str(identity.get("agent_id") or secrets.token_hex(6))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", agent_id) or (agent_id in DEV_AGENT_REGISTRY and not binding):
            return jsonify(ok=False, error="agent_id_unavailable"), 409
        record = {
            "id": agent_id,
            "owner_id": current_mesh_user_id(),
            "name": name,
            "role": role,
            "public_key": public_key,
            "codeseal_key": codeseal_key,
            "codeseal_evidence": codeseal_evidence,
            "fingerprint": fingerprint_for(name, public_key, codeseal_key),
            "trust_state": verification["state"],
            "trust_valid": verification["valid"],
            "trust_reason": verification["reason"],
            "state": "offline",
            "task": "Awaiting gateway",
            "phase": "Enrollment complete · connecting agent",
            "progress": 0,
            "model": "Unknown",
            "runtime": "—",
            "enrolled_at": utcnow(),
            "transport": "not-connected",
            "last_heartbeat": None,
            "telemetry": {},
        }
        with LIVE_LOCK:
            if binding:
                try: record.update(enrollment_binding(payload, current_mesh_user_id(), DEV_AGENT_REGISTRY, GATEWAY_SOCKETS))
                except ValueError as exc: return jsonify(ok=False, error=str(exc)), 409
            elif agent_id in DEV_AGENT_REGISTRY:
                return jsonify(ok=False, error="agent_id_unavailable"), 409
            DEV_AGENT_REGISTRY[agent_id] = record
        if binding and DEV_AGENT_REGISTRY[binding['control_center_gateway']].get('gateway_enrollment_restore_version') == 1:
            from mesh_gateway_receipts import issue_receipt
            gid = binding['control_center_gateway']
            receipt = issue_receipt(record, DEV_AGENT_REGISTRY[gid], device_credential_secret())
            saved, status = control_relay.dispatch(agent_id, 'identity.enrollment.save', {'receipt': receipt}, send_gateway_message, gid)
            if saved.get('ok') is not True or saved.get('result', {}).get('stored') is not True:
                with LIVE_LOCK:
                    if DEV_AGENT_REGISTRY.get(agent_id) is record:
                        DEV_AGENT_REGISTRY.pop(agent_id)
                return jsonify(ok=False, error='gateway_enrollment_persistence_failed'), 502
        return jsonify(ok=True, agent=public_agent(record)), 201

    @app.post("/api/agents/<agent_id>/pair-token")
    @require_session
    # noinspection DuplicatedCode
    def create_pair_token(agent_id: str):
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return jsonify(ok=False, error="agent_not_found"), 404
        if record.get("trust_state") != "verified":
            return jsonify(ok=False, error="verified_identity_required"), 403

        token = secrets.token_urlsafe(32)
        expires_at = unix_now() + PAIR_TOKEN_TTL_SECONDS

        with LIVE_LOCK:
            PAIRING_TOKENS[token] = {
                "agent_id": agent_id,
                "expires_at": expires_at,
                "used": False,
            }

        mesh_origin = mesh_public_origin()
        ws_base = websocket_origin_from_http(mesh_origin)
        ws_url = f"{ws_base}/ws/gateway/{agent_id}?token={token}"

        return jsonify(
            ok=True,
            agent_id=agent_id,
            token=token,
            expires_in=PAIR_TOKEN_TTL_SECONDS,
            websocket_url=ws_url,
            gateway_command=(
                f'python gateway/mesh_gateway.py --mesh "{mesh_public_origin()}" '
                f'--agent "{agent_id}" --token "{token}"'
            ),
        )

    @app.get("/api/agents/<agent_id>/events")
    @require_session
    def get_events(agent_id: str):
        if agent_id not in DEV_AGENT_REGISTRY:
            return jsonify(ok=False, error="agent_not_found"), 404
        with LIVE_LOCK:
            events = list(EVENT_BUFFERS.get(agent_id, []))
        return jsonify(ok=True, events=events)

    @app.get("/api/agents/<agent_id>/capability-provider")
    @require_session
    def agent_capability_provider(agent_id: str):
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return jsonify(ok=False, error="agent_not_found"), 404
        provider = record.get("capability_provider")
        if not provider:
            return jsonify(
                ok=False,
                error="capability_provider_not_reported",
                agent_id=agent_id,
                connected=record.get("transport") == "connected",
            ), 404
        return jsonify(
            ok=True,
            agent_id=agent_id,
            agent_name=record.get("name"),
            connected=record.get("transport") == "connected",
            capability_provider=provider,
        )

    @app.post("/api/agents/<agent_id>/heartbeat-request")
    @require_session
    # noinspection DuplicatedCode
    def request_heartbeat(agent_id: str):
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return jsonify(ok=False, error="agent_not_found"), 404

        with LIVE_LOCK:
            gateway = GATEWAY_SOCKETS.get(agent_id)

        if gateway is None:
            return jsonify(ok=False, error="gateway_not_connected"), 409

        try:
            gateway.send(json.dumps({
                "type": "heartbeat_request",
                "timestamp": utcnow(),
                "requested_by": session["mesh_user"]["id"],
            }))
        except (OSError, RuntimeError):
            return jsonify(ok=False, error="gateway_send_failed"), 502

        return jsonify(ok=True, requested=True)

    @app.post("/api/agents/<agent_id>/message")
    @require_session
    # noinspection DuplicatedCode
    def send_agent_message(agent_id: str):
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return jsonify(ok=False, error="agent_not_found"), 404

        if record.get("control_center_gateway"):
            from mesh_agent_management import linked_message
            return linked_message(record, current_mesh_user_id(), DEV_AGENT_REGISTRY, GATEWAY_SOCKETS, send_gateway_message)

        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text", "")).strip()
        if not text:
            return jsonify(ok=False, error="message_required"), 400

        if len(text) > 4000:
            return jsonify(ok=False, error="message_too_long"), 400

        request_id = secrets.token_urlsafe(10)

        append_event(agent_id, {
            "type": "user_message",
            "message": text,
            "payload": {
                "request_id": request_id,
                "sender": session["mesh_user"]["display_name"],
            },
        })

        ok, error = send_gateway_message(agent_id, {
            "type": "message_request",
            "request_id": request_id,
            "timestamp": utcnow(),
            "payload": {
                "text": text,
                "sender": session["mesh_user"]["display_name"],
                "room": "direct",
            },
        })

        if not ok:
            return jsonify(ok=False, error=error), 409 if error == "gateway_not_connected" else 502

        broadcast_to_clients(agent_id, {
            "type": "gateway_message",
            "agent_id": agent_id,
            "message": {
                "type": "user_message",
                "timestamp": utcnow(),
                "message": text,
                "payload": {
                    "request_id": request_id,
                    "sender": session["mesh_user"]["display_name"],
                },
            },
            "agent": public_agent(record),
        })

        return jsonify(ok=True, request_id=request_id)

    @app.post("/api/rooms/group/message")
    @require_session
    def send_group_message():
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text", "")).strip()
        requested_ids = payload.get("agent_ids") or []

        if not text:
            return jsonify(ok=False, error="message_required"), 400
        if len(text) > 4000:
            return jsonify(ok=False, error="message_too_long"), 400
        if not isinstance(requested_ids, list) or not requested_ids:
            return jsonify(ok=False, error="agent_ids_required"), 400

        request_id = secrets.token_urlsafe(10)
        results = []

        for agent_id in requested_ids:
            record = DEV_AGENT_REGISTRY.get(str(agent_id))
            allowed, _reason = ownership_can_access(record, current_mesh_user_id())
            if not record or not allowed:
                results.append({"agent_id": agent_id, "ok": False, "error": "agent_not_found"})
                continue

            append_event(str(agent_id), {
                "type": "group_message",
                "message": text,
                "payload": {
                    "request_id": request_id,
                    "sender": session["mesh_user"]["display_name"],
                },
            })

            ok, error = send_gateway_message(str(agent_id), {
                "type": "message_request",
                "request_id": request_id,
                "timestamp": utcnow(),
                "payload": {
                    "text": text,
                    "sender": session["mesh_user"]["display_name"],
                    "room": "group",
                    "participants": requested_ids,
                },
            })

            results.append({"agent_id": agent_id, "ok": ok, "error": error})

            if ok:
                broadcast_to_clients(str(agent_id), {
                    "type": "gateway_message",
                    "agent_id": str(agent_id),
                    "message": {
                        "type": "group_message",
                        "timestamp": utcnow(),
                        "message": text,
                        "payload": {
                            "request_id": request_id,
                            "sender": session["mesh_user"]["display_name"],
                        },
                    },
                    "agent": public_agent(record),
                })

        delivered = sum(1 for r in results if r["ok"])
        return jsonify(
            ok=delivered > 0,
            request_id=request_id,
            delivered=delivered,
            attempted=len(results),
            results=results,
        ), 200 if delivered > 0 else 409

    @app.get("/api/agents/<agent_id>/actions")
    @require_session
    def list_actions(agent_id: str):
        if agent_id not in DEV_AGENT_REGISTRY:
            return jsonify(ok=False, error="agent_not_found"), 404
        items = [a for a in ACTION_REQUESTS.values() if a["agent_id"] == agent_id and ownership_can_access(DEV_AGENT_REGISTRY.get(a["agent_id"]), current_mesh_user_id())[0]]
        items.sort(key=lambda x: x["created_at"], reverse=True)
        return jsonify(ok=True, actions=items[:50])

    @app.post("/api/agents/<agent_id>/actions/request")
    @require_session
    def request_agent_action(agent_id: str):
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return jsonify(ok=False, error="agent_not_found"), 404

        payload = request.get_json(silent=True) or {}
        action_type = str(payload.get("action_type", "")).strip()
        action_payload = payload.get("payload") or {}

        allowed_actions = {"request_status", "request_task_snapshot", "request_terminal_snapshot"}
        if action_type not in allowed_actions:
            return jsonify(ok=False, error="action_not_allowed"), 403

        action = issue_action_request(agent_id, action_type, action_payload)
        return jsonify(ok=True, action=action), 201

    @app.post("/api/actions/<action_id>/approve")
    @require_session
    def approve_action(action_id: str):
        action = ACTION_REQUESTS.get(action_id)
        if not action:
            return jsonify(ok=False, error="action_not_found"), 404
        if not ownership_can_access(DEV_AGENT_REGISTRY.get(action["agent_id"]), current_mesh_user_id())[0]:
            return jsonify(ok=False, error="action_not_found"), 404
        if action["status"] != "pending":
            return jsonify(ok=False, error="action_not_pending"), 409

        action["status"] = "approved"
        action["approved_at"] = utcnow()

        ok, error = send_gateway_message(action["agent_id"], {
            "type": "approved_action",
            "timestamp": utcnow(),
            "payload": {
                "action_id": action["id"],
                "action_type": action["action_type"],
                "payload": action["payload"],
            },
        })

        if not ok:
            action["status"] = "approved_waiting_for_gateway"
            return jsonify(ok=False, error=error, action=action), 409

        action["status"] = "dispatched"
        action["dispatched_at"] = utcnow()
        append_event(action["agent_id"], {
            "type": "approval",
            "message": f"Approved action: {action['action_type']}",
            "payload": {"action_id": action["id"]},
        })
        return jsonify(ok=True, action=action)

    @app.post("/api/actions/<action_id>/reject")
    @require_session
    def reject_action(action_id: str):
        action = ACTION_REQUESTS.get(action_id)
        if not action:
            return jsonify(ok=False, error="action_not_found"), 404
        if not ownership_can_access(DEV_AGENT_REGISTRY.get(action["agent_id"]), current_mesh_user_id())[0]:
            return jsonify(ok=False, error="action_not_found"), 404
        if action["status"] != "pending":
            return jsonify(ok=False, error="action_not_pending"), 409

        action["status"] = "rejected"
        action["completed_at"] = utcnow()
        append_event(action["agent_id"], {
            "type": "approval",
            "message": f"Rejected action: {action['action_type']}",
            "payload": {"action_id": action["id"]},
        })
        return jsonify(ok=True, action=action)

    @app.post("/api/agents/<agent_id>/files/send")
    @require_session
    def send_file_to_agent(agent_id: str):
        cleanup_expired_transfer_state()

        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return jsonify(ok=False, error="agent_not_found"), 404
        if record.get("transport") != "connected":
            return jsonify(ok=False, error="gateway_not_connected"), 409

        uploaded = request.files.get("file")
        if uploaded is None or not uploaded.filename:
            return jsonify(ok=False, error="file_required"), 400

        filename = sanitize_filename(uploaded.filename)
        classification = classify_file(filename)
        sensitive_approved = request.form.get("sensitive_approved", "false").lower() == "true"

        if classification["sensitive"] and not sensitive_approved:
            return jsonify(ok=False, error="sensitive_file_requires_approval",
                           extension=classification["extension"]), 428
        if not classification["allowed"] and not classification["sensitive"]:
            return jsonify(ok=False, error="file_type_not_allowed",
                           extension=classification["extension"]), 415

        transfer_id = secrets.token_urlsafe(10)
        hasher = hashlib.sha256()
        total = 0
        first_bytes = bytearray()
        temp_path = transfer_temp_dir() / f"upload-{transfer_id}.part"

        try:
            with temp_path.open("wb") as handle:
                while True:
                    chunk = uploaded.stream.read(MAX_WS_FILE_CHUNK)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_FILE_BYTES:
                        return jsonify(ok=False, error="file_too_large",
                                       max_bytes=MAX_FILE_BYTES), 413
                    if session_file_total() + total > MAX_SESSION_FILE_BYTES:
                        return jsonify(ok=False, error="session_file_limit_exceeded",
                                       max_bytes=MAX_SESSION_FILE_BYTES), 413
                    if len(first_bytes) < 64:
                        first_bytes.extend(chunk[: 64 - len(first_bytes)])
                    hasher.update(chunk)
                    handle.write(chunk)

            if total <= 0:
                return jsonify(ok=False, error="empty_file"), 400

            mime = uploaded.mimetype or "application/octet-stream"
            mime_ok, mime_details = validate_mime_claim(filename, mime, bytes(first_bytes))
            if not mime_ok:
                return jsonify(ok=False, error="mime_content_mismatch",
                               details=mime_details), 415

            digest = hasher.hexdigest()
            ACTIVE_UPLOAD_TRANSFERS[transfer_id] = {
                "agent_id": agent_id,
                "filename": filename,
                "size": total,
                "started_epoch": time.time(),
            }

            ok, error = send_gateway_message(agent_id, {
                "type": "file_transfer_start",
                "timestamp": utcnow(),
                "payload": {
                    "transfer_id": transfer_id,
                    "filename": filename,
                    "mime": mime,
                    "size": total,
                    "sha256": digest,
                    "sensitive": classification["sensitive"],
                },
            })
            if not ok:
                return jsonify(ok=False, error=error), 502

            sent = 0
            with temp_path.open("rb") as handle:
                index = 0
                while True:
                    chunk = handle.read(MAX_WS_FILE_CHUNK)
                    if not chunk:
                        break
                    ok, error = send_gateway_message(agent_id, {
                        "type": "file_transfer_chunk",
                        "timestamp": utcnow(),
                        "payload": {
                            "transfer_id": transfer_id,
                            "index": index,
                            "content_base64": base64.b64encode(chunk).decode("ascii"),
                        },
                    })
                    if not ok:
                        send_gateway_message(agent_id, {
                            "type": "file_transfer_cancel",
                            "timestamp": utcnow(),
                            "payload": {
                                "transfer_id": transfer_id,
                                "reason": "relay_interrupted",
                            },
                        })
                        return jsonify(ok=False, error=error), 502
                    sent += len(chunk)
                    index += 1

            ok, error = send_gateway_message(agent_id, {
                "type": "file_transfer_end",
                "timestamp": utcnow(),
                "payload": {
                    "transfer_id": transfer_id,
                    "size": sent,
                    "sha256": digest,
                },
            })
            if not ok:
                return jsonify(ok=False, error=error), 502

            add_session_file_bytes(total)
            append_event(agent_id, {
                "type": "file_transfer",
                "message": f"Sent file to agent: {filename}",
                "payload": {
                    "transfer_id": transfer_id,
                    "size": total,
                    "sha256": digest,
                    "severity": "info",
                },
            })
            return jsonify(ok=True, transfer_id=transfer_id, filename=filename,
                           size=total, sha256=digest)
        finally:
            ACTIVE_UPLOAD_TRANSFERS.pop(transfer_id, None)
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    @app.get("/api/files/offers")
    @require_session
    def list_file_offers():
        agent_id = request.args.get("agent_id")
        items = [
            f for f in FILE_OFFERS.values()
            if ownership_can_access(DEV_AGENT_REGISTRY.get(f["agent_id"]), current_mesh_user_id())[0]
        ]
        if agent_id:
            items = [f for f in items if f["agent_id"] == agent_id]
        items.sort(key=lambda x: x["created_at"], reverse=True)
        safe_items = [{k: v for k, v in item.items() if k != "content_base64"} for item in items]
        return jsonify(ok=True, files=safe_items[:50])

    @app.get("/api/files/<offer_id>/download")
    @require_session
    def download_file_offer(offer_id: str):
        cleanup_expired_transfer_state()
        record = FILE_OFFERS.get(offer_id)
        if not record or record.get("status") != "ready":
            return jsonify(ok=False, error="file_offer_not_ready"), 404
        if not ownership_can_access(DEV_AGENT_REGISTRY.get(record["agent_id"]), current_mesh_user_id())[0]:
            return jsonify(ok=False, error="file_offer_not_ready"), 404

        temp_path = Path(record["temp_path"])
        if not temp_path.exists():
            FILE_OFFERS.pop(offer_id, None)
            return jsonify(ok=False, error="file_offer_expired"), 410

        response = send_file(
            temp_path,
            mimetype=record.get("mime") or "application/octet-stream",
            as_attachment=True,
            download_name=record["filename"],
            conditional=False,
            max_age=0,
        )
        response.headers["Cache-Control"] = "no-store"
        response.call_on_close(lambda: _cleanup_download_offer(offer_id))
        return response


    def _cleanup_download_offer(offer_id: str) -> None:
        record = FILE_OFFERS.pop(offer_id, None)
        if not record:
            return
        try:
            Path(record["temp_path"]).unlink(missing_ok=True)
        except OSError:
            pass

    @app.post("/api/agents/<agent_id>/files/request-demo")
    @require_session
    def request_demo_file(agent_id: str):
        if agent_id not in DEV_AGENT_REGISTRY:
            return jsonify(ok=False, error="agent_not_found"), 404
        ok, error = send_gateway_message(agent_id, {
            "type": "demo_file_offer_request",
            "timestamp": utcnow(),
        })
        if not ok:
            return jsonify(ok=False, error=error), 409
        return jsonify(ok=True, requested=True)

    @app.post("/api/agents/<agent_id>/verify")
    @require_session
    def reverify_agent(agent_id: str):
        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            return jsonify(ok=False, error="agent_not_found"), 404

        verification = verify_runtime_agent_identity(
            {
                "agent_id": agent_id,
                "codeseal_evidence": record.get("codeseal_evidence"),
            },
            record["name"],
            record["public_key"],
            record.get("codeseal_key", ""),
        )
        record.update(
            trust_state=verification["state"],
            trust_valid=verification["valid"],
            trust_reason=verification["reason"],
            verified_at=utcnow(),
        )
        return jsonify(ok=True, agent=public_agent(record))

    @app.delete("/api/agents/<agent_id>")
    @require_session
    def remove_agent(agent_id: str):
        if agent_id not in DEV_AGENT_REGISTRY:
            return jsonify(ok=False, error="agent_not_found"), 404
        with LIVE_LOCK:
            gateway = GATEWAY_SOCKETS.pop(agent_id, None)
            CLIENT_SOCKETS.pop(agent_id, None)
            EVENT_BUFFERS.pop(agent_id, None)
        try:
            if gateway:
                gateway.close()
        except (OSError, RuntimeError):
            pass
        removed = DEV_AGENT_REGISTRY.pop(agent_id)
        return jsonify(ok=True, removed={"id": removed["id"], "name": removed["name"]})

    @sock.route("/ws/gateway/<agent_id>")
    def gateway_socket(ws, agent_id: str):
        token = request.args.get("token", "")
        credential = request.args.get("credential", "")
        record = DEV_AGENT_REGISTRY.get(agent_id)

        if not record or record.get("trust_state") != "verified":
            ws.close(reason="untrusted_agent")
            return

        auth_mode = None
        device_payload = None

        with LIVE_LOCK:
            if credential:
                valid_device, reason, device_payload = validate_device_credential(
                    agent_id, credential
                )
                if not valid_device:
                    ws.close(reason=reason)
                    return
                record_owner = str(record.get("owner_id") or "").strip()
                credential_owner = str((device_payload or {}).get("owner_id") or "").strip()
                if record_owner and credential_owner != record_owner:
                    ws.close(reason="agent_owner_mismatch")
                    return
                auth_mode = "device_credential"
            else:
                token_record = PAIRING_TOKENS.get(token)
                if (
                    not token_record
                    or token_record["agent_id"] != agent_id
                    or token_record["used"]
                    or token_record["expires_at"] < unix_now()
                ):
                    ws.close(reason="invalid_pairing_token")
                    return
                token_record["used"] = True
                auth_mode = "pairing_token"

            GATEWAY_SOCKETS[agent_id] = ws
            record["transport"] = "connected"
            record["state"] = "online"
            record["last_heartbeat"] = utcnow()

        append_event(agent_id, {
            "type": "gateway",
            "message": "Agent gateway connected",
            "payload": {"transport": "websocket"},
        })
        broadcast_to_clients(agent_id, {
            "type": "gateway_connected",
            "agent_id": agent_id,
            "agent": public_agent(record),
        })

        try:
            ws.send(json.dumps({
                "type": "paired",
                "build_id": app.config["BUILD_ID"],
                "agent_id": agent_id,
                "timestamp": utcnow(),
                "auth_mode": auth_mode,
                "device_id": (device_payload or {}).get("device_id"),
                "integration_mode": "plug-and-monitor",
            }))

            while True:
                raw = ws.receive()
                if raw is None:
                    break
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                update_from_gateway(agent_id, message)
        finally:
            with LIVE_LOCK:
                if GATEWAY_SOCKETS.get(agent_id) is ws:
                    GATEWAY_SOCKETS.pop(agent_id, None)
                record["transport"] = "not-connected"
                record["state"] = "offline"
            append_event(agent_id, {
                "type": "gateway",
                "message": "Agent gateway disconnected",
            })
            broadcast_to_clients(agent_id, {
                "type": "gateway_disconnected",
                "agent_id": agent_id,
                "agent": public_agent(record),
            })

    @sock.route("/ws/client/<agent_id>")
    def client_socket(ws, agent_id: str):
        if not session.get("mesh_user"):
            ws.close(reason="authentication_required")
            return

        record = DEV_AGENT_REGISTRY.get(agent_id)
        if not record:
            ws.close(reason="agent_not_found")
            return
        allowed, _reason = ownership_can_access(record, current_mesh_user_id())
        if not allowed:
            ws.close(reason="agent_not_found")
            return

        # Browser streams must lose private delivery when canonical account state
        # changes, including connections opened before the lock.
        from mesh_account_security import AccountBoundSocket
        ws = AccountBoundSocket(ws, app, session.get("mesh_user") or {})
        with LIVE_LOCK:
            CLIENT_SOCKETS.setdefault(agent_id, []).append(ws)
            recent = list(EVENT_BUFFERS.get(agent_id, []))

        try:
            ws.send(json.dumps({
                "type": "snapshot",
                "agent_id": agent_id,
                "agent": public_agent(record),
                "events": recent,
            }))

            # Browser doesn't need to send commands through this socket in Phase 3.
            # Keep the connection open and accept lightweight ping messages.
            while True:
                raw = ws.receive()
                if raw is None:
                    break
                try:
                    incoming = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if incoming.get("type") == "ping":
                    ws.send(json.dumps({"type": "pong", "timestamp": utcnow()}))
        finally:
            with LIVE_LOCK:
                clients = CLIENT_SOCKETS.get(agent_id, [])
                CLIENT_SOCKETS[agent_id] = [client for client in clients if client is not ws]

    @app.get("/manifest.webmanifest")
    def manifest():
        response = send_from_directory(
            app.static_folder,
            "manifest.webmanifest",
            mimetype="application/manifest+json",
        )
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/sw.js")
    def service_worker():
        response = send_from_directory(
            app.static_folder,
            "sw.js",
            mimetype="application/javascript",
        )
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    from mesh_onboarding import register_onboarding_routes
    register_onboarding_routes(app, require_session, current_mesh_user_id,
        DEV_AGENT_REGISTRY, mesh_public_origin, verify_runtime_agent_identity,
        create_agent_enrollment_message, utcnow, fingerprint_for)

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="127.0.0.1" if os.environ.get("MESH_LOCAL_CONTROL_CENTER")=="1" else "0.0.0.0", port=port, debug=debug, threaded=True)
