"""Authenticated browser office requests relayed to the selected owned host."""
from flask import jsonify, request, render_template
from mesh_agent_management import same_origin
from mesh_control_center import control_relay
from control_center.office import validate_office


def register_office_routes(app, require_session, user_id, registry, gateways, send):
    @app.get('/agents/<agent_id>/terminal')
    @require_session
    def agent_terminal(agent_id):
        record=registry.get(agent_id)
        if not record or record.get('owner_id') != user_id():
            return jsonify(ok=False,error='agent_not_found'),404
        return render_template('agent_terminal.html', agent_id=agent_id, name=record.get('name',agent_id))

    @app.post('/api/agents/<agent_id>/office')
    @require_session
    def office_request(agent_id):
        if not same_origin():
            return jsonify(ok=False, error='same_origin_required'), 403
        if request.content_length and request.content_length > 16384:
            return jsonify(ok=False, error='payload_too_large'), 413
        record = registry.get(agent_id)
        if not record or record.get('owner_id') != user_id():
            return jsonify(ok=False, error='agent_not_found'), 404
        host_id = record.get('control_center_gateway') or agent_id
        host = registry.get(host_id, {})
        if host.get('owner_id') != user_id() or host.get('trust_state') != 'verified':
            return jsonify(ok=False, error='verified_host_required'), 403
        if host_id not in gateways:
            return jsonify(ok=False, error='gateway_not_connected'), 503
        body = request.get_json(silent=True)
        try:
            validate_office(body)
        except (ValueError, TypeError):
            return jsonify(ok=False, error='invalid_office_request'), 400
        result, status = control_relay.dispatch(host_id, 'factory.office', body, send, host_id)
        if result.get('ok'):
            snapshot=result.get('result',{}).get('snapshot',{})
            current=snapshot.get('orchestratorId')
            archived={a['id'] for a in snapshot.get('archivedAgents',[])}
            if current:
                for item in registry.values():
                    if item.get('owner_id') == user_id() and (item is host or item.get('control_center_gateway') == host_id) and item.get('office_agent_id'):
                        item['is_orchestrator']=item['office_agent_id'] == current
                        item['office_archived']=item['office_agent_id'] in archived
        return jsonify(result), status
