# Mesh Offline

Ubuntu is the recommended desktop platform. The Windows edition is built natively from the same Python application. Installers include Python, Qt WebEngine, Flask, CrewAI, the Munder Difflin coordination engine, Node, Git, llama.cpp inference and an Apache-licensed Qwen starter model. They require no hosted Mesh account, Firebase, CodeSeal, public gateway, model server or runtime dependency downloads.

## Install

Use the Ubuntu `.deb` from the Mesh Offline release on Ubuntu 22.04 or newer, x86-64:

```bash
sudo apt install ./mesh-offline-0.1.1-ubuntu-amd64.deb
```

On a standard Ubuntu desktop, installation can be performed without network access using `sudo dpkg -i ./mesh-offline-0.1.1-ubuntu-amd64.deb`. Qt's additional xcb libraries are bundled. A minimal/server Ubuntu installation still needs its operating-system graphics and audio stack before running a desktop application.

Launch **Mesh Offline** from the applications menu. The tar archive is a portable alternative: extract it and run `MeshOffline/MeshOffline`. Keep the `_internal` directory beside the executable. Windows users run the `windows-setup.exe` installer; the portable zip also contains `MeshOffline.exe` and all its dependencies. Neither platform needs a separately installed Python.

The application uses an embedded, private loopback UI engine while its window is open. It binds only to 127.0.0.1 on a random port and requires a per-launch desktop cookie. It is not an externally hosted server or a service users need to administer. The native browser blocks nonlocal requests. Closing the app closes this engine.

## Bring your agents

1. Click the **Agent onboarding** plus tile in Mission Control.
2. Find installed OpenClaw, Hermes or Claude runtimes, or enter their executable and workspace. Discovery reads only public identity and workspace fields. Nothing is added until you confirm ownership, acknowledge Mesh’s intermediary role and click Add.
3. To add gateway agents one by one, use **Select identified agents from gateway**. This reads the running local OpenClaw gateway. Select an agent, review its executable/workspace, acknowledge ownership and add it. Already linked agents disappear from the list; a repeated or simultaneous selection is rejected. No PEM or CodeSeal is created locally.
4. For a PyCharm project, select its Python executable, workspace and runnable agent entry point. The Files menu provides native file and folder pickers. The entry point receives one JSON object with a `question` on stdin, prints its answer on stdout, and exits with zero on success. PyCharm itself is an IDE and does not provide this runtime protocol.
5. Ask the agent to identify itself. Its pulse turns green only after it actually returns a successful answer.

Onboarding stores local references. It does not copy credentials, histories, model subscriptions or another agent's private memory, and does not alter the source runtime's configuration. Unlinking an agent removes the reference, not the runtime or project.

OpenClaw runs embedded `agent --local`; Hermes runs one-shot `chat --query-file`; Claude runs `-p --output-format json`. Existing agents retain their own model configuration. A runtime configured for an online provider still needs that provider; importing it cannot make that provider offline. Python agents and runtimes configured for local models can operate offline.

## Run your office offline

The included 0.5B model is a small CPU starter suitable for checking the workflow, not a substitute for a capable model on difficult missions. You can choose a larger instruction-tuned GGUF in Mission Control. No model server is required: CrewAI calls the bundled inference engine directly.

Open Factory, hire workers, and create missions with dependencies and owner approvals. To let a worker use an imported runtime, return to Mission Control and select that agent under the worker's name, then save. CrewAI delegates between office workers and provides a bounded tool to call each linked local agent. The Hive engine preserves mailboxes, tasks, reviewed office memory, results and history. Pausing takes effect at the next agent step; it does not kill an already running external runtime.

State is stored in the OS application-data directory for `ProgreTech/Mesh Offline`, separate from hosted Mesh state. Back up this directory with the app closed. Workspace and runtime files remain where the user keeps them.

## Development and release

Use Python 3.12 and `requirements-offline.txt`, then run `python mesh_offline.py`. Build with `python packaging/build.py` on the target OS. Ubuntu builds include a portable archive and a `.deb`; Windows builds include a portable zip and an Inno Setup executable. PyInstaller cannot cross-compile these applications, so CI builds each on its native runner. Runtime/model downloads happen at build time and are placed inside the installer. SHA256 manifests accompany release assets.

`python mesh_offline.py --self-test` checks the actual bundled coordination engine and inference imports. The separate offline tests exercise ownership, origin/cookie protection, secret-free import, local-only settings and an actual Python agent's response. The release workflow executes these checks before uploading assets.
