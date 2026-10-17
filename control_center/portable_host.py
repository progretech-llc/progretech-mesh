"""Portable loopback provider for gateways without the reference workstation stack."""
import json
from pathlib import Path
import threading
from types import SimpleNamespace

from flask import Flask


def create_host(home=None):
    home = Path(home or Path.home())
    state = home / '.progretech-mesh'
    credential = json.loads((state / 'local-access.json').read_text())
    if not isinstance(credential.get('token'), str) or len(credential['token']) < 24:
        raise ValueError('local_auth_missing')
    host = SimpleNamespace(app=Flask(__name__), token=lambda: credential['token'], voice_providers=(), MUTATION_LOCK=threading.Lock(),
                           capabilities={'host.system', 'models.list'})

    def dispatch(action, args):
        if action == 'host.system':
            import psutil
            return {'cpu_percent': psutil.cpu_percent(), 'memory': psutil.virtual_memory()._asdict()}
        if action == 'models.list':
            # Inventory is read-only; provider credentials never cross the relay.
            from urllib.request import Request, build_opener, HTTPRedirectHandler
            class NoRedirect(HTTPRedirectHandler):
                def redirect_request(self, *args, **kwargs): return None
            try:
                with build_opener(NoRedirect).open(Request('http://127.0.0.1:11434/api/tags'), timeout=5) as response:
                    data = json.loads(response.read(1048576))
                return {'provider': 'ollama', 'models': [{'name': m.get('name'), 'size': m.get('size')} for m in data.get('models', [])]}
            except OSError:
                return {'provider': 'ollama', 'available': False, 'models': []}
        raise ValueError('capability_unavailable')

    host.dispatch = dispatch
    from control_center.rend_bridge import install
    host.provider = install(host, home)
    return host


if __name__ == '__main__':
    create_host().app.run(host='127.0.0.1', port=8787, threaded=True)
