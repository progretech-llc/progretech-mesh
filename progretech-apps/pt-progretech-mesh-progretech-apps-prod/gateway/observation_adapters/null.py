from __future__ import annotations

from .base import ObservationAdapter


class NullObservationAdapter(ObservationAdapter):
    name = "none"

    def health(self):
        return {
            "ok": True,
            "adapter": self.name,
            "mode": "read-only",
            "detail": "No passive activity source configured.",
        }
