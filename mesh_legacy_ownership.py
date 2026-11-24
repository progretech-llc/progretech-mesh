"""Resolve existing workspace ownership by immutable central subject only."""
import json
import os
from pathlib import Path


def legacy_owner(subject):
    filename = os.environ.get('PT_LEGACY_IDENTITY_MAP')
    if not filename:
        if os.environ.get('MESH_FIREBASE_PROJECT_ID'):
            raise RuntimeError('Legacy identities require a subject-bound migration map')
        return subject
    with Path(filename).open('rb') as stream:
        raw = stream.read(1048577)
    if len(raw) > 1048576:
        raise RuntimeError('Legacy identity map exceeds its size bound')
    data = json.loads(raw)
    if data.get('schema_version') != 1 or not isinstance(data.get('users'), dict):
        raise RuntimeError('Unsupported legacy identity map')
    owners = set()
    for row in data['users'].values():
        if not isinstance(row, dict): raise RuntimeError('Invalid legacy identity record')
        if row.get('email_verified') is not True or row.get('disabled') is not False: continue
        canonical = row.get('canonical_subject')
        owner = row.get('uid')
        if not isinstance(canonical, str) or not canonical or not isinstance(owner, str) or not owner:
            raise RuntimeError('Legacy subject migration is incomplete')
        if canonical == subject: owners.add(owner)
    if len(owners) > 1: raise RuntimeError('Conflicting legacy workspace ownership')
    return next(iter(owners)) if owners else subject
