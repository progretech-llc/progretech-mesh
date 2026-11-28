import pytest
from flask import Flask,session
from mesh_progretech_auth import register_progretech_auth

@pytest.fixture
def setup():
    app=Flask(__name__);app.secret_key='fixture';app.testing=True
    app.add_url_rule('/',endpoint='index',view_func=lambda:'private')
    app.add_url_rule('/api/private',view_func=lambda:'private')
    register_progretech_auth(app)
    state={'sub':'central','status':'active','session_version':2,'billing_hold':False}
    calls=[]
    def fetch(sub):calls.append(sub);return dict(state)
    app.config.update(PROGRETECH_SECURITY_ENFORCED=True,PROGRETECH_SECURITY_STATUS_FETCH=fetch)
    client=app.test_client()
    with client.session_transaction() as s:s['mesh_user']={'id':'legacy-firebase-uid','progretech_user_id':'central','session_version':2,'auth_source':'progretech-shared'}
    return app,client,state,calls


def test_existing_cookie_lock_revokes_on_next_request(setup):
    app,client,state,calls=setup
    assert client.get('/api/private').status_code==200
    state['status']='locked'
    result=client.get('/api/private')
    assert result.status_code==423 and 'support@progretech.com' in result.json['message']
    assert calls==['central','central']
    with client.session_transaction() as s:assert not s.get('mesh_user')


@pytest.mark.parametrize('change',[{'session_version':3},{'sub':'other'},{'billing_hold':None},{'status':'unknown'}])
def test_binding_fails_closed(setup,change):
    app,client,state,calls=setup;state.update(change)
    assert client.get('/api/private').status_code==(401 if change=={'session_version':3} else 503)


def test_outage_blocks_and_retry_cookie_remains(setup):
    app,client,state,calls=setup
    def fail(subject):raise RuntimeError('unavailable')
    app.config['PROGRETECH_SECURITY_STATUS_FETCH']=fail
    assert client.get('/api/private').status_code==503
    with client.session_transaction() as s:assert s.get('mesh_user')


def test_legacy_human_cookie_requires_shared_login_but_robot_has_no_lookup(setup):
    app,client,state,calls=setup
    with client.session_transaction() as s:s['mesh_user']={'id':'firebase','email':'fixture@example.test','auth_source':'firebase-email-link'}
    assert client.get('/api/private').status_code==401
    assert app.test_client().get('/api/private').status_code==200
    assert calls==[]


def test_hold_does_not_remove_existing_service_access(setup):
    app,client,state,calls=setup;state['billing_hold']=True
    assert client.get('/api/private').status_code==200


def test_open_browser_socket_revalidates_every_delivery(setup):
    from mesh_account_security import AccountBoundSocket
    app,client,state,calls=setup
    class Socket:
        sent=[]
        closed=False
        def send(self,value):self.sent.append(value)
        def close(self,**kwargs):self.closed=True
    socket=Socket();bound=AccountBoundSocket(socket,app,{'progretech_user_id':'central','session_version':2})
    bound.send('first')
    state['status']='locked'
    with pytest.raises(RuntimeError):bound.send('private second')
    assert socket.sent==['first'] and socket.closed and calls==['central','central']


def test_legacy_new_session_cannot_avoid_shared_lock(setup):
    app,client,state,calls=setup
    anonymous=app.test_client()
    assert anonymous.post('/api/auth/firebase/session').status_code==401
    assert anonymous.post('/login/dev').status_code==401
