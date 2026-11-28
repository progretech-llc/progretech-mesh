"""Observed native roster for Mission Control; no product-specific role cards."""
import json
import re
from pathlib import Path


def agent_entries(config):
    agents = config.get('agents', {})
    entries = agents.get('entries')
    if entries is None:
        rows = agents.get('list')
        entries = {row['id']: row for row in rows if isinstance(row, dict) and isinstance(row.get('id'), str)} if isinstance(rows, list) else {'main': {}}
    if not isinstance(entries, dict):
        raise ValueError('invalid_gateway_roster')
    return {key: value for key, value in entries.items()
            if isinstance(key, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', key) and isinstance(value, dict)}


def native_roster(home):
    home = Path(home)
    config = json.loads((home / '.openclaw/openclaw.json').read_text())
    agents = config.get('agents', {})
    defaults = agents.get('defaults', {})
    valid = agent_entries(config)
    output = []
    for runtime, value in valid.items():
        permissions = dict(defaults.get('subagents') or {})
        permissions.update(value.get('subagents') or {})
        allowed = permissions.get('allowAgents', [])
        targets = [key for key in valid if key != runtime
                   and isinstance(allowed, list) and ('*' in allowed or key in allowed)]
        workspace = value.get('workspace', defaults.get('workspace'))
        path = Path(workspace).expanduser() if isinstance(workspace, str) and workspace else None
        # These are the existing mailbox adapter identities, not inferred mail accounts.
        mailbox = {'main': 'rend', 'researcher': 'lyra', 'coder': 'mak'}.get(runtime)
        output.append({'id': runtime, 'runtime_id': runtime,
                       'name': value.get('name') or runtime,
                       'role': (value.get('identity') or {}).get('theme', ''),
                       'model': value.get('model', defaults.get('model')),
                       'controller': bool(targets), 'delegation_targets': targets,
                       'controller_basis': 'Configured delegation to other current gateway agents',
                       'workspace_ready': path.is_dir() if path else None,
                       'hardware_status': 'Runs on the selected gateway',
                       'mail_identity': mailbox})
    return output
