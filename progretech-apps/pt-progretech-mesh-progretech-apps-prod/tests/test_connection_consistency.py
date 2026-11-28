from unittest.mock import patch
import main


def test_gateway_status_uses_live_socket_instead_of_stale_registry_flag():
    record = {'id': 'status-test', 'name': 'Status', 'owner_id': 'alice', 'trust_state': 'verified',
              'transport': 'connected', 'state': 'idle'}
    with patch.dict(main.GATEWAY_SOCKETS, {}, clear=True):
        assert main.public_agent(record)['transport'] == 'not-connected'
        main.GATEWAY_SOCKETS['status-test'] = object()
        record['transport'] = 'not-connected'
        assert main.public_agent(record)['transport'] == 'connected'


def test_linked_agent_follows_host_transport_and_keeps_private_profile_out_of_fleet():
    host = {'id': 'status-host', 'owner_id': 'alice', 'trust_state': 'verified'}
    child = {'id': 'status-host--coder', 'owner_id': 'alice', 'trust_state': 'verified',
             'control_center_gateway': 'status-host', 'gateway_linked': True,
             'account_profile': {'role': 'Private profile'}, 'transport': 'connected'}
    with patch.dict(main.DEV_AGENT_REGISTRY, {'status-host': host}), patch.dict(main.GATEWAY_SOCKETS, {}, clear=True):
        assert main.public_agent(child)['transport'] == 'not-connected'
        main.GATEWAY_SOCKETS['status-host'] = object()
        public = main.public_agent(child)
        assert public['transport'] == 'connected'
        assert 'account_profile' not in public


def test_replaced_gateway_socket_cannot_mark_new_connection_offline():
    record = {'id':'race-host','name':'Host','owner_id':'alice','trust_state':'verified','state':'idle'}
    replacement = object()
    class OldSocket:
        def send(self, message): pass
        def close(self, **kwargs): pass
        def receive(self):
            main.GATEWAY_SOCKETS['race-host'] = replacement
            record.update(transport='connected', state='working')
            return None
    with patch.dict(main.DEV_AGENT_REGISTRY, {'race-host':record}), patch.dict(main.GATEWAY_SOCKETS, {}, clear=True), \
         patch('main.validate_device_credential', return_value=(True,'ok',{'owner_id':'alice'})), \
         patch('main.append_event'), patch('main.broadcast_to_clients') as broadcast:
        with main.app.test_request_context('/ws/gateway/race-host?credential=fixture'):
            main.app.view_functions['gateway_socket'].__wrapped__(OldSocket(),'race-host')
        assert main.GATEWAY_SOCKETS['race-host'] is replacement
        assert record['state'] == 'working'
        assert record['transport'] == 'connected'
        assert not any(call.args[1]['type']=='gateway_disconnected' for call in broadcast.call_args_list)
