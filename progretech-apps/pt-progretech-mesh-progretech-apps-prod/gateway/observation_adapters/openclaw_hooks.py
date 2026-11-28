from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .jsonl import JsonlObservationAdapter


class OpenClawHooksObservationAdapter(JsonlObservationAdapter):
    name = "openclaw_hooks"

    def __init__(self) -> None:
        explicit = os.environ.get("PROGRETECH_MESH_EVENT_PATH", "").strip()
        if explicit:
            os.environ["MESH_OBSERVATION_JSONL"] = explicit
        elif os.environ.get("XDG_RUNTIME_DIR"):
            os.environ["MESH_OBSERVATION_JSONL"] = str(
                Path(os.environ["XDG_RUNTIME_DIR"]) / "progretech-mesh" / "openclaw-activity.jsonl"
            )
        else:
            os.environ["MESH_OBSERVATION_JSONL"] = str(
                Path(tempfile.gettempdir()) / f"progretech-mesh-{os.getuid() if hasattr(os, 'getuid') else 'user'}" / "openclaw-activity.jsonl"
            )
        super().__init__()
