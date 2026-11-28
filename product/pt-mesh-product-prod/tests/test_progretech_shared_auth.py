import io,json,time
import pytest
from flask import Flask,session
from mesh_progretech_auth import register_progretech_auth

@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('MESH_FIREBASE_PROJECT_ID',raising=False)
    app=Flask(__name__);app.secret_key='fixture-secret';app.testing=True
    app.add_url_rule('/',endpoint='index',view_func=lambda:'Mesh')
    register_progretech_auth(app)
    return app.test_client()

def test_shared_callback_requires_state_and_correct_audience(client,monkeypatch):
    import mesh_progretech_auth as auth
    assert client.get('/auth/progretech/login').status_code==302
    assert client.get('/auth/progretech/callback?state=incorrect').status_code==400
    client.get('/auth/progretech/login')
    with client.session_transaction() as s:state=s['progretech_login']['state']
    user={'iss':auth.ISSUER,'sub':'central-subject','aud':'mesh','email_verified':True,'email':'verified@example.test','auth_strength':'email+totp'}
    def exchange(request,timeout):
        return io.BytesIO(json.dumps({'access_token':'synthetic'} if request.full_url.endswith('/token') else user).encode())
    monkeypatch.setattr(auth,'urlopen',exchange)
    assert client.get('/auth/progretech/callback?state='+state+'&code=synthetic').status_code==302
    with client.session_transaction() as s:assert s['mesh_user']['id']=='central-subject' and s['mesh_user']['progretech_user_id']=='central-subject'
    client.get('/auth/progretech/login')
    with client.session_transaction() as s:state=s['progretech_login']['state']
    user['aud']='atlas'
    assert client.get('/auth/progretech/callback?state='+state+'&code=synthetic').status_code==401
