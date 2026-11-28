#!/usr/bin/env python3
from pathlib import Path
import json, sys

ROOT = Path.home() / ".progretech-mesh" / "quarantine" / "mattpocock-skills" / "1.2.3"
CURATED = ROOT / "curated"

def main() -> int:
    if len(sys.argv) != 2:
        print("usage: curated-skill-info.py <skill-name>", file=sys.stderr)
        return 2
    name = sys.argv[1]
    skill = CURATED / name / "SKILL.md"
    if not skill.is_file():
        print("skill not in qualified curated pack", file=sys.stderr)
        return 3
    print(skill.read_text(encoding="utf-8"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
