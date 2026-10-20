"""Owner-configured runtime discovery and invocation; never execute cloud commands."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid
try:
    import tomllib
except ImportError:
    import tomli as tomllib
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

import yaml


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def runtime_key(value):
    return value if re.fullmatch(r'[A-Za-z0-9_-]{1,50}', value) else 'agent_' + hashlib.sha256(value.encode()).hexdigest()[:24]


def harness_environment():
    return dict(os.environ, AI_AGENT='mesh', HARNESS_AGENT_SESSION='mesh-native-gateway',
                CODEX_THREAD_ID='', CLAUDECODE='', CLAUDE_CODE_SESSION_ID='', TMUX='', TMUX_PANE='')


class Platform:
    def __init__(self, config, home=None):
        self.config = config
        self.home = Path(home or Path.home())
        self.kind = config['platform']
        if self.kind not in {'hermes', 'opencode', 'openwebui', 'openai', 'codex', 'openclaw', 'harness', 'mixed'}:
            raise ValueError('unsupported_platform')
        self.workspace = Path(config['workspace']).expanduser().resolve(strict=True)
        if not self.workspace.is_dir():
            raise ValueError('workspace_required')
        self.rows = {}
        self.members = {}

    def api(self, path, body=None):
        base = (self.config.get('endpoint') or '').rstrip('/')
        u = urlsplit(base)
        if (u.scheme not in {'http', 'https'} or not u.hostname or u.username or u.password
                or u.query or u.fragment or (u.scheme == 'http' and u.hostname not in {'localhost', '127.0.0.1', '::1'})):
            raise ValueError('https_or_loopback_endpoint_required')
        headers = {'Content-Type': 'application/json'}
        if self.config.get('api_key_file'):
            headers['Authorization'] = 'Bearer ' + Path(self.config['api_key_file']).expanduser().read_text().strip()
        if getattr(self, '_native_token', None):
            headers['Authorization'] = 'Bearer ' + self._native_token
        req = Request(base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with build_opener(NoRedirect).open(req, timeout=600 if body else 15) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError('runtime_response_too_large')
        return json.loads(raw)

    def discover(self):
        rows = []
        if self.kind == 'mixed':
            entries = self.config.get('runtimes', [])
            if not isinstance(entries, list) or not 1 <= len(entries) <= 64:
                raise ValueError('bounded_runtime_manifest_required')
            members = {}
            for entry in entries:
                key = entry.get('id') if isinstance(entry, dict) else None
                if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', key) or any(r['runtime_id'] == key for r in rows):
                    raise ValueError('unique_runtime_registration_required')
                if entry.get('platform') == 'mixed':
                    raise ValueError('nested_mixed_platform_forbidden')
                child = Platform({**entry, 'workspace': entry.get('workspace', str(self.workspace))}, self.home)
                try:
                    discovered = child.discover()
                    matches = [r for r in discovered if r['runtime_id'] == entry.get('native_id') or r.get('native_id') == entry.get('native_id')]
                except (OSError, ValueError, subprocess.SubprocessError):
                    matches = []
                if len(matches) != 1:
                    rows.append({'runtime_id': key, 'platform': child.kind, 'native_id': entry.get('native_id'),
                                 'name': str(entry.get('name') or key)[:80], 'role': 'Unavailable native binding',
                                 'model': '', 'memory_provider': 'unverified', 'rag_available': None,
                                 'enabled': False, 'native_state': 'unavailable'})
                    continue
                row = dict(matches[0], runtime_id=key, platform=child.kind,
                           native_runtime_id=matches[0]['runtime_id'], installation_id=key)
                row['name'] = str(entry.get('name') or row['name'])[:80]
                rows.append(row)
                members[key] = (child, matches[0]['runtime_id'])
            self.members = members
        elif self.kind == 'codex':
            root = Path(self.config.get('runtime_home', self.home / '.codex')).expanduser()
            profile = self.config.get('native_id', 'local')
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', profile):
                raise ValueError('invalid_codex_profile')
            path = root / ('config.toml' if profile == 'default' else profile + '.config.toml')
            cfg = tomllib.loads(path.read_text())
            rows.append({'runtime_id': profile, 'native_id': profile, 'name': 'Codex ' + profile,
                         'role': 'Native Codex installation', 'model': cfg.get('model', ''),
                         'memory_provider': 'native configured', 'rag_available': None})
        elif self.kind == 'openclaw':
            root = Path(self.config.get('runtime_home', self.home / '.openclaw')).expanduser()
            cfg = json.loads((root / 'openclaw.json').read_text())
            entries = cfg.get('agents', {}).get('list', [])
            entries = entries or [{'id': 'main'}]
            defaults = cfg.get('agents', {}).get('defaults', {})
            for entry in entries:
                ident = entry.get('id')
                if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', ident):
                    raise ValueError('invalid_openclaw_runtime')
                model = entry.get('model', defaults.get('model', {}))
                rows.append({'runtime_id': ident, 'native_id': ident, 'name': entry.get('name', ident),
                             'role': 'Native OpenClaw agent', 'model': model.get('primary', '') if isinstance(model, dict) else model,
                             'memory_provider': 'native configured', 'rag_available': None})
        elif self.kind == 'harness':
            exe = shutil.which('harness') or str(self.home / '.local/bin/harness')
            result = subprocess.run([exe, 'ps', '--json'], cwd=self.workspace, env=harness_environment(), capture_output=True, text=True, timeout=20)
            if result.returncode:
                raise ValueError('native_harness_unavailable')
            for session in json.loads(result.stdout).get('harnesses', []):
                ident = session.get('id')
                if not isinstance(ident, str):
                    continue
                if self.config.get('native_id') and self.config['native_id'] != ident:
                    continue
                permitted=True
                if self.config.get('native_id'):
                    check=subprocess.run([exe,'followup',ident,'--check','--json'],cwd=self.workspace,env=harness_environment(),capture_output=True,text=True,timeout=20)
                    permitted=check.returncode==0 and json.loads(check.stdout).get('allowed') is True
                rows.append({'runtime_id': runtime_key(ident), 'native_id': ident,
                             'name': session.get('name', ident), 'role': 'Native Harness session',
                             'model': session.get('agent', ''), 'memory_provider': 'native session',
                             'rag_available': None, 'native_state': session.get('state', 'unknown'),
                             'folder': session.get('folder', ''), 'enabled': permitted and session.get('state') not in {'stopped','gone','closed','failed'}})
        elif self.kind == 'hermes':
            root = Path(self.config.get('runtime_home', self.home / '.hermes')).expanduser()
            paths = [('default', root), *((p.name, p) for p in sorted((root / 'profiles').glob('*')) if p.is_dir())]
            for name, path in paths:
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', name) or not (path / 'config.yaml').is_file():
                    continue
                cfg = yaml.safe_load((path / 'config.yaml').read_text()) or {}
                model = cfg.get('model', {})
                model = model.get('default', '') if isinstance(model, dict) else str(model)
                memory = cfg.get('memory', {}).get('provider') or 'native'
                rows.append({'runtime_id': name, 'name': name if name != 'default' else 'Hermes',
                    'role': 'Hermes profile', 'model': model, 'memory_provider': memory,
                    'rag_available': 'shared-knowledge' in cfg.get('mcp_servers', {}),
                    'skills': cfg.get('skills', {}).get('external_dirs', [])})
        elif self.kind == 'opencode':
            root = Path(self.config.get('runtime_home', self.home / '.config/opencode')).expanduser()
            cfg = json.loads((root / 'opencode.json').read_text())
            # Built-in primary agents plus locally configured primary definitions.
            agents = {'build': {}, 'plan': {}, **cfg.get('agent', {})}
            for path in (root / 'agents').glob('*.md'):
                text = path.read_text()
                if text.startswith('---'):
                    agents[path.stem] = yaml.safe_load(text.split('---', 2)[1]) or {}
            for name, data in agents.items():
                if not isinstance(data, dict) or data.get('disable') or data.get('mode') == 'subagent':
                    continue
                rows.append({'runtime_id': runtime_key(name), 'native_id': name, 'name': name,
                    'role': data.get('description', 'OpenCode agent')[:160],
                    'model': data.get('model', cfg.get('model', '')), 'memory_provider':
                    'hindsight' if 'hindsight' in str(cfg.get('plugin', [])) else 'native',
                    'rag_available': 'shared-knowledge' in cfg.get('mcp', {})})
        else:
            models = self.api('/models').get('data', [])
            if not isinstance(models, list) or len(models) > 256:
                raise ValueError('invalid_runtime_roster')
            for item in models:
                name = item.get('id') if isinstance(item, dict) else None
                if not isinstance(name, str) or not 1 <= len(name) <= 256:
                    raise ValueError('invalid_runtime_roster')
                rows.append({'runtime_id': runtime_key(name), 'native_id': name,
                    'name': str(item.get('name') or name)[:80], 'role': 'API model or workspace',
                    'model': name, 'memory_provider': 'upstream managed', 'rag_available': None})
        if not rows or len(rows) > 256:
            raise ValueError('runtime_roster_unavailable')
        for row in rows:
            row['enabled'] = row.get('enabled', True) and self.config.get('enabled', True) and row['runtime_id'] not in self.config.get('excluded_agents', [])
        self.rows = {r['runtime_id']: r for r in rows}
        if len(self.rows) != len(rows):
            raise ValueError('duplicate_runtime_identity')
        return rows

    def complete(self, runtime, body):
        if self.kind == 'mixed':
            member = self.members.get(runtime)
            if not member or not self.rows[runtime]['enabled']:
                raise ValueError('runtime_agent_disabled_or_unavailable')
            return member[0].complete(member[1], body)
        row = self.rows.get(runtime)
        if not row or not row['enabled']:
            raise ValueError('runtime_agent_disabled_or_unavailable')
        if self.kind == 'openclaw':
            root = Path(self.config.get('runtime_home', self.home / '.openclaw')).expanduser()
            cfg = json.loads((root / 'openclaw.json').read_text())
            self.config['endpoint'] = 'http://127.0.0.1:' + str(int(cfg.get('gateway', {}).get('port', 18789))) + '/v1'
            token = cfg.get('gateway', {}).get('auth', {}).get('token')
            if not isinstance(token, str) or not token:
                raise ValueError('native_openclaw_token_required')
            self._native_token = token
            return self.api('/chat/completions', {**body, 'model': 'openclaw:' + row['native_id'], 'stream': False})
        if self.kind in {'openwebui', 'openai'}:
            result = self.api('/chat/completions', {**body, 'model': row['native_id'], 'stream': False})
            if not isinstance(result.get('choices'), list) or not result['choices']:
                raise ValueError('runtime_completion_unavailable')
            return result
        # CLI agents cannot faithfully implement an upstream tool-call protocol.
        if body.get('tools') or any(m.get('role') in {'tool', 'function'} or not isinstance(m.get('content'), str)
                                    for m in body.get('messages', [])):
            raise ValueError('cli_relay_requires_text_messages_without_tools')
        text = '\n\n'.join(m['role'].upper() + ':\n' + m.get('content', '') for m in body['messages'])
        exe = shutil.which(self.kind) or shutil.which(self.kind, path=str(self.home / '.local/bin'))
        if not exe:
            raise ValueError('runtime_executable_required')
        if self.kind == 'harness':
            return self._harness_complete(row, text, exe)
        if self.kind == 'hermes':
            args = [exe, '--profile', runtime, 'chat', '--query-file', '-', '--quiet']
        elif self.kind == 'codex':
            args = [exe, 'exec', '--json', '--cd', str(self.workspace)]
            if row['native_id'] != 'default':
                args += ['--profile', row['native_id']]
            args += ['-']
        else:
            args = [exe, 'run', '--agent', row['native_id'], '--format', 'json']
        env = dict(os.environ)
        # A native permission prompt must fail visibly rather than block unattended work.
        try:
            result = subprocess.run(args, input=text, text=True, encoding='utf-8', errors='replace',
                cwd=self.workspace, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        except subprocess.TimeoutExpired:
            raise ValueError('mesh_runtime_completion_unconfirmed') from None
        if result.returncode:
            raise ValueError('runtime_execution_failed_check_local_logs')
        reply = result.stdout.strip()
        if self.kind == 'codex':
            events = [json.loads(line) for line in reply.splitlines() if line.startswith('{')]
            reply = '\n'.join(e.get('item', {}).get('text', '') for e in events
                              if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'agent_message')
        if self.kind == 'opencode':
            events = [json.loads(line) for line in reply.splitlines() if line.startswith('{')]
            if any(e.get('type') == 'error' for e in events):
                raise ValueError('runtime_execution_failed_check_local_logs')
            reply = '\n'.join(e.get('part', {}).get('text', '') for e in events if e.get('type') == 'text')
        if not reply:
            raise ValueError('runtime_returned_no_answer')
        return {'id': 'chatcmpl-' + os.urandom(12).hex(), 'object': 'chat.completion',
            'model': runtime, 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': reply[-100000:]},
                'finish_reason': 'stop'}]}


    def _harness_complete(self, row, text, exe):
        # Native Harness owns permissions and state; a binding grants no ownership bypass.
        env = harness_environment()
        key = uuid.uuid4().hex
        args = [exe, 'followup', row['native_id'], '--key', key, '--json']
        result = subprocess.run([*args, '--text-file', '-'], input=text, cwd=self.workspace,
                                env=env, capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise ValueError('native_harness_followup_refused_or_unavailable')
        receipt = json.loads(result.stdout)
        deadline = time.monotonic() + 65
        while receipt.get('state') != 'started':
            if receipt.get('state') in {'rejected', 'unknown'} or time.monotonic() > deadline:
                raise ValueError('native_harness_delivery_unconfirmed_do_not_duplicate')
            time.sleep(0.5)
            result = subprocess.run([*args, '--status'], cwd=self.workspace, env=env,
                                    capture_output=True, text=True, timeout=20)
            if result.returncode:
                raise ValueError('native_harness_delivery_unconfirmed_do_not_duplicate')
            receipt = json.loads(result.stdout)
        waited = subprocess.run([exe, 'wait', row['native_id'], '--timeout', '8m', '--json'],
                                cwd=self.workspace, env=env, capture_output=True, text=True, timeout=490)
        if waited.returncode == 124:
            raise ValueError('native_harness_still_working_do_not_duplicate')
        if waited.returncode:
            raise ValueError('native_harness_result_unconfirmed')
        result = subprocess.run([exe, 'show', row['native_id'], '--json'], cwd=self.workspace,
                                env=env, capture_output=True, text=True, timeout=20)
        reply = json.loads(result.stdout).get('answer') if result.returncode == 0 else None
        if not reply:
            raise ValueError('native_harness_returned_no_answer')
        return {'id': 'chatcmpl-' + os.urandom(12).hex(), 'object': 'chat.completion',
                'model': row['runtime_id'], 'choices': [{'index': 0, 'message':
                    {'role': 'assistant', 'content': reply}, 'finish_reason': 'stop'}]}
