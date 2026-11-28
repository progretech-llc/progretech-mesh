"""One selected gateway per owner; reconnects cannot steal another host's slot."""


def activate(registry, sockets, gateway_id):
    host = registry[gateway_id]
    owner = host.get('owner_id')
    if not owner or host.get('control_center_gateway'):
        raise ValueError('owned_gateway_required')
    previous = [row for row in registry.values() if row.get('owner_id') == owner
                and row['id'] != gateway_id and not row.get('control_center_gateway')
                and (row.get('gateway_active') or row['id'] in sockets)]
    if previous and not host.get('gateway_activation_pending'):
        raise ValueError('another_gateway_active')
    for row in previous:
        row.update(gateway_active=False, gateway_superseded=True, transport='not-connected', state='offline')
        socket = sockets.pop(row['id'], None)
        if socket:
            try:
                socket.close(reason='gateway_replaced')
            except (OSError, RuntimeError):
                pass
    host.update(gateway_active=True, gateway_superseded=False, gateway_activation_pending=False)


def visible(row, registry):
    host = registry.get(row.get('control_center_gateway'), row)
    return not host.get('gateway_superseded')
