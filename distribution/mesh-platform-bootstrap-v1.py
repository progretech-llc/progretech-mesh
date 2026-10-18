"""Verified, owner-run connector install. Runtime credentials never leave this host."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import zipfile
import io


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    if hasattr(os, 'fchmod'):
        os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    identity = parser.add_mutually_exclusive_group(required=True)
    identity.add_argument('--enrollment-file', type=Path)
    identity.add_argument('--reconnect-file', type=Path, help='Existing owner-bound Mesh device credential; preserve the signed host identity during migration')
    parser.add_argument('--platform', choices=['hermes', 'opencode', 'openwebui', 'openai'], required=True)
    parser.add_argument('--prime', required=True, help='Exact profile/agent/model ID, not a guessed display name')
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--endpoint', help='API base including /api for Open WebUI or /v1 for compatible servers')
    parser.add_argument('--api-key-file', type=Path)
    parser.add_argument('--exclude', action='append', default=[], help='Discover but never execute this native profile ID')
    parser.add_argument('--start', action='store_true', help='Run connector in foreground after checks; install under your native supervisor for persistence')
    args = parser.parse_args()
    if not shutil.which('node'):
        parser.error('Node.js is required for the existing Factory board. Install a supported Node LTS with your normal authority.')
    workspace = args.workspace.expanduser().resolve(strict=True)
    if not workspace.is_dir():
        parser.error('workspace must be an existing directory')
    reconnect = json.loads(args.reconnect_file.read_text()) if args.reconnect_file else {}
    if reconnect:
        envelope = reconnect
        if not isinstance(reconnect.get('device_credential'), str) or not reconnect['device_credential']:
            parser.error('signed reconnect credential required')
    else:
        text = args.enrollment_file.read_text().strip()
        if text.startswith('{'):
            text = json.loads(text)['enrollment_payload']
        if not text.startswith('PTM1:'):
            parser.error('website-generated PTM1 enrollment required')
        encoded = text[5:]
        envelope = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        if envelope.get('type') != 'PROGRETECH_MESH_CONNECT_OR_ENROLL' or envelope.get('version') != 5:
            parser.error('unsupported enrollment envelope')
    base = envelope['mesh'].rstrip('/')
    u = urlsplit(base)
    if u.scheme != 'https' or not u.hostname or u.path or u.query or u.fragment or u.username or u.password:
        parser.error('plain HTTPS Mesh origin required')
    opener = build_opener(NoRedirect)
    def call(path, body=None, limit=4 * 1024 * 1024):
        req = Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                      headers={'Content-Type': 'application/json'})
        with opener.open(req, timeout=45) as response:
            raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('mesh_response_too_large')
        return raw
    plan = json.loads(call('/api/enrollment/adapters/platform/install-plan'))
    bundle = call('/api/distribution/host/bundle', limit=32 * 1024 * 1024)
    if hashlib.sha256(bundle).hexdigest() != plan['bundle_sha256']:
        raise ValueError('bundle_checksum_mismatch')
    state = Path.home() / '.progretech-mesh/platform'
    source = state / 'source'
    source.mkdir(parents=True, exist_ok=True, mode=0o700)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        for member in archive.infolist():
            destination = (source / member.filename).resolve()
            if not destination.is_relative_to(source.resolve()) or member.is_dir() or member.file_size > 16 * 1024 * 1024:
                raise ValueError('unsafe_bundle_member')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(member))
    environment = state / 'venv'
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(source / 'requirements.txt')], check=True)
    sys.path.insert(0, str(source))
    # Use the installed environment to validate native discovery before consuming activation.
    config = {'platform': args.platform, 'prime': args.prime, 'workspace': str(workspace),
        'endpoint': args.endpoint, 'api_key_file': str(args.api_key_file.expanduser().resolve()) if args.api_key_file else None,
        'excluded_agents': args.exclude, 'mesh': base, 'agent_id': envelope['agent_id'], 'device_credential': reconnect.get('device_credential', '')}
    config_file = state / 'connector.json'
    if config_file.exists():
        old = json.loads(config_file.read_text())
        if old.get('agent_id') == config['agent_id'] and old.get('mesh') == base:
            config['device_credential'] = old.get('device_credential', '')
    # Persist a candidate separately so a failed preflight cannot clobber a working connection.
    candidate = state / 'candidate.json'
    private(candidate, config)
    subprocess.run([str(python), '-m', 'gateway.platform_gateway', '--config', str(candidate), '--check'], cwd=source, check=True)
    if not config['device_credential']:
        redeemed = json.loads(call('/api/activation/redeem', {k: envelope[k] for k in ('agent_id', 'activation_code', 'activation_signature')}))
        if not redeemed.get('ok'):
            raise ValueError('activation_failed')
        config['device_credential'] = redeemed['device_credential']
    private(config_file, config)
    candidate.unlink(missing_ok=True)
    print('Connector ready. Install the following command in your authorized host supervisor; keep its config private:')
    command = [str(python), '-m', 'gateway.platform_gateway', '--config', str(config_file)]
    print('Working directory:', source)
    print('Command:', __import__('shlex').join(command))
    if args.start:
        subprocess.run(command, cwd=source, check=True)


if __name__ == '__main__':
    main()
