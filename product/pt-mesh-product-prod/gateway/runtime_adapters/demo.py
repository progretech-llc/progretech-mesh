from __future__ import annotations

from typing import Any

from .base import RuntimeAdapter, RuntimeResponse


class DemoRuntimeAdapter(RuntimeAdapter):
    name = "demo"

    def send_message(
        self,
        *,
        agent_id: str,
        text: str,
        room: str,
        sender: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> RuntimeResponse:
        room_label = "group room" if room == "group" else "direct conversation"
        attachment_note = ""
        if attachments:
            names = ", ".join(str(item.get("filename", "file")) for item in attachments)
            attachment_note = f" Attachments available locally: {names}."

        return RuntimeResponse(
            ok=True,
            text=(
                f"{agent_id.capitalize()} received your message through Mesh "
                f"({room_label}). Demo runtime adapter is active. "
                f"Message: {text}.{attachment_note}"
            ),
            metadata={"adapter": self.name, "room": room},
        )
