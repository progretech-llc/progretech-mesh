"""Owner-configured runtime discovery and invocation; never execute cloud commands."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

import yaml


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def runtime_key(value):
    return value if re.fullmatch(r'[A-Za-z0-9_-]{1,50}', value) else 'agent_' + hashlib.sha256(value.encode()).hexdigest()[:24]


class Platform:
    def __init__(self, config, home=None):
        self.config = config
        self.home = Path(home or Path.home())
        self.kind = config['platform']
        if self.kind not in {'hermes', 'opencode', 'openwebui', 'openai'}:
            raise ValueError('unsupported_platform')
        self.workspace = Path(config['workspace']).expanduser().resolve(strict=True)
        if not self.workspace.is_dir():
            raise ValueError('workspace_required')
        self.rows = {}

    def api(self, path, body=None):
        base = (self.config.get('endpoint') or '').rstrip('/')
        u = urlsplit(base)
        if (u.scheme not in {'http', 'https'} or not u.hostname or u.username or u.password
                or u.query or u.fragment or (u.scheme == 'http' and u.hostname not in {'localhost', '127.0.0.1', '::1'})):
            raise ValueError('https_or_loopback_endpoint_required')
        headers = {'Content-Type': 'application/json'}
        if self.config.get('api_key_file'):
            headers['Authorization'] = 'Bearer ' + Path(self.config['api_key_file']).expanduser().read_text().strip()
        req = Request(base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with build_opener(NoRedirect).open(req, timeout=600 if body else 15) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError('runtime_response_too_large')
        return json.loads(raw)

    def discover(self):
        rows = []
        if self.kind == 'hermes':
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
            row['enabled'] = row['runtime_id'] not in self.config.get('excluded_agents', [])
        self.rows = {r['runtime_id']: r for r in rows}
        if len(self.rows) != len(rows):
            raise ValueError('duplicate_runtime_identity')
        return rows

    def complete(self, runtime, body):
        row = self.rows.get(runtime)
        if not row or not row['enabled']:
            raise ValueError('runtime_agent_disabled_or_unavailable')
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
        if self.kind == 'hermes':
            args = [exe, '--profile', runtime, 'chat', '--query-file', '-', '--quiet']
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
