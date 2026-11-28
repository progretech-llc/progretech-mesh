#!/usr/bin/env python3
"""Point the existing local Mesh service at the same reviewed release source.

Run from the release checkout after tests. Preserves the base unit and host data;
never copies credentials or overlays an unrelated dirty product checkout.
"""
import argparse
import json
import subprocess
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--python',required=True);parser.add_argument('--version',required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip():raise SystemExit('Commit the reviewed release before installation')
    interpreter=Path(args.python).absolute()
    if not interpreter.is_file():raise SystemExit('Python interpreter not found')
    for value in (str(root),str(interpreter),args.version):
        if any(c in value for c in '\n\r"%'):raise SystemExit('Unsafe unit value')
    folder=Path.home()/'.config/systemd/user/progretech-mesh-local.service.d';folder.mkdir(parents=True,exist_ok=True)
    path=folder/'release.conf'
    if path.exists() and not path.with_suffix('.conf.before').exists():path.with_suffix('.conf.before').write_bytes(path.read_bytes())
    path.write_text(f'''[Service]
WorkingDirectory={root}
ExecStart=
ExecStart="{interpreter}" "{root}/main.py"
Environment=MESH_LOCAL_CONTROL_CENTER=1
Environment=DEV_SEED_AGENTS=0
Environment=TRUST_PROXY_HEADERS=0
Environment=MESH_VERSION={args.version}
Environment=BUILD_ID={commit[:7]}
''')
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','restart','progretech-mesh-local.service'],check=True)
    print(json.dumps({'source':str(root),'commit':commit,'version':args.version,'unit_override':str(path),'host_state_preserved':True}))


if __name__=='__main__':main()
