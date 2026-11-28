"""Native build and installer assembly; no runtime dependency downloads."""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / 'packaging/runtime-cache'
NODE = '22.22.0'
GIT = '2.53.0'
VERSION = os.environ.get('MESH_OFFLINE_VERSION', '0.1.1')
MODEL_REV = '9217f5db79a29953eb74d5343926648285ec7e67'
MODEL_SHA256 = '74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db'


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists(): urllib.request.urlretrieve(url, path)
    return path


def prepare():
    win = os.name == 'nt'
    node_name = f'node-v{NODE}-' + ('win-x64.zip' if win else 'linux-x64.tar.xz')
    archive = download(f'https://nodejs.org/dist/v{NODE}/{node_name}', CACHE / node_name)
    sums = download(f'https://nodejs.org/dist/v{NODE}/SHASUMS256.txt', CACHE / 'node-shasums.txt').read_text()
    expected = next(line.split()[0] for line in sums.splitlines() if line.split()[-1] == node_name)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected, 'Node checksum mismatch'
    node = CACHE / 'node'
    if not node.exists():
        extracted = CACHE / 'unpack-node'; extracted.mkdir(exist_ok=True)
        if win:
            with zipfile.ZipFile(archive) as z: z.extractall(extracted)
        else:
            with tarfile.open(archive) as t: t.extractall(extracted, filter='data')
        shutil.move(str(next(extracted.iterdir())), node)
        shutil.rmtree(extracted)
    git = CACHE / 'git'
    if not git.exists():
        if win:
            archive = download(f'https://github.com/git-for-windows/git/releases/download/v{GIT}.windows.1/MinGit-{GIT}-64-bit.zip', CACHE / 'mingit.zip')
            git.mkdir()
            with zipfile.ZipFile(archive) as z: z.extractall(git)
        else:
            archive = download(f'https://www.kernel.org/pub/software/scm/git/git-{GIT}.tar.xz', CACHE / f'git-{GIT}.tar.xz')
            with tarfile.open(archive) as t: t.extractall(CACHE, filter='data')
            source = CACHE / f'git-{GIT}'
            options = ['NO_GETTEXT=YesPlease', 'NO_CURL=YesPlease', 'NO_OPENSSL=YesPlease', 'NO_EXPAT=YesPlease', 'NO_TCLTK=YesPlease']
            subprocess.run(['make', '-j2', 'git', *options], cwd=source, check=True)
            (git / 'bin').mkdir(parents=True)
            shutil.copy2(source / 'git', git / 'bin/git')
            shutil.copy2(source / 'COPYING', git / 'COPYING')
            shutil.copy2(archive, git / 'corresponding-source.tar.xz')
            shutil.rmtree(source)
    # Exclude download intermediates from the installed app.
    for item in CACHE.iterdir():
        if item.is_file(): item.unlink()
    model = download(f'https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/{MODEL_REV}/qwen2.5-0.5b-instruct-q4_k_m.gguf', CACHE / 'models/starter.gguf')
    assert hashlib.sha256(model.read_bytes()).hexdigest() == MODEL_SHA256, 'Starter model checksum mismatch'
    download(f'https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/{MODEL_REV}/LICENSE', CACHE / 'models/LICENSE')
    (CACHE / 'models/UPSTREAM.json').write_text(json.dumps({'repository':'Qwen/Qwen2.5-0.5B-Instruct-GGUF', 'revision':MODEL_REV, 'sha256':MODEL_SHA256}))


def build():
    prepare()
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', str(ROOT / 'packaging/mesh-offline.spec')], cwd=ROOT, check=True)
    app = ROOT / 'dist/MeshOffline'
    import importlib.metadata
    inventory = sorted([{'name':d.metadata['Name'], 'version':d.version} for d in importlib.metadata.distributions()], key=lambda d:d['name'].lower())
    (app / 'DEPENDENCIES.json').write_text(json.dumps(inventory, indent=2))
    executable = app / ('MeshOffline.exe' if os.name == 'nt' else 'MeshOffline')
    subprocess.run([str(executable), '--self-test'], check=True, timeout=120)
    out = ROOT / 'dist/releases'; out.mkdir(exist_ok=True)
    if os.name == 'nt':
        shutil.make_archive(str(out / f'mesh-offline-{VERSION}-windows-x64'), 'zip', app.parent, app.name)
        # Inno Setup is preinstalled on GitHub's Windows runner.
        compiler = shutil.which('iscc') or r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
        subprocess.run([compiler, f'/DAppVersion={VERSION}', str(ROOT / 'packaging/windows.iss')], cwd=ROOT, check=True)
    else:
        shutil.make_archive(str(out / f'mesh-offline-{VERSION}-ubuntu-x64'), 'gztar', app.parent, app.name)
        deb = ROOT / 'dist/debian'
        target = deb / 'opt/progretech/mesh-offline'; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(app, target, dirs_exist_ok=True)
        (deb / 'DEBIAN').mkdir(exist_ok=True)
        (deb / 'DEBIAN/control').write_text(f'Package: mesh-offline\nVersion: {VERSION}\nArchitecture: amd64\nMaintainer: ProgreTech\nSection: utils\nPriority: optional\nDepends: libc6 (>= 2.35), libgl1, libegl1, libxkbcommon0, libnss3, libasound2 | libasound2t64\nDescription: Mesh Offline agent orchestration desktop\n Bundled Python, Qt, CrewAI, local inference, Node and Git.\n')
        applications = deb / 'usr/share/applications'; applications.mkdir(parents=True, exist_ok=True)
        (applications / 'mesh-offline.desktop').write_text('[Desktop Entry]\nType=Application\nName=Mesh Offline\nComment=Local agent orchestration\nExec=/opt/progretech/mesh-offline/MeshOffline\nTerminal=false\nCategories=Development;Utility;\n')
        subprocess.run(['dpkg-deb', '-Zgzip', '-z1', '--root-owner-group', '--build', str(deb), str(out / f'mesh-offline-{VERSION}-ubuntu-amd64.deb')], check=True)
    sums = []
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != 'SHA256SUMS.txt': sums.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name)
    (out / 'SHA256SUMS.txt').write_text('\n'.join(sums) + '\n')


if __name__ == '__main__': build()
