"""Start the existing loopback bridge with the per-agent extension installed."""
import importlib.util
from pathlib import Path

from control_center.rend_bridge import install


def main():
    path = Path.home() / 'software-factory-setup/factory-control/host/factory_host.py'
    spec = importlib.util.spec_from_file_location('rend_factory_host', path)
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    install(host)
    @host.app.get('/api/factory/workday')
    def workday():
        import json
        try:data=json.loads((Path.home()/'.local/state/progretech-workday/activity.json').read_text())
        except (OSError,ValueError):data={'agents':{},'tasks':[]}
        return host.jsonify(ok=True,result=data)
    host.app.run(host='127.0.0.1', port=8787, threaded=True)


if __name__ == '__main__':
    main()
