from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RuntimeResponse:
    ok: bool
    text: str
    metadata: dict[str, Any]
    error: str | None = None


class RuntimeAdapter:
    name = "base"

    def health(self) -> dict[str, Any]:
        return {"ok": True, "adapter": self.name}

    def send_message(
        self,
        *,
        agent_id: str,
        text: str,
        room: str,
        sender: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> RuntimeResponse:
        raise NotImplementedError
