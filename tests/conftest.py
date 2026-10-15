"""Isolate office-memory transport contracts from any real workstation service."""
import json,os,sys
from pathlib import Path
import pytest

@pytest.fixture(autouse=True)
def office_memory_transport(tmp_path,monkeypatch):
    helper=tmp_path/'memory-helper'
    helper.write_text('#!'+sys.executable+'\n'+'''import json,sys
from pathlib import Path
x=json.load(sys.stdin);p=Path(__file__).with_name(x['namespace']+'-'+x['subject']+'.json')
if x['action']=='save':p.write_text(json.dumps({'text':x['text']}))
print(p.read_text() if p.exists() else '{"text":""}')
''')
    helper.chmod(0o700)
    monkeypatch.setenv('PROGRETECH_OFFICE_MEMORY_HELPER',str(helper))
