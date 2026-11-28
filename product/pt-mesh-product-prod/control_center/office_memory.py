"""Explicit reviewed office notes in a host-local Hindsight service."""
import json
import os
import re
import sys
from urllib.error import HTTPError
from urllib.parse import urlsplit, quote
from urllib.request import Request, urlopen


def main():
    body = json.load(sys.stdin)
    subject, namespace = body['subject'], body['namespace']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', subject) or not re.fullmatch(r'[a-f0-9]{20}', namespace):
        raise ValueError('invalid_office_memory_identity')
    base = os.environ.get('MESH_HINDSIGHT_URL', 'http://127.0.0.1:8888').rstrip('/')
    origin = urlsplit(base)
    if origin.scheme != 'http' or origin.hostname not in {'localhost', '127.0.0.1', '::1'} or origin.username or origin.password or origin.query or origin.fragment:
        raise ValueError('local_hindsight_origin_required')
    path = '/v1/default/banks/mesh-office-' + namespace
    def call(suffix, data=None):
        request = Request(base + path + suffix, data=json.dumps(data).encode() if data else None,
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=15) as response:
            return json.load(response)
    if body['action'] == 'save':
        text = body.get('text')
        if not isinstance(text, str) or not text.strip() or len(text) > 6000:
            raise ValueError('invalid_office_memory_text')
        result = call('/memories', {'async': True, 'items': [{'content': text,
            'document_id': subject, 'context': 'Owner-reviewed Mesh Factory office note', 'tags': ['mesh-office', 'agent:' + subject]}]})
        print(json.dumps({'accepted': True, 'pending': True, 'operation_id': result.get('operation_id'),
            'note': 'Queued in local Hindsight. Recall must be verified after extraction.'}))
    elif body['action'] == 'get':
        try:
            result = call('/documents/' + quote(subject, safe=''))
            document = result.get('document', result)
            text = document.get('original_text', document.get('content', ''))
            if not isinstance(text, str):
                text = ''
        except HTTPError as exc:
            if exc.code != 404:
                raise
            text = ''
        print(json.dumps({'text': text}))
    else:
        raise ValueError('invalid_office_memory_action')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('local_hindsight_memory_unavailable', file=sys.stderr)
        sys.exit(1)
