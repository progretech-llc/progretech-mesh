"""Relay discovery follows each authenticated gateway's native roster."""
from unittest.mock import patch
import pytest
import main
from mesh_control_center import register_gateway_agents


@pytest.fixture
def fleet(monkeypatch):
    registry={host:{'id':host,'owner_id':owner,'trust_state':'verified','transport':'connected'}
              for host,owner in [('my-host','owner'),('other-host','other-owner')]}
    monkeypatch.setattr(main,'DEV_AGENT_REGISTRY',registry)
    monkeypatch.setattr(main,'GATEWAY_SOCKETS',{'my-host':object(),'other-host':object()})
    monkeypatch.setattr(main,'IDE_PENDING',{})
    monkeypatch.setattr(main,'ide_token_secret',lambda:b'synthetic-roster-secret')
    roster=[{'id':'my-host','runtime_id':'intake','name':'Intake'},
            {'id':'my-host--specialist','runtime_id':'specialist','name':'Specialist'}]
    assert register_gateway_agents('my-host',{'agents':roster},registry)
    client=main.app.test_client()
    with client.session_transaction() as session:session['mesh_user']={'id':'owner','display_name':'Owner'}
    token=main.issue_ide_token('owner','my-host')['token']
    return client,registry,roster,{'Authorization':'Bearer '+token}


def test_host_discovery_and_recommendation_match_current_roster(fleet):
    client,registry,roster,headers=fleet
    assert main.ide_models('my-host')==['my-host','my-host--specialist']
    response=client.post('/api/agents/my-host/ide/token',headers={'Origin':'http://localhost'})
    assert response.status_code==201
    assert response.json['recommended_model']=='my-host'
    assert response.json['models']==main.ide_models('my-host')
    assert [x['id'] for x in client.get('/v1/models',headers=headers).json['data']]==main.ide_models('my-host')
    assert register_gateway_agents('my-host',{'agents':roster[:1]},registry)
    assert main.ide_models('my-host')==['my-host']
    with patch.object(main,'send_gateway_message') as send:
        removed=client.post('/v1/chat/completions',headers=headers,json={'model':'my-host--specialist','messages':[{'role':'user','content':'Fixture'}]})
    assert removed.status_code==400
    assert removed.json['error']['code']=='model_not_allowed'
    send.assert_not_called()


def test_unknown_or_foreign_roles_never_enter_host_catalog(fleet):
    client,registry,roster,headers=fleet
    assert register_gateway_agents('other-host',{'agents':[{'id':'other-host','runtime_id':'main','name':'Other'}, {'id':'other-host--specialist','runtime_id':'specialist','name':'Other specialist'}]},registry)
    registry['my-host']['identified_agents'].extend([{'id':'other-host--specialist'},{'id':'missing'}])
    assert main.ide_models('my-host')==['my-host','my-host--specialist']
    registry['my-host--specialist']['owner_id']='other-owner'
    assert main.ide_models('my-host')==['my-host']


@pytest.mark.parametrize('flag',['office_worker','office_archived'])
def test_office_only_or_archived_role_is_not_a_relay_model(fleet,flag):
    client,registry,roster,headers=fleet
    registry['my-host--specialist'][flag]=True
    assert main.ide_models('my-host')==['my-host']


def test_missing_host_runtime_is_cleared_and_mint_fails_closed(fleet):
    client,registry,roster,headers=fleet
    assert register_gateway_agents('my-host',{'agents':[]},registry)
    assert 'runtime_id' not in registry['my-host']
    assert main.ide_models('my-host')==[]
    result=client.post('/api/agents/my-host/ide/token',headers={'Origin':'http://localhost'})
    assert result.status_code==409
    assert result.json['error']=='gateway_roster_unavailable'


def test_host_token_dispatches_exact_target_with_separate_role_sessions(fleet):
    client,registry,roster,headers=fleet
    calls=[]
    def send(host,message):
        assert host=='my-host'
        calls.append(message['payload'])
        assert main.resolve_ide_pending(host,{'request_id':message['request_id'],'payload':{'ok':True,'completion':{'choices':[{'message':{'role':'assistant','content':'Synthetic'},'finish_reason':'stop'}]}}})
        return True,None
    with patch.object(main,'send_gateway_message',side_effect=send):
        for model in ['my-host','my-host--specialist']:
            response=client.post('/v1/chat/completions',headers=headers,json={'model':model,'messages':[{'role':'user','content':'Fixture'}],'user':'shared-hint'})
            assert response.status_code==200
    assert calls[0]['target']=={'agent_id':'my-host','gateway_id':'my-host','runtime_id':'intake'}
    assert calls[1]['target']=={'agent_id':'my-host--specialist','gateway_id':'my-host','runtime_id':'specialist'}
    assert calls[0]['openai']['user']!=calls[1]['openai']['user']


def test_role_removed_while_request_runs_does_not_deliver_stale_completion(fleet):
    client,registry,roster,headers=fleet
    def send(host,message):
        assert register_gateway_agents('my-host',{'agents':roster[:1]},registry)
        main.resolve_ide_pending(host,{'request_id':message['request_id'],'payload':{'ok':True,'completion':{'choices':[]}}})
        return True,None
    with patch.object(main,'send_gateway_message',side_effect=send):
        ok,error,_=main.dispatch_ide_chat('my-host',{'model':'my-host--specialist','messages':[{'role':'user','content':'Fixture'}]})
    assert not ok and error=='ide_role_binding_invalid'


def test_intake_runtime_changes_are_rechecked(fleet):
    client,registry,roster,headers=fleet
    def send(host,message):
        registry['my-host']['runtime_id']='replacement'
        main.resolve_ide_pending(host,{'request_id':message['request_id'],'payload':{'ok':True,'completion':{'choices':[]}}})
        return True,None
    with patch.object(main,'send_gateway_message',side_effect=send):
        ok,error,_=main.dispatch_ide_chat('my-host',{'model':'my-host','messages':[{'role':'user','content':'Fixture'}]})
    assert not ok and error=='ide_role_binding_invalid'
