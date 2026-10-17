#!/usr/bin/env python3
"""Install the verified Mesh host bundle without altering the agent runtime."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import zipfile


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def save(path, value):
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream: json.dump(value, stream)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--gateway', required=True)
    parser.add_argument('--runtime', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]{1,48}', args.gateway) or not re.fullmatch('[A-Za-z0-9_.-]{1,128}', args.runtime):
        raise SystemExit('Invalid gateway or runtime binding')
    origin = urlsplit(args.bundle)
    if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password or origin.fragment:
        raise SystemExit('A verified HTTPS bundle URL is required')
    with build_opener(NoRedirect).open(Request(args.bundle), timeout=30) as response: data = response.read(8*1024*1024+1)
    if len(data) > 8*1024*1024 or hashlib.sha256(data).hexdigest() != args.sha256:
        raise SystemExit('Host bundle verification failed')
    state = Path.home() / '.progretech-mesh'
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    root = state / 'host' / args.sha256
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 16*1024*1024:
            raise SystemExit('Host bundle is too large')
        for item in archive.infolist():
            path = Path(item.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in item.filename:
                raise SystemExit('Invalid host bundle path')
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            target.write_bytes(archive.read(item))
    python = root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        subprocess.run([sys.executable, '-m', 'venv', str(root / '.venv')], check=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(root / 'requirements.txt')], check=True)
    sys.path.insert(0, str(root))
    from control_center.gateway_roster import native_roster
    if args.runtime not in {row['runtime_id'] for row in native_roster(Path.home())}:
        raise SystemExit('Running agent is not in the local gateway roster')
    bindings_path = state / 'control-center-bindings.json'
    bindings = json.loads(bindings_path.read_text()) if bindings_path.exists() else {}
    if args.gateway in bindings and bindings[args.gateway] != args.runtime:
        raise SystemExit('Existing gateway runtime binding differs')
    bindings[args.gateway] = args.runtime
    save(bindings_path, bindings)
    if not (state / 'local-access.json').exists(): save(state / 'local-access.json', {'version': 1, 'token': secrets.token_urlsafe(32)})
    save(state / 'portable-host.json', {'python': str(python), 'root': str(root)})
    print('Mesh host is installed. The Mesh adapter starts it on demand; no agent restart is needed.')


if __name__ == '__main__': main()
