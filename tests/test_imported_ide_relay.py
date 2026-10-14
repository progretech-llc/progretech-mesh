"""Imported relay tokens bind an owned host and its current native role, not aliases."""
import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
import main


@pytest.fixture
def relay(monkeypatch):
    registry = {
        'host-a': {'id':'host-a','owner_id':'owner-a','trust_state':'verified','transport':'connected',
                   'identified_agents':[{'id':'host-a--custom_role','name':'Custom role'}]},
        'host-a--custom_role': {'id':'host-a--custom_role','owner_id':'owner-a','trust_state':'verified',
                'transport':'connected','control_center_gateway':'host-a','runtime_id':'custom_role','gateway_linked':True},
        'host-b': {'id':'host-b','owner_id':'owner-b','trust_state':'verified','transport':'connected'},
    }
    monkeypatch.setattr(main,'DEV_AGENT_REGISTRY',registry)
    monkeypatch.setattr(main,'GATEWAY_SOCKETS',{'host-a':object(),'host-b':object()})
    monkeypatch.setattr(main,'IDE_PENDING',{})
    monkeypatch.setattr(main,'ide_token_secret',lambda:b'synthetic-test-only-secret')
    client=main.app.test_client()
    with client.session_transaction() as session:session['mesh_user']={'id':'owner-a','display_name':'Owner A'}
    return client,registry


def mint(client,agent='host-a--custom_role'):
    response=client.post('/api/agents/'+agent+'/ide/token',headers={'Origin':'http://localhost'})
    assert response.status_code==201
    return response.json


def test_imported_mint_models_are_role_bound_and_origin_guarded(relay):
    client,registry=relay
    path='/api/agents/host-a--custom_role/ide/token'
    assert client.post(path).status_code==403
    assert client.post(path,headers={'Origin':'https://foreign.invalid'}).status_code==403
    assert client.post(path,json={'agent_id':'host-b'},headers={'Origin':'http://localhost'}).status_code==400
    assert client.post(path,data='{bad',content_type='application/json',headers={'Origin':'http://localhost'}).status_code==400
    issued=mint(client)
    assert issued['models']==['host-a--custom_role','host-a--custom_role-code']
    assert issued['recommended_model']=='host-a--custom_role-code'
    good,reason,payload=main.validate_ide_token(issued['api_key'])
    assert good,reason
    assert payload['gateway_id']=='host-a' and payload['runtime_id']=='custom_role'
    response=client.get('/v1/models',headers={'Authorization':'Bearer '+issued['api_key']})
    assert [m['id'] for m in response.json['data']]==issued['models']
    assert response.headers['Cache-Control']=='no-store'
    assert client.post('/api/agents/host-a--custom_role/pair-token',headers={'Origin':'http://localhost'}).status_code==409
    with client.session_transaction() as session:session['mesh_user']={'id':'owner-b','display_name':'Other'}
    assert client.post(path,headers={'Origin':'http://localhost'}).status_code==404


@pytest.mark.parametrize('mutation',[
    lambda r:r['host-a'].update(owner_id='owner-b'),
    lambda r:r['host-a'].update(trust_state='unsigned'),
    lambda r:r['host-a'].update(identified_agents=[]),
    lambda r:r['host-a--custom_role'].update(runtime_id='main'),
    lambda r:r['host-a--custom_role'].update(control_center_gateway='host-b'),
    lambda r:r['host-a--custom_role'].update(office_worker=True),
    lambda r:r['host-a--custom_role'].update(office_archived=True),
    lambda r:r['host-a--custom_role'].update(owner_id='owner-b'),
])
def test_binding_changes_revoke_token_before_dispatch(relay,mutation):
    client,registry=relay;token=mint(client)['api_key'];mutation(registry)
    with patch.object(main,'send_gateway_message') as send:
        response=client.post('/v1/chat/completions',headers={'Authorization':'Bearer '+token},json={'model':'host-a--custom_role-code','messages':[{'role':'user','content':'Fixture'}]})
    assert response.status_code==401
    send.assert_not_called()


def test_dispatch_targets_host_and_only_host_can_resolve_role_response(relay):
    client,registry=relay;issued=mint(client);calls=[]
    completion={'id':'synthetic','model':'host-a--custom_role-code','choices':[{'message':{'role':'assistant','content':'Synthetic role response'},'finish_reason':'stop'}]}
    def send(agent,message):
        calls.append((agent,message));rid=message['request_id']
        response={'type':'ide_chat_response','request_id':rid,'payload':{'ok':True,'completion':completion}}
        assert not main.resolve_ide_pending('host-b',response)
        assert not main.resolve_ide_pending('host-a--custom_role',response)
        assert main.resolve_ide_pending('host-a',response)
        return True,None
    headers={'Authorization':'Bearer '+issued['api_key']}
    body={'model':'host-a--custom_role-code','messages':[{'role':'user','content':'Synthetic input'}],'user':'same-client-hint'}
    with patch.object(main,'send_gateway_message',side_effect=send):
        assert client.post('/v1/chat/completions',headers=headers,json=body).status_code==200
        assert client.post('/v1/chat/completions',headers=headers,json=body).status_code==200
        other=mint(client)['api_key']
        assert client.post('/v1/chat/completions',headers={'Authorization':'Bearer '+other},json=body).status_code==200
    assert all(agent=='host-a' for agent,_ in calls)
    assert all(message['payload']['target']=={'agent_id':'host-a--custom_role','gateway_id':'host-a','runtime_id':'custom_role'} for _,message in calls)
    outgoing=[message['payload']['openai'] for _,message in calls]
    assert all(row['messages']==body['messages'] and row['stream'] is False for row in outgoing)
    assert outgoing[0]['user']==outgoing[1]['user']!=outgoing[2]['user']
    assert outgoing[0]['user']!='same-client-hint'
    assert not main.IDE_PENDING


@pytest.mark.parametrize('body',[
    {'model':'rend','messages':[{'role':'user','content':'Fixture'}]},
    {'model':'host-a--custom_role-code','messages':[{}]},
    {'model':'host-a--custom_role-code','messages':[{'role':[]}]},
    {'model':'host-a--custom_role-code','messages':[{'role':'user'}],'target':{'runtime_id':'main'}},
    {'model':'host-a--custom_role-code','messages':[{'role':'user'}],'user':[]},
])
def test_malformed_or_cross_role_chat_never_dispatches(relay,body):
    client,_=relay;token=mint(client)['api_key']
    with patch.object(main,'send_gateway_message') as send:
        response=client.post('/v1/chat/completions',headers={'Authorization':'Bearer '+token},json=body)
    assert response.status_code==400
    send.assert_not_called()


def test_disconnected_host_and_removed_role_fail_closed(relay):
    client,registry=relay;token=mint(client)['api_key'];main.GATEWAY_SOCKETS.pop('host-a')
    with patch.object(main,'send_gateway_message') as send:
        response=client.post('/v1/chat/completions',headers={'Authorization':'Bearer '+token},json={'model':'host-a--custom_role','messages':[{'role':'user','content':'Fixture'}]})
    assert response.status_code==503;send.assert_not_called()
    del registry['host-a--custom_role']
    assert client.get('/v1/models',headers={'Authorization':'Bearer '+token}).status_code==401


@pytest.mark.parametrize('payload',[[],None,{'scope':'mesh-ide','v':1,'expires_at':'bad'}, {'scope':'mesh-ide','v':1,'expires_at':True}])
def test_signed_malformed_token_is_rejected_without_500(relay,payload):
    client,_=relay
    encoded=main._b64url_encode(json.dumps(payload).encode())
    signature=hmac.new(main.ide_token_secret(),encoded.encode(),hashlib.sha256).hexdigest()
    token='PTMIDE1.'+encoded+'.'+signature
    assert client.get('/v1/models',headers={'Authorization':'Bearer '+token}).status_code==401


def test_long_native_runtime_preserved_in_hashed_roster_binding(relay):
    from mesh_control_center import register_gateway_agents
    client,registry=relay
    runtime='custom_native_role_with_a_long_name'
    agent='host-a--role_'+hashlib.sha256(runtime.encode()).hexdigest()[:24]
    assert register_gateway_agents('host-a',{'agents':[{'id':agent,'runtime_id':runtime,'name':'Custom native role'}]},registry)
    assert registry[agent]['runtime_id']==runtime
    issued=mint(client,agent)
    valid,reason,payload=main.validate_ide_token(issued['api_key'])
    assert valid,reason
    assert payload['runtime_id']==runtime
    assert not register_gateway_agents('host-a',{'agents':[{'id':agent,'runtime_id':'main','name':'Bad binding'}]},registry)
    assert registry[agent]['runtime_id']==runtime
