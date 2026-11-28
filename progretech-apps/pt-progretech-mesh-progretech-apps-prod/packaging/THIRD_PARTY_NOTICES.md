# Mesh Offline third-party components

Mesh source retains the ProgreTech Public Source License in LICENSE.md. Dependency licenses apply separately and are not replaced by that license.

- CrewAI: MIT, https://github.com/crewaiinc/crewai (1.15.23).
- Munder Difflin: MIT, vendor/munder-difflin/LICENSE and UPSTREAM.json identify the retained source and revision.
- llama-cpp-python and llama.cpp: MIT, https://github.com/abetlen/llama-cpp-python (0.3.16). The bundled package retains its distribution metadata and native libraries.
- Qwen2.5-0.5B-Instruct-GGUF: Apache 2.0, Alibaba Cloud. The exact revision, checksum and license are in runtimes/models. Original model: https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF. Quantized weights are distributed unchanged.
- Python: PSF License, https://www.python.org/downloads/source/ (3.12).
- Qt / PySide6 / Shiboken6: LGPL v3/GPL v3/commercial as applicable, https://doc.qt.io/qtforpython-6/licenses.html (6.10.2). The installer uses replaceable shared libraries in its on-directory distribution. Corresponding Qt source is available at https://download.qt.io/archive/qt/6.10/6.10.2/submodules/ and PySide source at https://download.qt.io/official_releases/QtForPython/pyside6/. Users may replace these libraries and debug modifications. No restriction on reverse engineering for this purpose is imposed by Mesh.
- Node.js: MIT with bundled component notices, runtimes/node/LICENSE (22.22.0).
- Ubuntu Qt platform libraries: libxcb, libxkbcommon, libXau and libXdmcp, with their Debian copyright and license notices in licenses/system. These unmodified shared libraries provide the xcb platform extras without installation-time downloads.
- Git: GPL v2, runtimes/git/COPYING or runtimes/git/mingw64/share/licenses. Ubuntu includes the exact upstream corresponding-source.tar.xz for its locally built Git (2.53.0). Windows uses unmodified Git for Windows MinGit 2.53.0.windows.1; upstream source and build scripts are at https://github.com/git-for-windows/git/tree/v2.53.0.windows.1 and https://github.com/git-for-windows/build-extra.

Python dependency notices and licenses are retained in their .dist-info directories. The build also emits a dependency inventory with names and versions. Chromium and Qt resource notices remain with Qt WebEngine. Operating-system graphics and audio libraries retain their platform licenses.
