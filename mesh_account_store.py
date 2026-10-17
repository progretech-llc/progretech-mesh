"""Durable public enrollment/configuration; live activity and credentials stay ephemeral."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading

FIELDS = frozenset('id owner_id name role public_key codeseal_evidence fingerprint trust_state trust_valid trust_reason enrolled_at control_center_gateway gateway_enrollment gateway_linked gateway_candidate_id runtime_id office_worker office_agent_id office_archived is_orchestrator account_profile identity_device_id identity_proof'.split())


def configuration(registry):
    return json.loads(json.dumps({aid: {k: v for k, v in row.items() if k in FIELDS}
            for aid, row in list(registry.items()) if row.get('owner_id') and not row.get('local_host_binding')}))


class AccountStore:
    def __init__(self, backend, path=None):
        self.lock = threading.RLock()
        self.backend = backend
        self.previous = {}
        if backend == 'sqlite':
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.db = sqlite3.connect(path, check_same_thread=False)
            path.chmod(0o600)
            self.db.execute('CREATE TABLE IF NOT EXISTS agents (id TEXT PRIMARY KEY, config TEXT NOT NULL)')
        elif backend == 'firestore':
            import firebase_admin
            from firebase_admin import firestore
            if not firebase_admin._apps:
                firebase_admin.initialize_app(options={'projectId': os.environ.get('MESH_FIREBASE_PROJECT_ID') or os.environ.get('GOOGLE_CLOUD_PROJECT')})
            self.collection = firestore.client().collection('mesh_agent_configuration')
        else:
            raise ValueError('invalid_mesh_account_store')

    def restore(self, registry):
        with self.lock:
            if self.backend == 'sqlite':
                rows = [json.loads(row[0]) for row in self.db.execute('SELECT config FROM agents')]
            else:
                rows = [doc.to_dict() for doc in self.collection.stream()]
            for row in rows:
                if not isinstance(row.get('id'), str) or not row.get('owner_id'):
                    raise ValueError('invalid_saved_agent_configuration')
                row = {k: v for k, v in row.items() if k in FIELDS}
                registry.setdefault(row['id'], {**row, 'transport': 'not-connected', 'state': 'offline',
                    'model': 'Unknown', 'task': 'Awaiting gateway', 'phase': 'Saved to your account; waiting for gateway',
                    'last_heartbeat': None, 'telemetry': {}})
            self.previous = {row['id']: row for row in rows}

    def save(self, registry):
        with self.lock:
            current = configuration(registry)
            changed = {aid: row for aid, row in current.items() if self.previous.get(aid) != row}
            removed = self.previous.keys() - current.keys()
            if not changed and not removed:
                return
            if self.backend == 'sqlite':
                with self.db:
                    self.db.executemany('INSERT OR REPLACE INTO agents VALUES (?, ?)',
                                        [(aid, json.dumps(row)) for aid, row in changed.items()])
                    self.db.executemany('DELETE FROM agents WHERE id = ?', [(aid,) for aid in removed])
            else:
                for aid, row in changed.items():
                    self.collection.document(hashlib.sha256(aid.encode()).hexdigest()).set(row)
                for aid in removed:
                    self.collection.document(hashlib.sha256(aid.encode()).hexdigest()).delete()
            self.previous = current
