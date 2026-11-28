from __future__ import annotations

import os

from .base import RuntimeAdapter
from .demo import DemoRuntimeAdapter
from .openclaw import OpenClawRuntimeAdapter
from .openclaw_bridge import OpenClawBridgeRuntimeAdapter


def build_runtime_adapter() -> RuntimeAdapter:
    requested = os.environ.get("MESH_RUNTIME_ADAPTER", "demo").strip().lower()

    if requested == "openclaw_bridge":
        return OpenClawBridgeRuntimeAdapter()

    if requested == "openclaw":
        return OpenClawRuntimeAdapter()

    return DemoRuntimeAdapter()
