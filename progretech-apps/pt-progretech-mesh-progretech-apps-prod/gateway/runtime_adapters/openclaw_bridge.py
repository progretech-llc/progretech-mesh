from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from .base import RuntimeAdapter, RuntimeResponse


class OpenClawBridgeRuntimeAdapter(RuntimeAdapter):
    """Use the local OpenClaw Mesh plugin bridge instead of spawning agent exec."""

    name = "openclaw_bridge"

    def __init__(self) -> None:
        self.url = os.environ.get(
            "MESH_OPENCLAW_BRIDGE_URL",
            "http://127.0.0.1:18789/plugins/progretech-mesh/message",
        ).strip()
        self.token = os.environ.get("PROGRETECH_MESH_LOCAL_TOKEN", "").strip()
        self.timeout = int(os.environ.get("MESH_OPENCLAW_BRIDGE_TIMEOUT", "240"))

    def health(self) -> dict[str, Any]:
        return {
            "ok": self.url.startswith("http://127.0.0.1:") or self.url.startswith("http://localhost:"),
            "adapter": self.name,
            "bridge_url": self.url,
            "loopback_only": True,
            "timeout": self.timeout,
        }

    def send_message(
        self,
        *,
        agent_id: str,
        text: str,
        room: str,
        sender: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> RuntimeResponse:
        if attachments:
            return RuntimeResponse(
                ok=False,
                text="",
                metadata={"adapter": self.name},
                error="OpenClaw bridge attachment handoff is not enabled yet; file staging remains separate.",
            )

        payload = json.dumps({
            "agent_id": agent_id,
            "text": text,
            "room": room,
            "sender": sender,
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-ProgreTech-Mesh-Local-Token"] = self.token

        request = urllib.request.Request(self.url, data=payload, headers=headers, method="POST")
        started = time.time()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            return RuntimeResponse(
                ok=False,
                text="",
                metadata={
                    "adapter": self.name,
                    "duration_seconds": round(time.time() - started, 2),
                    "http_status": exc.code,
                },
                error=f"OpenClaw Mesh bridge HTTP {exc.code}: {detail[:500]}",
            )
        except Exception as exc:
            return RuntimeResponse(
                ok=False,
                text="",
                metadata={
                    "adapter": self.name,
                    "duration_seconds": round(time.time() - started, 2),
                },
                error=f"OpenClaw Mesh bridge failed: {exc}",
            )

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return RuntimeResponse(
                ok=False,
                text="",
                metadata={"adapter": self.name},
                error="OpenClaw Mesh bridge returned invalid JSON",
            )

        metadata = {
            "adapter": self.name,
            "duration_seconds": round(time.time() - started, 2),
            "session_id": parsed.get("session_id"),
            "session_key": parsed.get("session_key"),
            "run_id": parsed.get("run_id"),
        }
        if not parsed.get("ok"):
            return RuntimeResponse(
                ok=False,
                text=str(parsed.get("text") or ""),
                metadata=metadata,
                error=str(parsed.get("error") or "OpenClaw Mesh bridge error"),
            )
        return RuntimeResponse(
            ok=True,
            text=str(parsed.get("text") or ""),
            metadata=metadata,
        )
