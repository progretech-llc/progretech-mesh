"""Public Mesh integration fingerprints; no credentials or profile contents."""
import hashlib
import json
from pathlib import Path


def digest(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def installed(root):
    root = Path(root)
    paths = [*root.joinpath('control_center').glob('*.py'), *root.joinpath('gateway').glob('platform*.py'),
             root/'office/engine.mjs', root/'offline/__init__.py', root/'offline/registry.py', root/'requirements.txt']
    try:
        return digest({p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    except OSError:
        return None
