"""Explicit host-configured CrewAI/OpenHands jobs; cloud cannot choose commands or paths."""
import sys
import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from control_center.file_lock import lock

_LOCK = threading.Lock()


def _config(home):
    path = Path(home) / '.progretech-mesh/factory-runtimes.json'
    return json.loads(path.read_text()) if path.is_file() else {}


def _write(path, value):
    tmp = path.with_suffix('.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream: json.dump(value, stream)
    tmp.replace(path)


def dispatch_factory(home, role, action, args, office_id=None):
    if action == 'factory.office':
        from control_center.office import dispatch_office
        return dispatch_office(home, role, args, office_id)
    cfg = _config(home)
    from control_center.office import namespace
    office_role = namespace(role, office_id)
    root = Path(home) / '.progretech-mesh/factory-jobs' / office_role
    if action == 'factory.providers':
        return {'providers': [{'id': name, 'configured': bool(cfg.get(name, {}).get('enabled')),
                               'setup': 'docs/AGENT_MANAGEMENT.md'} for name in ('crewai', 'openhands')]}
    if action == 'factory.job':
        path = root / (args['job_id'] + '.json')
        if not path.is_file(): raise ValueError('factory_job_not_found')
        result = json.loads(path.read_text())
        output = root / (args['job_id'] + '.output.txt')
        if output.is_file():
            result['result'] = output.read_text()[-6000:]
        return result
    provider = args['provider']
    settings = cfg.get(provider, {})
    if not settings.get('enabled') or role not in settings.get('roles', []):
        raise ValueError('factory_provider_not_configured_for_role')
    python = Path(settings.get('python', ''))
    workspace = Path(settings.get('workspace', ''))
    if not python.is_absolute() or not python.is_file() or not workspace.is_absolute() or not workspace.is_dir():
        raise ValueError('factory_runtime_paths_invalid')
    model = settings.get('model')
    if not isinstance(model, str) or not model: raise ValueError('factory_model_required')
    if not _LOCK.acquire(blocking=False): raise ValueError('factory_workstation_busy')
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        job_id = uuid.uuid4().hex
        path = root / (job_id + '.json')
        job = {'job_id': job_id, 'provider': provider, 'role': role, 'state': 'queued', 'created_at': time.time()}
        office = None
        if args.get('office_task'):
            from control_center.office import engine
            office = engine(home, office_role, 'begin', {'id': args['office_task']})['result']
            job['office_task'] = args['office_task']
        _write(path, job)
    except Exception:
        _LOCK.release()
        raise
    def run():
        try:
            lockpath = Path(home) / '.progretech-mesh/factory-admission.lock'
            with lockpath.open('a+') as admission:
                try: lock(admission, blocking=False)
                except BlockingIOError:
                    job.update(state='failed', error='factory_workstation_busy'); return
                job['state'] = 'running'; _write(path, job)
                env = os.environ.copy()
                env['PYTHONUTF8'] = '1'
                env['MESH_FACTORY_MODEL'] = model
                env['MESH_FACTORY_BASE_URL'] = str(settings.get('base_url', ''))
                secret_env = settings.get('api_key_env', 'MESH_FACTORY_API_KEY')
                env['MESH_FACTORY_API_KEY'] = os.environ.get(secret_env, '')
                env['MESH_FACTORY_GGUF'] = str(settings.get('gguf', ''))
                command = [str(python), str(Path(__file__).with_name('factory_worker.py')), provider]
                if getattr(sys, 'frozen', False) and settings.get('bundled_worker'):
                    command = [sys.executable, '--factory-worker', provider]
                result = subprocess.run(command,
                    input=json.dumps({'task': args['task'], 'workspace': str(workspace), 'office': office, 'home': str(home), 'role': office_role,
                        'local_bindings': settings.get('local_bindings', {})}), text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='replace', env=env, cwd=workspace,
                    timeout=1800, check=False)
                job.update(state='completed' if result.returncode == 0 else 'failed', returncode=result.returncode)
                # Result text stays host-local. Status never forwards arbitrary logs or credentials.
                output = root / (job_id + '.output.txt')
                output.write_text(result.stdout[-65536:])
                output.chmod(0o600)
                diagnostic = root / (job_id + '.stderr.txt')
                diagnostic.write_text(result.stderr[-65536:]); diagnostic.chmod(0o600)
                if result.returncode: job['error'] = 'factory_runtime_failed; inspect host-local runtime logs'
        except subprocess.TimeoutExpired: job.update(state='failed', error='factory_timeout')
        except Exception: job.update(state='failed', error='factory_runtime_unavailable')
        finally:
            if office:
                from control_center.office import engine
                try:
                    output_path = root / (job_id + '.output.txt')
                    summary = output_path.read_text()[-6000:] if output_path.exists() and job.get('state') == 'completed' else job.get('error', 'Mission interrupted')
                    engine(home, office_role, 'finish', {'id': args['office_task'], 'ok': job.get('state') == 'completed', 'result': summary})
                except Exception:
                    job['office_error'] = 'office_result_update_failed'
            try:
                job['finished_at'] = time.time(); _write(path, job)
            finally:
                _LOCK.release()
    threading.Thread(target=run, daemon=True).start()
    return {'job_id': job_id, 'state': 'queued'}
