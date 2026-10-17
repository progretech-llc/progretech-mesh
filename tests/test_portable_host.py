import json
from pathlib import Path
from unittest.mock import patch
import zipfile
import io

from mesh_host_distribution import host_bundle, host_setup_prompt

ROOT = Path(__file__).resolve().parents[1]


def test_bundle_is_reproducible_and_contains_all_host_sources():
    data, digest = host_bundle(ROOT)
    assert (data, digest) == host_bundle(ROOT)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert all(item.date_time == (1980,1,1,0,0,0) for item in archive.infolist())
        assert archive.read('control_center/portable_host.py') == (ROOT/'control_center/portable_host.py').read_bytes()
        assert archive.read('office/engine.mjs') == (ROOT/'office/engine.mjs').read_bytes()
    prompt = host_setup_prompt(ROOT, 'https://mesh.example', 'sample')
    assert digest in prompt
    assert '--gateway sample' in prompt
    assert '--runtime <your actual running OpenClaw agent id>' in prompt


def test_portable_provider_binds_only_local_runtime_and_requires_token(tmp_path):
    home = tmp_path
    state = home/'.progretech-mesh'; state.mkdir()
    (state/'local-access.json').write_text(json.dumps({'token':'t'*32}))
    (state/'control-center-bindings.json').write_text(json.dumps({'sample':'researcher'}))
    (home/'.openclaw').mkdir()
    (home/'.openclaw/openclaw.json').write_text(json.dumps({'agents':{'entries':{'researcher':{'model':'remote/model'}}}}))
    from control_center.portable_host import create_host
    with patch('control_center.specklet.start_observer'):
        host = create_host(home)
    client = host.app.test_client()
    body = {'agent_id':'sample','action':'profile.get','args':{}}
    assert client.post('/api/mesh/control-center', json=body).status_code == 401
    headers = {'X-ProgreTech-Mesh-Local-Token':'t'*32}
    data = client.post('/api/mesh/control-center', json=body, headers=headers).json
    assert data['ok'] is True
    assert set(data['result']['capabilities']) == {'host.system','models.list'}
    assert 'voice.preview' not in data['result']['capabilities']
    body['agent_id'] = 'other'
    assert client.post('/api/mesh/control-center', json=body, headers=headers).status_code == 400


def test_bootstrap_verifies_bundle_before_writing_and_keeps_plugin_token_format(tmp_path, monkeypatch):
    import hashlib
    import importlib.util
    import os
    import sys
    import pytest
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location('mesh_host_bootstrap', ROOT/'distribution/mesh-host-bootstrap-v1.py')
    bootstrap = importlib.util.module_from_spec(spec); spec.loader.exec_module(bootstrap)
    data, digest = host_bundle(ROOT)
    class Download:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return data[:size]
    monkeypatch.setattr(bootstrap, 'build_opener', lambda *args: SimpleNamespace(open=lambda *a, **kw: Download()))
    monkeypatch.setenv('HOME', str(tmp_path))
    args = ['installer', '--bundle','https://mesh.example/api/distribution/host/bundle','--sha256','bad', '--gateway','sample','--runtime','main']
    monkeypatch.setattr(sys, 'argv', args)
    with pytest.raises(SystemExit, match='verification failed'): bootstrap.main()
    assert not (tmp_path/'.progretech-mesh').exists()
    args[args.index('bad')] = digest
    root = tmp_path/'.progretech-mesh/host'/digest
    python = root/'.venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    python.parent.mkdir(parents=True);python.touch()
    (tmp_path/'.openclaw').mkdir()
    (tmp_path/'.openclaw/openclaw.json').write_text(json.dumps({'agents':{'entries':{'main':{}}}}))
    bootstrap.main()
    state = tmp_path/'.progretech-mesh'
    credential = json.loads((state/'local-access.json').read_text())
    assert credential['version'] == 1 and len(credential['token']) >= 24
    assert json.loads((state/'control-center-bindings.json').read_text()) == {'sample':'main'}
    assert json.loads((state/'portable-host.json').read_text())['python'] == str(python)
