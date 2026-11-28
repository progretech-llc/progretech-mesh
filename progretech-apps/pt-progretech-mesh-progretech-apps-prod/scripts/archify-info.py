#!/usr/bin/env python3
from pathlib import Path
import json, sys

ROOT = Path.home() / ".progretech-mesh" / "qualification-evidence" / "archify" / "2.11.0"
files = sorted(ROOT.glob("qualification-*.json"))
if not files:
    print("no Archify qualification evidence found", file=sys.stderr)
    raise SystemExit(2)
data = json.loads(files[-1].read_text(encoding="utf-8"))
print(json.dumps({
    "capability": data.get("capability"),
    "version": data.get("version"),
    "commit": data.get("commit"),
    "representative_output": data.get("representative_output"),
    "network_runtime_required": data.get("network_runtime_required"),
}, indent=2))
