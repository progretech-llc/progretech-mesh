"""Build on the target OS; released app does not require Python, Node or Git."""
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_all, copy_metadata

root = Path(SPECPATH).parent
datas = [(str(root / p), p) for p in ('templates', 'static', 'office', 'vendor/munder-difflin')]
datas += [(str(root / 'packaging/runtime-cache'), 'runtimes')]
datas += [(str(root / 'packaging/THIRD_PARTY_NOTICES.md'), 'licenses'), (str(root / 'LICENSE.md'), 'licenses')]
datas += [(str(root / 'packaging/licenses'), 'licenses')]
for package in ('PyInstaller', 'PySide6', 'PySide6_Addons', 'PySide6_Essentials', 'shiboken6'):
    datas += copy_metadata(package)
binaries, hiddenimports = [], []
for package in ('crewai', 'llama_cpp'):
    d, b, h = collect_all(package)
    datas += d; binaries += b; hiddenimports += h
datas += copy_metadata('crewai', recursive=True)
hiddenimports += ['offline.local_llm', 'control_center.factory_worker', 'control_center.office_crew', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineCore']
if os.name != 'nt':
    binaries.append((str(root / 'packaging/runtime-cache/git/bin/git'), 'runtimes/git/bin'))
    # Qt's xcb extras are absent from a stock Ubuntu desktop. Include them in
    # the portable bundle so installation does not need an apt download.
    import ctypes.util
    for name in ('xcb', 'xcb-cursor', 'xcb-icccm', 'xcb-image', 'xcb-keysyms',
                 'xcb-render', 'xcb-render-util', 'xcb-shape', 'xcb-shm',
                 'xcb-sync', 'xcb-util', 'xcb-xfixes', 'xcb-xkb',
                 'xkbcommon', 'xkbcommon-x11', 'Xau', 'Xdmcp'):
        soname = ctypes.util.find_library(name)
        paths = [directory / soname for directory in (Path('/usr/lib/x86_64-linux-gnu'), Path('/lib/x86_64-linux-gnu'))] if soname else []
        library = next((path for path in paths if path.is_file()), None)
        if library is None: raise RuntimeError('Missing build-time Qt platform library: ' + name)
        binaries.append((str(library), '.'))
    for pattern in ('libxcb*', 'libxkbcommon*', 'libxau*', 'libxdmcp*'):
        for notice in Path('/usr/share/doc').glob(pattern + '/copyright'):
            datas.append((str(notice), 'licenses/system/' + notice.parent.name))
analysis = Analysis([str(root / 'mesh_offline.py')], pathex=[str(root)], binaries=binaries,
    datas=datas, hiddenimports=hiddenimports, excludes=['tkinter', 'PyQt5', 'PyQt6'], noarchive=False)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name='MeshOffline',
    debug=False, strip=False, upx=False, console=True)
bundle = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, name='MeshOffline')
