#!/usr/bin/env python3
"""Agent-executed enrollment rendezvous. Private key never leaves this process.

The running agent answers via the printed files using its existing tools. This
helper does not invoke a model, grant permissions, or invent an identity reply.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def private_write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mesh', required=True)
    parser.add_argument('--invitation-file', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--runtime', required=True)
    args = parser.parse_args()
    base = args.mesh.rstrip('/')
    origin = urlsplit(base)
    if origin.scheme != 'https' or origin.username or origin.password or origin.path or origin.query or origin.fragment:
        raise SystemExit('Mesh onboarding requires a plain HTTPS origin')
    invitation = args.invitation_file.read_text().strip()
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    sign = lambda value: base64.b64encode(key.sign(canonical(value))).decode()
    opener = build_opener(NoRedirect)
    token = None

    def call(path, body=None):
        headers = {'Accept': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        if body is not None:
            headers['Content-Type'] = 'application/json'
        req = Request(base + path, data=canonical(body) if body is not None else None, headers=headers)
        with opener.open(req, timeout=25) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise RuntimeError('mesh_response_too_large')
        result = json.loads(raw)
        if not result.get('ok'):
            raise RuntimeError(result.get('error', 'mesh_request_failed'))
        return result

    claim = call('/api/onboarding/claim', {'invitation': invitation, 'public_key': public,
        'signature': sign({'invitation': invitation, 'public_key': public}), 'runtime': args.runtime})
    token = claim['device_token']
    aid = claim['agent_id']
    root = Path.home() / '.progretech-mesh' / 'onboarding' / aid
    root.mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    sid = claim['id']
    question_seen = None
    last_answer_at = 0
    deadline = time.monotonic() + 900
    print(f'Onboarding connected for {claim["name"]}. Waiting for the identity question.', flush=True)
    while time.monotonic() < deadline:
        response = call(f'/api/onboarding/{sid}/poll')
        question = response.get('question')
        if response['state'] in {'question', 'answered'} and question:
            question_file = root / (question['id'] + '.question.txt')
            answer_file = root / (question['id'] + '.answer.txt')
            if question_seen != question['id']:
                private_write(question_file, question['text'])
                print(f'OWNER QUESTION: {question_file}\nWrite your own agent reply to: {answer_file}', flush=True)
                question_seen = question['id']
            if answer_file.is_file() and (response['state'] == 'question' or time.monotonic() - last_answer_at > 60):
                text = answer_file.read_text()[:4001]
                identity = {'agent_id': aid, 'agent_name': claim['name'], 'public_key': public, 'issued_at': int(time.time())}
                call(f'/api/onboarding/{sid}/answer', {'text': text, 'identity': identity,
                    'signature': sign({'question_id': question['id'], 'text': text, 'identity': identity}),
                    'identity_signature': sign(identity)})
                last_answer_at = time.monotonic()
                print('Signed reply sent. Waiting for Mesh to complete the authorized connection.', flush=True)
        if response['state'] == 'complete':
            directory = Path(os.environ.get('PROGRETECH_MESH_IDENTITY_DIR', str(Path.home() / '.config/progretech/mesh/identity'))).expanduser()
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            directory.chmod(0o700)
            private_write(directory / (aid + '_identity_private.pem'), key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode())
            private_write(directory / (aid + '_identity_public.pem'), public)
            private_write(directory / (aid + '_codeseal_evidence.json'), json.dumps(response['evidence']))
            instructions = root / 'adapter-enrollment.txt'
            private_write(instructions, response['enrollment']['enrollment_message'])
            private_write(root / 'adapter-enrollment.json', json.dumps(response['enrollment']))
            print(f'Identity and CodeSeal evidence saved locally. Read and follow: {instructions}', flush=True)
            return
        time.sleep(2)
    raise SystemExit('Onboarding expired; ask the owner for a new invitation')


if __name__ == '__main__':
    main()
