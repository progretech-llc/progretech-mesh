from __future__ import annotations

import argparse
import json
import os
import base64
import hashlib
from pathlib import Path
import platform
import socket
import sys
import time
import threading
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import psutil
import websocket

# Allow running this file directly while still importing sibling package modules.
GATEWAY_DIR = Path(__file__).resolve().parent
if str(GATEWAY_DIR.parent) not in sys.path:
    sys.path.insert(0, str(GATEWAY_DIR.parent))

from gateway.runtime_adapters import build_runtime_adapter
from gateway.observation_adapters import build_observation_adapter
from gateway.identity import build_identity_verifier


GATEWAY_TRANSFER_TTL_SECONDS = int(os.environ.get("MESH_TRANSFER_TTL_SECONDS", "900"))

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def websocket_url(
    mesh_url: str,
    agent_id: str,
    token: str = "",
    credential: str = "",
) -> str:
    parsed = urlparse(mesh_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    base = f"{scheme}://{parsed.netloc}"
    if credential:
        auth_query = f"credential={quote(credential)}"
    else:
        auth_query = f"token={quote(token)}"
    return f"{base}/ws/gateway/{quote(agent_id)}?{auth_query}"


def telemetry() -> dict:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(os.path.abspath(os.sep))
    return {
        "hostname": socket.gethostname(),
        "platform": platform.system(),
        "platform_release": platform.release(),
        "python": platform.python_version(),
        "cpu_percent": psutil.cpu_percent(interval=None),
        "memory_percent": memory.percent,
        "memory_used_gb": round(memory.used / (1024 ** 3), 2),
        "memory_total_gb": round(memory.total / (1024 ** 3), 2),
        "disk_percent": disk.percent,
    }


def heartbeat_payload(agent_id: str, started: float, state: str = "online") -> dict:
    elapsed = max(0, int(time.time() - started))
    hours, rem = divmod(elapsed, 3600)
    minutes, seconds = divmod(rem, 60)

    return {
        "type": "heartbeat",
        "timestamp": utcnow(),
        "payload": {
            "state": state,
            "task": "Mesh gateway connected",
            "phase": "Live heartbeat transport",
            "progress": 100,
            "model": "Local agent runtime",
            "runtime": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            "message": f"{agent_id} heartbeat received",
            "telemetry": telemetry(),
            "runtime_adapter": os.environ.get("MESH_RUNTIME_ADAPTER", "demo"),
            "observation_adapter": os.environ.get("MESH_OBSERVATION_ADAPTER", "none"),
            "identity_mode": os.environ.get("MESH_AGENT_IDENTITY_MODE", "development"),
        },
    }




def safe_stage_directory() -> Path:
    path = Path(os.environ.get("MESH_GATEWAY_STAGE_DIR", ".mesh-staging")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(name: str) -> str:
    name = os.path.basename(str(name or "").strip())
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "._- ()")
    return safe[:180] or "mesh-file"


def stage_received_file(payload: dict) -> dict:
    filename = safe_filename(payload.get("filename", "mesh-file"))
    encoded = payload.get("content_base64", "")
    raw = base64.b64decode(encoded)
    expected_size = int(payload.get("size", 0) or 0)
    expected_hash = str(payload.get("sha256", ""))

    if expected_size and len(raw) != expected_size:
        raise ValueError("received file size mismatch")

    actual_hash = hashlib.sha256(raw).hexdigest()
    if expected_hash and actual_hash.lower() != expected_hash.lower():
        raise ValueError("received file checksum mismatch")

    target = safe_stage_directory() / filename
    target.write_bytes(raw)

    return {
        "filename": filename,
        "path": str(target),
        "size": len(raw),
        "sha256": actual_hash,
    }


def make_demo_output_file(agent_id: str) -> dict:
    content = (
        f"ProgreTech Mesh demo artifact\n"
        f"Agent: {agent_id}\n"
        f"Generated: {utcnow()}\n"
        f"This file proves agent-to-user transfer over the Mesh gateway.\n"
    ).encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    return {
        "filename": f"{agent_id}_mesh_demo_output.txt",
        "mime": "text/plain",
        "size": len(content),
        "sha256": digest,
        "content_base64": base64.b64encode(content).decode("ascii"),
    }


def terminal_snapshot() -> list[str]:
    return [
        f"host={socket.gethostname()}",
        f"platform={platform.system()} {platform.release()}",
        f"python={platform.python_version()}",
        "mode=read-only-snapshot",
        "shell=disabled",
    ]




def run_passive_observer(ws, stop_event, adapter, agent_id: str, interval: float = 1.0):
    """
    Poll the read-only observation adapter and mirror normalized activity to Mesh.

    This loop must never control the agent runtime.
    """
    seen_health_warning = False

    while not stop_event.is_set():
        try:
            health = adapter.health()
            if not health.get("ok", False) and not seen_health_warning:
                ws.send(json.dumps({
                    "type": "event",
                    "timestamp": utcnow(),
                    "message": "Passive observation source is not currently available",
                    "payload": {
                        "severity": "warn",
                        "event_class": "observation",
                        "observer": health,
                    },
                }))
                seen_health_warning = True

            for event in adapter.poll():
                normalized = event.as_dict()
                ws.send(json.dumps({
                    "type": "agent_activity",
                    "timestamp": utcnow(),
                    "message": normalized.get("summary") or "Agent activity",
                    "payload": {
                        **normalized,
                        "agent_id": agent_id,
                        "observer": adapter.name,
                        "read_only": True,
                    },
                }))
        except Exception as exc:
            try:
                ws.send(json.dumps({
                    "type": "event",
                    "timestamp": utcnow(),
                    "message": f"Passive observation warning: {exc}",
                    "payload": {
                        "severity": "warn",
                        "event_class": "observation",
                    },
                }))
            except Exception:
                pass

        stop_event.wait(interval)



def main() -> int:
    parser = argparse.ArgumentParser(
        description="ProgreTech Mesh local agent gateway."
    )
    parser.add_argument("--mesh", required=True, help="Mesh base URL, e.g. http://127.0.0.1:8080")
    parser.add_argument("--agent", required=True, help="Mesh agent ID")
    parser.add_argument("--token", default="", help="One-time pairing token from Mesh")
    parser.add_argument("--credential", default="", help="Signed reconnect credential from Mesh")
    parser.add_argument("--reconnect-seconds", type=int, default=5)
    parser.add_argument("--heartbeat-seconds", type=int, default=5)
    args = parser.parse_args()

    if not args.token and not args.credential:
        parser.error("one of --token or --credential is required")
    ws_url = websocket_url(args.mesh, args.agent, args.token, args.credential)
    started = time.time()
    pending_transfers = {}
    runtime = build_runtime_adapter()
    runtime_health = runtime.health()

    observer = build_observation_adapter()
    observer_health = observer.health()
    observer_stop = threading.Event()
    identity_verifier = build_identity_verifier()

    print(f"[mesh-gateway] runtime adapter={runtime_health.get('adapter')}")
    print(f"[mesh-gateway] passive observer={observer_health.get('adapter')}")
    if not runtime_health.get("ok", False):
        print(f"[mesh-gateway] runtime warning: {runtime_health}")
    if not observer_health.get("ok", False):
        print(f"[mesh-gateway] observation warning: {observer_health}")

    print(f"[mesh-gateway] agent={args.agent}")
    print(f"[mesh-gateway] connecting to {ws_url.split('?', 1)[0]}")

    ws = websocket.create_connection(ws_url, timeout=15)
    try:
        paired = json.loads(ws.recv())
        if paired.get("type") != "paired":
            raise RuntimeError(f"Unexpected pairing response: {paired}")

        print("[mesh-gateway] paired")
        ws.settimeout(1.0)
        next_heartbeat = 0.0

        while True:
            now = time.time()

            if now >= next_heartbeat:
                ws.send(json.dumps(heartbeat_payload(args.agent, started)))
                next_heartbeat = now + max(2, args.heartbeat_seconds)

            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue

            if not raw:
                break

            message = json.loads(raw)
            now_epoch = time.time()
            expired_ids = [
                transfer_id for transfer_id, transfer in pending_transfers.items()
                if now_epoch - float(transfer.get("started", now_epoch)) > GATEWAY_TRANSFER_TTL_SECONDS
            ]
            for expired_id in expired_ids:
                expired = pending_transfers.pop(expired_id, None)
                if expired:
                    expired["target"].unlink(missing_ok=True)

            if message.get("type") == "heartbeat_request":
                print("[mesh-gateway] heartbeat requested by Mesh")
                ws.send(json.dumps(heartbeat_payload(args.agent, started)))
            elif message.get("type") == "message_request":
                payload = message.get("payload", {})
                text = str(payload.get("text", "")).strip()
                room = str(payload.get("room", "direct"))
                sender = str(payload.get("sender", "Mesh user"))
                request_id = message.get("request_id")
                attachments = payload.get("attachments") or []

                print(
                    f"[mesh-gateway] message_request room={room} "
                    f"request_id={request_id} adapter={runtime.name}"
                )

                ws.send(json.dumps({
                    "type": "event",
                    "timestamp": utcnow(),
                    "message": f"{args.agent} is processing the Mesh message",
                    "payload": {
                        "severity": "info",
                        "event_class": "runtime",
                        "request_id": request_id,
                        "adapter": runtime.name,
                    },
                }))

                result = runtime.send_message(
                    agent_id=args.agent,
                    text=text,
                    room=room,
                    sender=sender,
                    attachments=attachments,
                )

                if result.ok:
                    ws.send(json.dumps({
                        "type": "message_response",
                        "timestamp": utcnow(),
                        "message": result.text,
                        "payload": {
                            "request_id": request_id,
                            "room": room,
                            "agent_id": args.agent,
                            "runtime": result.metadata,
                        },
                    }))
                else:
                    ws.send(json.dumps({
                        "type": "message_response",
                        "timestamp": utcnow(),
                        "message": (
                            f"{args.agent.capitalize()} could not complete the request "
                            f"through the configured runtime."
                        ),
                        "payload": {
                            "request_id": request_id,
                            "room": room,
                            "agent_id": args.agent,
                            "runtime": result.metadata,
                            "runtime_error": result.error,
                            "severity": "error",
                        },
                    }))
                    ws.send(json.dumps({
                        "type": "event",
                        "timestamp": utcnow(),
                        "message": f"Runtime error: {result.error}",
                        "payload": {
                            "severity": "error",
                            "event_class": "runtime",
                            "request_id": request_id,
                            "adapter": runtime.name,
                        },
                    }))
            elif message.get("type") == "file_transfer_start":
                payload = message.get("payload", {})
                transfer_id = str(payload.get("transfer_id", ""))
                filename = safe_filename(payload.get("filename", "mesh-file"))
                target = safe_stage_directory() / f".{transfer_id}.part"
                target.write_bytes(b"")
                declared_size = int(payload.get("size", 0) or 0)
                max_file_bytes = int(os.environ.get("MESH_MAX_FILE_BYTES", str(20 * 1024 * 1024)))
                if len(pending_transfers) >= int(os.environ.get("MESH_MAX_ACTIVE_TRANSFERS_PER_AGENT", "3")):
                    ws.send(json.dumps({
                        "type": "event",
                        "timestamp": utcnow(),
                        "message": "File transfer rejected: too many active transfers",
                        "payload": {"severity": "error", "event_class": "file"},
                    }))
                    continue
                if declared_size <= 0 or declared_size > max_file_bytes:
                    ws.send(json.dumps({
                        "type": "event",
                        "timestamp": utcnow(),
                        "message": "File transfer rejected: invalid declared size",
                        "payload": {"severity": "error", "event_class": "file"},
                    }))
                    continue

                pending_transfers[transfer_id] = {
                    "filename": filename,
                    "target": target,
                    "final_path": safe_stage_directory() / filename,
                    "size": declared_size,
                    "sha256": str(payload.get("sha256", "")),
                    "received": 0,
                    "hasher": hashlib.sha256(),
                    "next_index": 0,
                    "started": time.time(),
                }
            elif message.get("type") == "file_transfer_chunk":
                payload = message.get("payload", {})
                transfer_id = str(payload.get("transfer_id", ""))
                transfer = pending_transfers.get(transfer_id)
                if transfer:
                    try:
                        index = int(payload.get("index", 0) or 0)
                        if index != transfer["next_index"]:
                            raise ValueError("chunk_sequence_mismatch")
                        chunk = base64.b64decode(payload.get("content_base64", ""), validate=True)
                        if len(chunk) > 256 * 1024:
                            raise ValueError("chunk_too_large")
                        if transfer["received"] + len(chunk) > transfer["size"]:
                            raise ValueError("transfer_overflow")
                        with transfer["target"].open("ab") as handle:
                            handle.write(chunk)
                        transfer["hasher"].update(chunk)
                        transfer["received"] += len(chunk)
                        transfer["next_index"] += 1
                    except Exception as exc:
                        transfer["target"].unlink(missing_ok=True)
                        pending_transfers.pop(transfer_id, None)
                        ws.send(json.dumps({
                            "type": "event",
                            "timestamp": utcnow(),
                            "message": f"File transfer failed: {exc}",
                            "payload": {"severity": "error", "event_class": "file"},
                        }))
            elif message.get("type") == "file_transfer_cancel":
                payload = message.get("payload", {})
                transfer_id = str(payload.get("transfer_id", ""))
                transfer = pending_transfers.pop(transfer_id, None)
                if transfer:
                    transfer["target"].unlink(missing_ok=True)
                    ws.send(json.dumps({
                        "type": "event",
                        "timestamp": utcnow(),
                        "message": f"File transfer cancelled: {transfer['filename']}",
                        "payload": {"severity": "warn", "event_class": "file"},
                    }))
            elif message.get("type") == "file_transfer_end":
                payload = message.get("payload", {})
                transfer_id = str(payload.get("transfer_id", ""))
                transfer = pending_transfers.pop(transfer_id, None)
                if transfer:
                    try:
                        actual_hash = transfer["hasher"].hexdigest()
                        if transfer["received"] != transfer["size"]:
                            raise ValueError("received file size mismatch")
                        if transfer["sha256"] and actual_hash.lower() != transfer["sha256"].lower():
                            raise ValueError("received file checksum mismatch")
                        transfer["target"].replace(transfer["final_path"])
                        ws.send(json.dumps({
                            "type": "event",
                            "timestamp": utcnow(),
                            "message": f"File received and staged locally: {transfer['filename']}",
                            "payload": {
                                "severity": "info",
                                "event_class": "file",
                                "filename": transfer["filename"],
                                "path": str(transfer["final_path"]),
                                "size": transfer["received"],
                                "sha256": actual_hash,
                            },
                        }))
                    except Exception as exc:
                        try:
                            transfer["target"].unlink(missing_ok=True)
                        except Exception:
                            pass
                        ws.send(json.dumps({
                            "type": "event",
                            "timestamp": utcnow(),
                            "message": f"File transfer failed: {exc}",
                            "payload": {
                                "severity": "error",
                                "event_class": "file",
                            },
                        }))
            elif message.get("type") == "approved_action":
                payload = message.get("payload", {})
                action_id = payload.get("action_id")
                action_type = payload.get("action_type")
                if action_type == "request_terminal_snapshot":
                    snapshot = terminal_snapshot()
                    ws.send(json.dumps({
                        "type": "terminal",
                        "timestamp": utcnow(),
                        "message": "Read-only terminal snapshot",
                        "payload": {
                            "action_id": action_id,
                            "lines": snapshot,
                            "severity": "info",
                        },
                    }))
                    ws.send(json.dumps({
                        "type": "action_result",
                        "timestamp": utcnow(),
                        "message": "Terminal snapshot completed",
                        "payload": {
                            "action_id": action_id,
                            "status": "completed",
                        },
                    }))
                elif action_type == "request_task_snapshot":
                    ws.send(json.dumps({
                        "type": "event",
                        "timestamp": utcnow(),
                        "message": "Task snapshot: gateway connected and responsive",
                        "payload": {
                            "action_id": action_id,
                            "severity": "info",
                            "event_class": "task",
                        },
                    }))
                    ws.send(json.dumps({
                        "type": "action_result",
                        "timestamp": utcnow(),
                        "message": "Task snapshot completed",
                        "payload": {
                            "action_id": action_id,
                            "status": "completed",
                        },
                    }))
                elif action_type == "request_status":
                    ws.send(json.dumps({
                        "type": "event",
                        "timestamp": utcnow(),
                        "message": "Status snapshot complete",
                        "payload": {
                            "action_id": action_id,
                            "severity": "info",
                            "event_class": "status",
                            "telemetry": telemetry(),
                        },
                    }))
                    ws.send(json.dumps({
                        "type": "action_result",
                        "timestamp": utcnow(),
                        "message": "Status request completed",
                        "payload": {
                            "action_id": action_id,
                            "status": "completed",
                        },
                    }))
            elif message.get("type") == "demo_file_offer_request":
                artifact = make_demo_output_file(args.agent)
                offer_id = f"demo-{int(time.time())}"
                ws.send(json.dumps({
                    "type": "file_offer_start",
                    "timestamp": utcnow(),
                    "payload": {
                        "offer_id": offer_id,
                        "filename": artifact["filename"],
                        "mime": artifact["mime"],
                        "size": artifact["size"],
                        "sha256": artifact["sha256"],
                    },
                }))
                raw = base64.b64decode(artifact["content_base64"])
                for index in range(0, len(raw), 256 * 1024):
                    chunk = raw[index:index + 256 * 1024]
                    ws.send(json.dumps({
                        "type": "file_offer_chunk",
                        "timestamp": utcnow(),
                        "payload": {
                            "offer_id": offer_id,
                            "content_base64": base64.b64encode(chunk).decode("ascii"),
                        },
                    }))
                ws.send(json.dumps({
                    "type": "file_offer_end",
                    "timestamp": utcnow(),
                    "payload": {
                        "offer_id": offer_id,
                    },
                }))
            elif message.get("type") == "ping":
                ws.send(json.dumps({"type": "pong", "timestamp": utcnow()}))

    except KeyboardInterrupt:
        print("\n[mesh-gateway] stopping")
    finally:
        try:
            ws.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
