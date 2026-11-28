from __future__ import annotations

import os

from .base import ObservationAdapter
from .jsonl import JsonlObservationAdapter
from .null import NullObservationAdapter
from .openclaw_hooks import OpenClawHooksObservationAdapter


def build_observation_adapter() -> ObservationAdapter:
    requested = os.environ.get("MESH_OBSERVATION_ADAPTER", "none").strip().lower()

    if requested == "openclaw_hooks":
        return OpenClawHooksObservationAdapter()

    if requested == "jsonl":
        return JsonlObservationAdapter()

    return NullObservationAdapter()
