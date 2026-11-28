#!/usr/bin/env python3
"""Stage, verify and update Mesh connector files using its existing private config."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler
import zipfile


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def unpack(data, destination, expected):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('bundle_checksum_mismatch; refresh Sync & Update for the latest prompt')
    files = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > 256 or sum(m.file_size for m in members) > 32*1024*1024:
            raise ValueError('bundle_too_large')
        for m in members:
            name = m.filename
            if (not re.fullmatch(r'(control_center/[A-Za-z0-9_]+\.py|gateway/platform[A-Za-z0-9_]*\.py|office/engine\.mjs|offline/(__init__|registry)\.py|requirements\.txt)', name)
                    or name in files or m.is_dir() or (m.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('unsafe_bundle_member')
            body = archive.read(m)
            target = destination/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            files[name] = hashlib.sha256(body).hexdigest()
    if not {'gateway/platform_gateway.py','gateway/platforms.py','requirements.txt','office/engine.mjs'} <= files.keys():
        raise ValueError('incomplete_bundle')
    return files


def update(state, expected, apply=False):
    state = state.expanduser().resolve()
    config = state/'connector.json'
    cfg = json.loads(config.read_text())
    origin = cfg['mesh'].rstrip('/')
    url = urlsplit(origin)
    if url.scheme != 'https' or not url.hostname or url.path or url.query or url.fragment or url.username or url.password:
        raise ValueError('plain_https_mesh_origin_required')
    if not re.fullmatch('[a-f0-9]{64}', expected): raise ValueError('invalid_checksum')
    with build_opener(NoRedirect).open(origin+'/api/distribution/host/bundle', timeout=45) as response:
        data = response.read(32*1024*1024+1)
    if len(data) > 32*1024*1024: raise ValueError('bundle_too_large')
    source = state/'source'
    python = state/'venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not source.is_dir() or not python.is_file(): raise ValueError('existing_platform_installation_required')
    lock = state/'update.lock'
    fd = os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with tempfile.TemporaryDirectory(prefix='.mesh-update-', dir=state) as temporary:
            stage = Path(temporary)/'source'
            shutil.copytree(source, stage, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            files = unpack(data, stage, expected)
            changed = [name for name, sha in files.items() if not (source/name).is_file()
                       or hashlib.sha256((source/name).read_bytes()).hexdigest() != sha]
            print(json.dumps({'changed_files':changed,'apply':apply}))
            if not apply: return
            # The owner agent stops the connector and waits for jobs before applying.
            subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','-r',str(stage/'requirements.txt')], check=True)
            subprocess.run([str(python),'-m','gateway.platform_gateway','--config',str(config),'--check'], cwd=stage,
                           stdout=subprocess.DEVNULL, check=True)
            previous = Path(temporary)/'previous'
            source.rename(previous)
            try:
                stage.rename(source)
            except BaseException:
                previous.rename(source)
                raise
            release = state/'release.json'
            release.write_text(json.dumps({'bundle_sha256':expected,'files':files})+'\n')
            os.chmod(release,0o600)
            print('Mesh integration updated. Restart its existing supervisor, then verify Sync & Update and the Factory roster.')
    finally:
        lock.unlink()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',type=Path,default=Path.home()/'.progretech-mesh/platform')
    p.add_argument('--sha256',required=True)
    p.add_argument('--apply',action='store_true',help='Apply after the owning agent has stopped the connector and reviewed the changed files')
    args=p.parse_args()
    update(args.state,args.sha256,args.apply)


if __name__=='__main__':main()
