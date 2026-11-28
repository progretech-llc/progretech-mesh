#!/usr/bin/env python3
"""Attach one native runtime to the owner's already authenticated Mesh workstation."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def origin(value):
    u = urlsplit(value)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('', '/'):
        raise ValueError('https_mesh_origin_required')
    return value.rstrip('/')


def load_binding(payload_file, home=None):
    text = Path(payload_file).read_text().strip()
    if len(text) > 16384 or not text.startswith('PTMR1:'): raise ValueError('runtime_invitation_required')
    invitation = json.loads(base64.b64decode(text[6:], altchars=b'-_', validate=True))
    state = Path(home or Path.home())/'.progretech-mesh/platform'
    config = json.loads((state/'connector.json').read_text())
    # Never send an existing credential to an origin supplied by an untrusted payload.
    if origin(invitation['mesh']) != origin(config['mesh']) or invitation['gateway'] != config['agent_id']:
        raise ValueError('invitation_does_not_match_existing_gateway')
    if invitation.get('platform') not in {'hermes','opencode','codex','openclaw','harness'}:
        raise ValueError('unsupported_platform')
    for key in ('invitation','token'):
        if not isinstance(invitation.get(key),str) or not invitation[key] or len(invitation[key]) > 128:
            raise ValueError('invalid_invitation')
    return invitation, config, state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload-file', required=True, type=Path)
    parser.add_argument('--native-id', required=True)
    args = parser.parse_args()
    invitation, config, state = load_binding(args.payload_file)
    python = state/('venv/Scripts/python.exe' if os.name == 'nt' else 'venv/bin/python')
    if Path(sys.executable).resolve() != python.resolve():
        if not python.is_file(): raise ValueError('update_existing_connector_first')
        result = subprocess.run([str(python),str(Path(__file__).resolve()),'--payload-file',str(args.payload_file.resolve()),'--native-id',args.native_id])
        return result.returncode
    if not (state/'source/gateway/platform_register.py').is_file(): raise ValueError('update_existing_connector_first')
    sys.path.insert(0,str(state/'source'))
    from gateway.platform_register import candidate, register, harness_control
    from gateway.platforms import Platform
    updated, ident = candidate(config, invitation['platform'], args.native_id, invitation.get('name'))
    probe = Platform(updated);probe.discover()
    if invitation['platform']=='harness':harness_control(args.native_id)
    elif not probe.rows.get(ident,{}).get('enabled'): raise ValueError('native_binding_not_ready')
    body = {'agent_id':config['agent_id'],'device_credential':config['device_credential'],'native_id':args.native_id}
    req = Request(origin(invitation['mesh'])+'/api/runtime-enrollment/'+invitation['invitation']+'/redeem',
        data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+invitation['token']})
    with build_opener(NoRedirect).open(req,timeout=30) as response: receipt=json.load(response)
    if not receipt.get('ok') or receipt.get('native_id') != args.native_id or receipt.get('platform') != invitation['platform']:
        raise ValueError('registration_receipt_mismatch')
    if invitation['platform']=='harness':harness_control(args.native_id,grant=True)
    registered=register(state/'connector.json',invitation['platform'],args.native_id,receipt['name'])
    req=Request(origin(invitation['mesh'])+'/api/runtime-enrollment/'+invitation['invitation']+'/complete',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+invitation['token']})
    with build_opener(NoRedirect).open(req,timeout=30) as response:ack=json.load(response)
    if not ack.get('ok'):raise ValueError('registration_acknowledgement_unconfirmed')
    print(json.dumps(registered))
    print('Added to the existing gateway. Its next roster refresh will expose this entry; keep native session ownership intact.')
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except Exception as error:
        # Exceptions from HTTP can contain private request context. Emit safe classification only.
        print('Runtime registration failed: '+(str(error) if isinstance(error,ValueError) else type(error).__name__),file=sys.stderr)
        sys.exit(1)
