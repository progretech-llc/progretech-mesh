import json
from mesh_account_store import AccountStore


def test_saved_accounts_survive_restart_without_live_state_or_secrets(tmp_path):
    path = tmp_path / 'accounts.sqlite3'
    registry = {
        'host': {'id': 'host', 'owner_id': 'alice', 'name': 'Gateway', 'trust_state': 'verified',
                 'transport': 'connected', 'state': 'working', 'last_heartbeat': 'now',
                 'private_key': 'NEVER STORE', 'device_credential': 'NEVER STORE',
                 'account_profile': {'models': ['local/model']}},
        'host--coder': {'id': 'host--coder', 'owner_id': 'alice', 'name': 'Coder',
                        'control_center_gateway': 'host', 'gateway_linked': True, 'runtime_id': 'coder'},
        'second': {'id': 'second', 'owner_id': 'bob', 'name': 'Bob gateway'},
        'demo': {'id': 'demo', 'name': 'Unowned demo'},
    }
    store = AccountStore('sqlite', path)
    store.save(registry)
    restored = {}
    AccountStore('sqlite', path).restore(restored)
    assert set(restored) == {'host', 'host--coder', 'second'}
    assert restored['host']['owner_id'] == 'alice'
    assert restored['second']['owner_id'] == 'bob'
    assert restored['host']['account_profile']['models'] == ['local/model']
    assert restored['host--coder']['control_center_gateway'] == 'host'
    assert all(row['transport'] == 'not-connected' and row['state'] == 'offline' for row in restored.values())
    assert 'NEVER STORE' not in json.dumps(restored)
    assert not path.stat().st_mode & 0o077
    # Nested edits and removals must reach durable storage too.
    registry['host']['account_profile']['models'].append('second/model')
    del registry['host--coder']
    store.save(registry)
    again = {}
    AccountStore('sqlite', path).restore(again)
    assert 'host--coder' not in again
    assert again['host']['account_profile']['models'] == ['local/model', 'second/model']


def test_firestore_restores_account_configuration_and_removal(monkeypatch):
    import firebase_admin
    from firebase_admin import firestore
    from types import SimpleNamespace
    rows = {}
    class Collection:
        def stream(self):
            return [SimpleNamespace(to_dict=lambda row=row: row) for row in rows.values()]
        def document(self, key):
            return SimpleNamespace(set=lambda row: rows.__setitem__(key, row.copy()), delete=lambda: rows.pop(key))
    monkeypatch.setattr(firebase_admin, 'initialize_app', lambda **kwargs: None)
    monkeypatch.setattr(firestore, 'client', lambda: SimpleNamespace(collection=lambda name: Collection()))
    store = AccountStore('firestore')
    registry = {'gateway': {'id':'gateway', 'owner_id':'alice', 'transport':'connected'}}
    store.save(registry)
    restarted = AccountStore('firestore')
    recovered = {}; restarted.restore(recovered)
    assert recovered['gateway']['owner_id'] == 'alice'
    assert recovered['gateway']['transport'] == 'not-connected'
    restarted.save({})
    assert rows == {}


def test_heartbeat_changes_do_not_rewrite_account_configuration(tmp_path):
    store=AccountStore('sqlite',tmp_path/'accounts.sqlite3')
    registry={'host':{'id':'host','owner_id':'alice','name':'Host','runtime':'00:00:01'}}
    store.save(registry)
    queries=[];store.db.set_trace_callback(queries.append)
    registry['host'].update(runtime='00:00:10',last_heartbeat='later',state='working',transport='connected')
    store.save(registry)
    assert not queries
