#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.home() / ".progretech-mesh" / "quarantine" / "archify" / "2.11.0" / "source" / "archify"

def find_node() -> str:
    candidates = [
        shutil.which("node"),
        str(Path.home() / ".openclaw" / "tools" / "node-v24.19.0" / "bin" / "node"),
    ]
    tools = Path.home() / ".openclaw" / "tools"
    if tools.exists():
        candidates.extend(str(p / "bin" / "node") for p in sorted(tools.glob("node-v*"), reverse=True))
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise SystemExit("qualified node runtime unavailable")

def main() -> int:
    if len(sys.argv) < 2:
        print("usage: archify-runtime.py <doctor|guide|validate|deliver> [args...]", file=sys.stderr)
        return 2

    action = sys.argv[1]
    if action not in {"doctor", "guide", "validate", "deliver"}:
        print("unsupported Archify action", file=sys.stderr)
        return 3

    cli = ROOT / "bin" / "archify.mjs"
    if not cli.is_file():
        print("qualified Archify runtime unavailable", file=sys.stderr)
        return 4

    env = os.environ.copy()
    for key in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY"):
        env.pop(key, None)

    proc = subprocess.run(
        [find_node(), str(cli), action, *sys.argv[2:]],
        cwd=str(ROOT),
        env=env,
        timeout=60,
    )
    return proc.returncode

if __name__ == "__main__":
    raise SystemExit(main())
