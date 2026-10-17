"""Reproducible host bundle built from the same source as this Mesh release."""
import hashlib
import io
from pathlib import Path
import zipfile


def host_bundle(root):
    root = Path(root)
    files = sorted((root / 'control_center').glob('*.py'))
    files += [root / 'office/engine.mjs', root / 'offline/__init__.py', root / 'offline/registry.py']
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(root).as_posix())
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo('requirements.txt')
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, 'Flask>=3.1,<4\npsutil>=6,<8\n')
    data = output.getvalue()
    return data, hashlib.sha256(data).hexdigest()


def host_setup_prompt(root, origin, gateway):
    _, digest = host_bundle(root)
    helper = Path(root) / 'distribution/mesh-host-bootstrap-v1.py'
    return '\n'.join([
        'For OpenClaw: core Mesh controls require the portable host provider. An existing authenticated reference provider on port 8787 can be reused.',
        f'If no provider is installed, fetch {origin}/api/distribution/host/bootstrap and verify SHA-256 {hashlib.sha256(helper.read_bytes()).hexdigest()} before executing.',
        f'Host bundle: {origin}/api/distribution/host/bundle ; SHA-256: {digest}',
        f'Using your normal installation authority, run: python3 mesh-host-bootstrap-v1.py --bundle {origin}/api/distribution/host/bundle --sha256 {digest} --gateway {gateway} --runtime <your actual running OpenClaw agent id>',
        'This installs an isolated Mesh provider and its Flask/psutil dependencies. It does not change or restart your agent runtime. Keep the gateway binding local; never guess the runtime id from a display name.',
        'For the IDE relay, check gateway.http.endpoints.chatCompletions.enabled. If disabled, enable it through the gateway supported control UI using your existing owner authority, retaining loopback binding and token authentication. Do not restart the runtime; report a pending reload if required.',
        'The Mesh adapter starts the provider automatically. Reconnect and verify agent discovery, Factory and Control Center before reporting success.',
    ])
