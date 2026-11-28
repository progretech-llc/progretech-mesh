#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

QUAR = Path.home() / ".progretech-mesh" / "quarantine" / "firecrawl-anydoc" / "0.2.4"
PY = QUAR / ".venv" / "bin" / "python"

def main() -> int:
    if len(sys.argv) != 2:
        print("usage: anydoc-local.py <document>", file=sys.stderr)
        return 2
    if not PY.exists():
        print("anydoc capability is not installed in quarantine", file=sys.stderr)
        return 3
    target = Path(sys.argv[1]).expanduser().resolve()
    if not target.is_file():
        print("input file not found", file=sys.stderr)
        return 4

    code = "import anydoc,sys; print(anydoc.to_markdown(sys.argv[1]))"
    env = os.environ.copy()
    env.pop("FIRECRAWL_API_KEY", None)
    env.pop("FIRECRAWL_API_URL", None)
    proc = subprocess.run([str(PY), "-c", code, str(target)], env=env, timeout=30)
    return proc.returncode

if __name__ == "__main__":
    raise SystemExit(main())
