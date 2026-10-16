"""Exercise the shipped enrollment helper with a fake CLI and real package bytes."""
import base64
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading

ROOT=Path(__file__).resolve().parents[1]


def test_enrollment_installs_current_verified_package_without_restart(tmp_path):
    index=json.loads((ROOT/'distribution/openclaw-plugin-index.json').read_text())
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT/'distribution')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    log=tmp_path/'calls'
    cli=tmp_path/'openclaw-fixture'
    cli.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$FIXTURE_CALLS"\nif [ "$1 $2" = "plugins inspect" ]; then printf "{}\\n"; fi\n')
    cli.chmod(0o700)
    payload={'type':'PROGRETECH_MESH_CONNECT_OR_ENROLL','mode':'plug-and-monitor','observation':'read-only','conversation_scope':'mesh-independent','agent_id':'fixture','mesh':'http://127.0.0.1','activation_code':'synthetic','activation_signature':'synthetic'}
    env=dict(os.environ,OPENCLAW=str(cli),FIXTURE_CALLS=str(log),MESH_PLUGIN_PACKAGE_URL=f'http://127.0.0.1:{server.server_port}/'+index['filename'],MESH_PLUGIN_SHA256=index['sha256'],MESH_ENROLLMENT_PAYLOAD='PTM1:'+base64.urlsafe_b64encode(json.dumps(payload).encode()).decode(),MESH_BOOTSTRAP_WORK_DIR=str(tmp_path/'work'),PROGRETECH_MESH_STATE_DIR=str(tmp_path/'state'))
    try:
        result=subprocess.run(['bash',str(ROOT/'distribution/openclaw-self-bootstrap-v1.sh')],env=env,capture_output=True,text=True,timeout=20)
    finally:server.shutdown();server.server_close();thread.join()
    assert result.returncode==0,result.stderr
    calls=log.read_text()
    assert 'plugins install' in calls and '--force --accept-capabilities' in calls
    assert 'restart' not in calls
    backup=tmp_path/'state/adapter-backups'/index['filename']
    assert hashlib.sha256(backup.read_bytes()).hexdigest()==index['sha256']
