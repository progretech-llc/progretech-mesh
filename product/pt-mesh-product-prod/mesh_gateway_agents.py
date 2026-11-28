"""Explicit owner-selected, independently signed gateway role enrollment."""
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def public_bytes(pem):
    try:
        key = serialization.load_pem_public_key(pem.encode())
        if not isinstance(key, Ed25519PublicKey): raise ValueError()
        return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    except (ValueError, TypeError, AttributeError):
        raise ValueError('gateway_agent_ed25519_pem_required') from None


def enrollment_binding(payload, owner, registry, gateways):
    gid, aid = payload.get('gateway_id'), payload.get('gateway_candidate_id')
    if not gid and not aid: return {}
    if not isinstance(gid, str) or not isinstance(aid, str): raise ValueError('gateway_candidate_required')
    host = registry.get(gid, {})
    if host.get('owner_id') != owner or host.get('trust_state') != 'verified' or gid not in gateways:
        raise ValueError('owned_connected_verified_gateway_required')
    candidate = next((item for item in host.get('identified_agents', []) if item['id'] == aid), None)
    if not candidate: raise ValueError('gateway_candidate_unavailable')
    evidence = payload.get('codeseal_evidence')
    manifest = evidence.get('manifest') if isinstance(evidence, dict) else None
    identity = manifest.get('mesh_identity') if isinstance(manifest, dict) else None
    if not isinstance(identity, dict) or identity.get('agent_id') != aid or payload.get('agent_id') != aid:
        raise ValueError('gateway_candidate_identity_mismatch')
    existing = registry.get(aid)
    if existing and (existing.get('owner_id') != owner or existing.get('gateway_enrollment') or
                     existing.get('control_center_gateway') != gid):
        raise ValueError('gateway_candidate_already_enrolled')
    key = public_bytes(payload.get('public_key'))
    for other in registry.values():
        if not other.get('public_key'): continue
        try: duplicate = public_bytes(other['public_key']) == key
        except ValueError: continue
        if duplicate: raise ValueError('each_gateway_agent_requires_its_own_pem')
    return {'control_center_gateway':gid, 'gateway_enrollment':True,
            'gateway_candidate_id':aid, 'runtime':'OpenClaw role'}
