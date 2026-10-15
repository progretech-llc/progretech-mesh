"""Desktop-owned loopback UI. No cloud login, gateway, signing or CodeSeal."""
import json
import os
import secrets
import sys
import subprocess
from pathlib import Path
from flask import Flask, abort, jsonify, render_template, request
from offline.registry import Registry

ROOT = Path(__file__).resolve().parent.parent


def create_app(home=None, token=None, include_starter=True):
    home = Path(home or Path.home()).resolve()
    registry = Registry(home)
    app = Flask(__name__, template_folder=str(ROOT / 'templates'), static_folder=str(ROOT / 'static'))
    app.config.update(MAX_CONTENT_LENGTH=65536, LOCAL_HOME=home, LOCAL_TOKEN=token or secrets.token_urlsafe(32))
    from control_center.factory_jobs import _write
    config = home / '.progretech-mesh/factory-runtimes.json'
    starter = ROOT / 'runtimes/models/starter.gguf'
    if not starter.is_file(): starter = ROOT / 'packaging/runtime-cache/models/starter.gguf'
    if include_starter and starter.is_file() and not config.exists():
        _write(config, {'crewai':{'enabled':True, 'roles':['offline'], 'python':sys.executable,
            'workspace':str(registry.root), 'model':'local/gguf', 'gguf':str(starter), 'bundled_worker':True, 'local_bindings':{}}})

    @app.before_request
    def local_only():
        if request.remote_addr not in {'127.0.0.1', '::1'}: abort(403)
        if request.host.split(':')[0] != '127.0.0.1': abort(403)
        if not secrets.compare_digest(request.cookies.get('mesh_local', ''), app.config['LOCAL_TOKEN']): abort(403)
        if request.method != 'GET':
            origin = request.headers.get('Origin')
            if origin and origin != request.host_url.rstrip('/'): abort(403)
            if not request.is_json: abort(415)
        if request.headers.get('Sec-Fetch-Site') == 'cross-site': abort(403)

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        return response

    @app.errorhandler(ValueError)
    def invalid(exc): return jsonify(ok=False, error=str(exc)), 400

    @app.errorhandler(TimeoutError)
    @app.errorhandler(subprocess.TimeoutExpired)
    def timeout(exc): return jsonify(ok=False, error='local_runtime_timed_out'), 504

    @app.get('/')
    @app.get('/mission-control')
    def fleet(): return render_template('offline.html')

    @app.get('/factory')
    def factory():
        return render_template('office.html', hosts=[{'id':'desktop', 'name':'This computer', 'verified':True, 'connected':True}], offline=True)

    @app.get('/api/local/agents')
    def agents(): return jsonify(ok=True, agents=registry.all())

    @app.get('/api/local/discover')
    def discover(): return jsonify(ok=True, candidates=registry.discover())

    @app.get('/api/local/gateway-agents')
    def gateway_agents(): return jsonify(ok=True, **registry.discover_gateway())

    @app.post('/api/local/agents')
    def add(): return jsonify(ok=True, agent=registry.add(request.get_json()))

    @app.post('/api/local/agents/<aid>/remove')
    def remove(aid):
        registry.remove(aid)
        return jsonify(ok=True)

    @app.post('/api/local/agents/<aid>/ask')
    def ask(aid):
        return jsonify(ok=True, **registry.ask(aid, request.get_json().get('question')))

    @app.get('/api/local/settings')
    def settings():
        from control_center.factory_jobs import _config
        cfg = _config(home).get('crewai', {})
        return jsonify(ok=True, gguf=cfg.get('gguf', ''), bindings=cfg.get('local_bindings', {}))

    @app.post('/api/local/settings')
    def save_settings():
        from control_center.factory_jobs import _write
        body = request.get_json()
        model = Path(body.get('gguf', '')).expanduser()
        if not model.is_absolute() or not model.is_file() or model.suffix.lower() != '.gguf': raise ValueError('select_local_gguf_model')
        bindings = body.get('bindings', {})
        from control_center.office import engine
        ids = {a['id'] for a in engine(home, 'offline', 'snapshot')['snapshot']['agents'] if not a['isDirector']}
        if not isinstance(bindings, dict) or set(bindings) - ids: raise ValueError('unknown_office_worker')
        for aid in bindings.values(): registry.get(aid)
        config = {'crewai': {'enabled': True, 'roles':['offline'], 'python':sys.executable,
            'workspace':str(registry.root), 'model':'local/gguf', 'gguf':str(model.resolve()),
            'bundled_worker':True, 'local_bindings':bindings}}
        # Offline uses its own home, so it cannot replace a hosted runtime's configuration.
        _write(home / '.progretech-mesh/factory-runtimes.json', config)
        return jsonify(ok=True)

    @app.get('/agents/<aid>/task-board')
    def task_board(aid):
        record=registry.get(aid)
        return render_template('task_board.html',agent=dict(record,id=aid),build_id='offline')

    @app.post('/api/agents/<aid>/management')
    def memory(aid):
        body=request.get_json()
        if not isinstance(body,dict) or set(body)-{'action','args'}: raise ValueError('invalid_request')
        from control_center.memory_search import ACTIONS as MEMORY_ACTIONS
        from control_center.specklet import ACTIONS as SPECKLET_ACTIONS
        from control_center.management import validate_management as validate
        ACTIONS=MEMORY_ACTIONS|SPECKLET_ACTIONS
        action=body.get('action');args=body.get('args',{})
        if action not in ACTIONS: raise ValueError('local_action_unavailable')
        validate(action,args)
        record=registry.get(aid)
        if record['kind']!='openclaw':
            if action=='memory.status': return jsonify(ok=True,result={'available':False,'shared':False})
            raise ValueError('specklet_unavailable' if action.startswith('specklet.') else 'hindsight_unavailable')
        from mesh_local_host import LocalHost
        host=LocalHost()
        try:
            rows=host.call('/api/mesh/control-center/agents?gateway_id=rend')['agents']
            target='rend--'+record['runtime_id']
            if not any(r.get('id')==target for r in rows): raise ValueError('agent_binding_required')
            return jsonify(host.call('/api/mesh/control-center',{'agent_id':target,'action':action,'args':args}))
        except Exception:
            if action=='memory.status': return jsonify(ok=True,result={'available':False,'shared':False})
            raise ValueError('specklet_unavailable' if action.startswith('specklet.') else 'hindsight_unavailable')

    @app.post('/api/agents/<aid>/office')
    def office(aid):
        if aid != 'desktop': raise ValueError('local_office_not_found')
        from control_center.office import dispatch_office
        return jsonify(ok=True, result=dispatch_office(home, 'offline', request.get_json()))

    return app
