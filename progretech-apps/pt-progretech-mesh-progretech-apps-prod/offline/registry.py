"""Local runtime references. Never import credentials, histories or private memory."""
import json
import os
import shutil
import sqlite3
import subprocess
import uuid
import re
import tempfile
import hashlib
from contextlib import contextmanager
from pathlib import Path

KINDS = {'openclaw', 'hermes', 'claude', 'pycharm'}
MAX_GATEWAY_ROSTER_BYTES = 16 * 1024 * 1024


def runtime_executable(kind, source_home):
    """Resolve accepted CLIs even in a desktop/systemd login without shell PATH."""
    if kind not in KINDS - {'pycharm'}:
        return None
    executable = shutil.which(kind)
    if executable:
        return executable
    # Only the owner's standard install directory; never scan arbitrary projects
    # or execute a candidate to decide whether it is a supported runtime.
    return shutil.which(kind, path=str(Path(source_home) / '.local' / 'bin'))


class Registry:
    def __init__(self, home):
        self.home = Path(home)
        self.root = self.home / '.progretech-mesh/offline'
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / 'agents.sqlite3'
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS agents (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db: yield db
        finally:
            db.close()

    def all(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT body FROM agents ORDER BY rowid')]

    def get(self, aid):
        with self.connect() as db:
            row = db.execute('SELECT body FROM agents WHERE id=?', (aid,)).fetchone()
        if not row: raise ValueError('local_agent_not_found')
        return json.loads(row[0])

    def add(self, body):
        allowed = {'kind', 'name', 'workspace', 'executable', 'runtime_id', 'entrypoint', 'confirmed', 'intermediary'}
        if not isinstance(body, dict) or set(body) - allowed or body.get('confirmed') is not True:
            raise ValueError('confirm_personally_owned_runtime')
        if body.get('intermediary') is not True:
            raise ValueError('accept_mesh_intermediary_terms')
        kind = body.get('kind')
        if kind not in KINDS: raise ValueError('unsupported_local_runtime')
        name = body.get('name', '').strip()
        if not 1 <= len(name) <= 80: raise ValueError('agent_name_required')
        workspace = Path(body.get('workspace', '')).expanduser()
        executable = Path(body.get('executable', '')).expanduser()
        if not workspace.is_absolute() or not workspace.is_dir(): raise ValueError('workspace_required')
        if not executable.is_absolute() or not executable.is_file(): raise ValueError('runtime_executable_required')
        if os.name != 'nt' and not os.access(executable, os.X_OK): raise ValueError('runtime_not_executable')
        runtime_id = body.get('runtime_id', 'main')
        if not isinstance(runtime_id, str) or not re.fullmatch('[A-Za-z0-9_][A-Za-z0-9_.-]{0,79}', runtime_id):
            raise ValueError('invalid_runtime_identity')
        entrypoint = body.get('entrypoint', '')
        if kind == 'pycharm':
            script = Path(entrypoint).expanduser()
            if not script.is_absolute() or not script.is_file() or script.suffix != '.py': raise ValueError('python_agent_entrypoint_required')
            entrypoint = str(script.resolve())
        row = {'id': 'local-' + uuid.uuid4().hex[:16], 'kind': kind, 'name': name,
            'workspace': str(workspace.resolve()), 'executable': str(executable.resolve()),
            'runtime_id': runtime_id, 'entrypoint': entrypoint, 'awake': False, 'local': True,
            'consent': {'personally_owned':True, 'mesh_intermediary':True}}
        # Serialize selection and insertion so two windows cannot import the same
        # local runtime twice. Different Python scripts remain distinct agents.
        def binding(agent):
            return (agent['kind'], agent['executable'], agent['runtime_id'],
                agent['workspace'] if agent['kind'] in {'claude', 'pycharm'} else '',
                agent.get('entrypoint', '') if agent['kind'] == 'pycharm' else '')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if any(binding(json.loads(existing[0])) == binding(row)
                   for existing in db.execute('SELECT body FROM agents')):
                raise ValueError('local_runtime_already_added')
            db.execute('INSERT INTO agents VALUES (?,?)', (row['id'], json.dumps(row)))
        return row

    def save(self, row):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO agents VALUES (?,?)', (row['id'], json.dumps(row)))

    def remove(self, aid):
        self.get(aid)
        with self.connect() as db: db.execute('DELETE FROM agents WHERE id=?', (aid,))

    def discover(self, source_home=None):
        candidates = []
        source_home = Path(source_home or Path.home())
        executable = runtime_executable('openclaw', source_home)
        config = source_home / '.openclaw/openclaw.json'
        if executable and config.is_file():
            try:
                source = json.loads(config.read_text())
                agents = source.get('agents', {}).get('entries', source.get('agents', {}).get('list', []))
                if isinstance(agents, dict): agents = [dict(value, id=key) for key, value in agents.items()]
                for item in agents:
                    if not isinstance(item, dict): continue
                    workspace = item.get('workspace') or source.get('agents', {}).get('defaults', {}).get('workspace')
                    if workspace:
                        candidates.append({'kind': 'openclaw', 'name': item.get('name') or item.get('id', 'main'),
                            'runtime_id': item.get('id', 'main'), 'workspace': workspace, 'executable': executable})
            except (OSError, ValueError, TypeError): pass
        for kind in ('hermes', 'claude'):
            executable = runtime_executable(kind, source_home)
            if executable:
                candidates.append({'kind': kind, 'name': kind.capitalize(), 'runtime_id': 'default' if kind == 'hermes' else 'main',
                    'workspace': str(source_home), 'executable': executable})
                if kind == 'hermes':
                    profiles = source_home / '.hermes/profiles'
                    if profiles.is_dir():
                        for profile in profiles.iterdir():
                            if profile.is_dir() and (profile/'config.yaml').is_file():
                                candidates.append({'kind':'hermes','name':profile.name,'runtime_id':profile.name,
                                    'workspace':str(source_home),'executable':executable})
        return candidates

    def discover_gateway(self, source_home=None, run=subprocess.run):
        source_home = Path(source_home or Path.home())
        executable = runtime_executable('openclaw', source_home)
        if not executable: return {'available':False, 'candidates':[], 'error':'openclaw_runtime_not_found'}
        port = 18789
        config = source_home / '.openclaw/openclaw.json'
        if config.is_file():
            try:
                configured = json.loads(config.read_text()).get('gateway', {}).get('port', port)
                if type(configured) is int and 1 <= configured <= 65535: port = configured
            except (OSError, ValueError, TypeError, AttributeError): pass
        try:
            response = run([executable, 'gateway', 'call', 'agents.list', '--expect-url',
                'ws://127.0.0.1:' + str(port), '--json'], capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=15, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            # OpenClaw includes inline avatar data in agents.list. Keep a strict
            # response ceiling, but leave enough room for the validated 256-agent
            # roster; only id, name and workspace are retained below.
            if response.returncode or len(response.stdout.encode("utf-8")) > MAX_GATEWAY_ROSTER_BYTES: raise ValueError()
            payload = json.loads(response.stdout)
            agents = payload.get('agents')
            if not isinstance(agents, list) or len(agents) > 256: raise ValueError()
            linked = {(a['kind'], a['runtime_id'], a['executable']) for a in self.all()}
            candidates, seen = [], set()
            for agent in agents:
                if not isinstance(agent, dict): raise ValueError()
                rid, workspace = agent.get('id'), agent.get('workspace')
                if not isinstance(rid, str) or not re.fullmatch('[A-Za-z0-9_][A-Za-z0-9_.-]{0,79}', rid): raise ValueError()
                if not isinstance(workspace, str) or not Path(workspace).is_absolute(): raise ValueError()
                if rid in seen: raise ValueError()
                seen.add(rid)
                if ('openclaw', rid, str(Path(executable).resolve())) in linked: continue
                name = agent.get('name') or rid
                if not isinstance(name, str) or not 1 <= len(name) <= 80: raise ValueError()
                candidates.append({'kind':'openclaw', 'name':name, 'runtime_id':rid,
                    'workspace':workspace, 'executable':executable, 'source':'gateway'})
            return {'available':True, 'candidates':candidates}
        except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError):
            return {'available':False, 'candidates':[], 'error':'local_gateway_unavailable'}

    def ask(self, aid, question):
        from control_center.file_lock import lock, unlock
        row = self.get(aid)
        identity = '|'.join([row['kind'], row['executable'], row['runtime_id'],
            row['workspace'] if row['kind'] in {'claude','pycharm'} else ''])
        locks = self.root / 'runtime-locks'; locks.mkdir(exist_ok=True, mode=0o700)
        path = locks / (hashlib.sha256(identity.encode()).hexdigest() + '.lock')
        with path.open('a+') as guard:
            try: lock(guard, blocking=False)
            except BlockingIOError: raise ValueError('local_agent_is_busy') from None
            try: return self._ask(aid, question)
            finally: unlock(guard)

    def _ask(self, aid, question):
        if not isinstance(question, str) or not question.strip() or len(question) > 8000:
            raise ValueError('question_required')
        row = self.get(aid)
        exe = row['executable']
        # Questions never enter a shell command or process-list argument, including
        # Windows .cmd launchers. Source runtime paths remain user-selected.
        with tempfile.TemporaryDirectory(dir=self.root) as prompts:
            prompt = Path(prompts) / 'question.txt'
            prompt.write_text(question, encoding='utf-8'); prompt.chmod(0o600)
            stdin = None
            if row['kind'] == 'openclaw':
                args = [exe, 'agent', '--local', '--agent', row['runtime_id'], '--message-file', str(prompt), '--json']
            elif row['kind'] == 'hermes':
                profile = 'default' if row['runtime_id'] == 'main' else row['runtime_id']
                args = [exe, '--profile', profile, 'chat', '--query-file', str(prompt)]
            elif row['kind'] == 'claude':
                args = [exe, '-p', '--output-format', 'json']; stdin = question
            else:
                args = [exe, row['entrypoint']]; stdin = json.dumps({'question': question})
            result = subprocess.run(args, input=stdin, text=True, encoding='utf-8', errors='replace',
                cwd=row['workspace'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300, check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode: raise ValueError('local_runtime_failed; inspect your runtime configuration')
        answer = result.stdout.strip()[-32000:]
        if not answer: raise ValueError('local_runtime_returned_no_answer')
        try:
            parsed = json.loads(answer)
            if row['kind'] == 'claude': answer = parsed.get('result') or answer
            elif row['kind'] == 'openclaw':
                payloads = parsed.get('result', parsed).get('payloads', [])
                answer = '\n'.join(p.get('text', '') for p in payloads) or answer
        except (ValueError, AttributeError, TypeError): pass
        row['awake'] = True
        self.save(row)
        return {'answer': answer, 'agent': row}
