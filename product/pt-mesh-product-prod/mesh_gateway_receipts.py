"""Owner-approved signed role enrollments restored from the owner's gateway."""
import base64
import hashlib
import hmac
import json

FIELDS = ('id', 'owner_id', 'name', 'role', 'public_key', 'codeseal_evidence',
          'fingerprint', 'control_center_gateway', 'gateway_candidate_id',
          'gateway_enrollment', 'runtime', 'enrolled_at')


def issue_receipt(record, host, secret):
    body = {'version': 1, 'record': {k: record.get(k) for k in FIELDS},
            'gateway_key_hash': hashlib.sha256(host['public_key'].strip().encode()).hexdigest()}
    encoded = base64.urlsafe_b64encode(json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).decode().rstrip('=')
    signed = 'PTMGE1.' + encoded
    return signed + '.' + hmac.new(secret if isinstance(secret, bytes) else secret.encode(), signed.encode(), hashlib.sha256).hexdigest()


def restore_receipt(receipt, gateway_id, host, secret, candidates, verify, existing=()):
    if not isinstance(receipt, str) or len(receipt) > 32768:
        raise ValueError('invalid_gateway_enrollment_receipt')
    try:
        prefix, encoded, signature = receipt.split('.')
        expected = hmac.new(secret if isinstance(secret, bytes) else secret.encode(), (prefix + '.' + encoded).encode(), hashlib.sha256).hexdigest()
        if prefix != 'PTMGE1' or not hmac.compare_digest(signature, expected):
            raise ValueError()
        body = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
        record = body['record']
        if (body['version'] != 1 or set(record) != set(FIELDS)
                or record['owner_id'] != host.get('owner_id')
                or record['control_center_gateway'] != gateway_id
                or record['id'] != record['gateway_candidate_id']
                or record['id'] not in candidates
                or record['gateway_enrollment'] is not True
                or body['gateway_key_hash'] != hashlib.sha256(host['public_key'].strip().encode()).hexdigest()):
            raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ValueError('invalid_gateway_enrollment_receipt') from exc
    if record['id'] in existing:
        raise ValueError('gateway_enrollment_already_present')
    verdict = verify({'agent_id': record['id'], 'codeseal_evidence': record['codeseal_evidence']},
                     record['name'], record['public_key'])
    if verdict.get('provider') != 'codeseal' or verdict.get('valid') is not True:
        raise ValueError('restored_identity_verification_failed')
    record.update(trust_state='verified', trust_valid=True, trust_reason=verdict['reason'],
                  transport='not-connected', state='unknown', task='Signed role restored',
                  phase='Waiting for gateway roster', progress=0, model='Unknown', telemetry={})
    return record
