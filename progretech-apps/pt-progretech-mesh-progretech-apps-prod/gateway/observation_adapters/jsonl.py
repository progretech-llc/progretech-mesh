from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .base import ObservationAdapter, ObservationEvent


class JsonlObservationAdapter(ObservationAdapter):
    """
    Passive adapter for an append-only local activity feed.

    The agent/runtime may export normalized activity into this file. Mesh only reads
    newly appended lines and never writes to, truncates, rotates, or otherwise modifies
    the source.
    """

    name = "jsonl"

    def __init__(self) -> None:
        self.path = Path(
            os.path.expanduser(
                os.environ.get("MESH_OBSERVER_JSONL", "~/.progretech-mesh/activity.jsonl")
            )
        )
        self._offset = 0
        self._identity = None

    def health(self) -> dict[str, Any]:
        return {
            "ok": self.path.exists(),
            "adapter": self.name,
            "mode": "read-only",
            "path": str(self.path),
            "exists": self.path.exists(),
        }

    def _reset_if_rotated(self) -> None:
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return

        identity = (stat.st_dev, stat.st_ino)
        if self._identity is None:
            self._identity = identity
        elif self._identity != identity or stat.st_size < self._offset:
            self._identity = identity
            self._offset = 0

    def poll(self) -> list[ObservationEvent]:
        if not self.path.exists():
            return []

        self._reset_if_rotated()
        events: list[ObservationEvent] = []

        with self.path.open("r", encoding="utf-8", errors="replace") as handle:
            handle.seek(self._offset)
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    # Invalid lines are ignored because this adapter must never alter
                    # or repair the source file.
                    continue

                events.append(
                    ObservationEvent(
                        event_type=str(data.get("event_type", data.get("type", "activity"))),
                        channel=str(data.get("channel", "system")),
                        state=str(data.get("state", "active")),
                        direction=data.get("direction"),
                        summary=data.get("summary") or data.get("message"),
                        payload=dict(data.get("payload") or {}),
                    )
                )

            self._offset = handle.tell()

        return events
