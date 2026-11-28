from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ObservationEvent:
    event_type: str
    channel: str
    state: str
    direction: str | None = None
    summary: str | None = None
    payload: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "channel": self.channel,
            "state": self.state,
            "direction": self.direction,
            "summary": self.summary,
            "payload": self.payload or {},
        }


class ObservationAdapter:
    """
    Read-only observation contract.

    Implementations MUST NOT:
    - start/stop/restart the agent runtime
    - mutate an existing task/session
    - change model/runtime configuration
    - claim ownership of another channel session
    """

    name = "base"

    def health(self) -> dict[str, Any]:
        return {"ok": True, "adapter": self.name, "mode": "read-only"}

    def poll(self) -> list[ObservationEvent]:
        return []
