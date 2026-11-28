"""Request-bound canonical account status; no cross-request authorization cache."""
import json
from urllib.request import Request, urlopen
from flask import current_app, g

ISSUER = 'https://codeseal.progretech.com'


def account_status(subject):
    cache = g.setdefault('_progretech_status', {})
    if subject not in cache:
        fetch = current_app.config.get('PROGRETECH_SECURITY_STATUS_FETCH')
        if fetch:
            value = fetch(subject)
        else:
            token = current_app.config.get('PROGRETECH_SECURITY_STATUS_TOKEN', '')
            if not token:
                raise RuntimeError('account status credential unavailable')
            req = Request(ISSUER + '/auth/sso/account-status', data=json.dumps({'sub': subject}).encode(),
                          headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            with urlopen(req, timeout=5) as response:
                value = json.load(response)
        if (not isinstance(value, dict) or value.get('sub') != subject or
                value.get('status') not in ('active', 'locked') or
                type(value.get('session_version')) is not int or value['session_version'] < 0 or
                type(value.get('billing_hold')) is not bool):
            raise RuntimeError('invalid account status')
        cache[subject] = value
    return cache[subject]


class AccountBoundSocket:
    """Check canonical status before every private browser socket delivery.

    Gateway/robot sockets do not use this wrapper. A fresh app context prevents
    the handshake request's memoized status surviving a long-lived connection.
    """
    def __init__(self, socket, app, user):
        self.socket = socket
        self.app = app
        self.subject = user.get('progretech_user_id')
        self.version = user.get('session_version')

    def send(self, payload):
        with self.app.app_context():
            if self.app.config.get('PROGRETECH_SECURITY_ENFORCED'):
                try:
                    state = account_status(self.subject)
                    valid = (bool(self.subject) and type(self.version) is int and
                             state['status'] == 'active' and state['session_version'] == self.version)
                except Exception:
                    valid = False
                if not valid:
                    self.close(reason='account_security_revoked')
                    raise RuntimeError('account security revoked')
        return self.socket.send(payload)

    def receive(self):
        return self.socket.receive()

    def close(self, **kwargs):
        return self.socket.close(**kwargs)
