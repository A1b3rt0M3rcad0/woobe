"""Instance attestations over owner receipts; no lifecycle or grant authority.

A separate operator-pinned root signs the verification-key manifest. Receipt
keys may be rotated or revoked without silently replacing that root. Keys are
configured, never generated on API startup or derived from JWT secrets.
"""
import base64
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from shared.contracts.asac import asac_digest


def encode(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def decode(value, size):
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError('Invalid Ed25519 key encoding')
    try:
        result = base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid Ed25519 key encoding') from exc
    if len(result) != size or encode(result) != value:
        raise ValueError('Invalid Ed25519 key size or canonical encoding')
    return result


def fingerprint(public):
    return 'sha256:' + sha256(public).hexdigest()


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Trust validity requires an explicit timezone')
    return parsed.astimezone(UTC)


class ASaCReceiptSigner:
    def __init__(self, *, instance_id, root_private_key, receipt_private_key,
                 epoch, expires_at, keys, clock=lambda: datetime.now(UTC)):
        self.instance_id = str(UUID(instance_id))
        if type(epoch) is not int or epoch < 1:
            raise ValueError('Trust epoch must be a positive integer')
        self.root = Ed25519PrivateKey.from_private_bytes(decode(root_private_key, 32))
        self.signer = Ed25519PrivateKey.from_private_bytes(decode(receipt_private_key, 32))
        root_public = self.root.public_key().public_bytes_raw()
        signer_public = self.signer.public_key().public_bytes_raw()
        if root_public == signer_public:
            raise ValueError('Root and online receipt keys must be separate')
        self.key_id = fingerprint(signer_public)
        self.clock = clock
        expires = timestamp(expires_at)
        if not isinstance(keys, list) or not 1 <= len(keys) <= 64:
            raise ValueError('A bounded verification-key manifest is required')
        verified = []
        for key in keys:
            if not isinstance(key, dict) or set(key) != {'public_key', 'status', 'not_before', 'not_after'}:
                raise ValueError('Verification key has unknown or missing fields')
            public = decode(key['public_key'], 32)
            if key['status'] not in {'active', 'retired', 'revoked'}:
                raise ValueError('Invalid verification key status')
            before, after = timestamp(key['not_before']), timestamp(key['not_after'])
            if before >= after:
                raise ValueError('Invalid verification key validity interval')
            verified.append({'key_id': fingerprint(public), **deepcopy(key)})
        if len({key['key_id'] for key in verified}) != len(verified):
            raise ValueError('Duplicate verification keys')
        active = next((key for key in verified if key['key_id'] == self.key_id), None)
        if active is None or active['status'] != 'active':
            raise ValueError('The signing key must be active in the root manifest')
        self.active = active
        self.manifest = {'format': 'woobe-asac-trust', 'schema_version': '1.0',
            'instance_id': self.instance_id, 'epoch': epoch, 'expires_at': expires_at,
            'root_public_key': encode(root_public), 'root_fingerprint': fingerprint(root_public),
            'keys': sorted(verified, key=lambda item: item['key_id'])}
        digest = asac_digest('trust-manifest', self.manifest)
        self.manifest.update(record_digest=digest,
            signature=encode(self.root.sign(digest.encode('ascii'))))
        self.expires = expires

    def attest(self, *, category, project_id, resource_id, kind, receipt):
        now = self.clock().astimezone(UTC)
        if now >= self.expires or not timestamp(self.active['not_before']) <= now < timestamp(self.active['not_after']):
            raise ValueError('Receipt signing authority has expired or is not yet valid')
        if category not in {'revision', 'evaluation', 'publication', 'deployment', 'history'}:
            raise ValueError('Unsupported receipt category')
        if kind not in {'Agent', 'Network'} or not isinstance(receipt, dict):
            raise ValueError('Invalid owner receipt')
        # API callers supply a receipt read from the authorized lifecycle owner,
        # never a request body supplied by the client.
        project, resource = str(UUID(str(project_id))), str(UUID(str(resource_id)))
        if receipt.get('project_id', project) != project or receipt.get('resource_id', resource) != resource:
            raise ValueError('Receipt scope differs from the authorized owner')
        payload = {'format': 'woobe-signed-asac-receipt', 'schema_version': '1.0',
            'instance_id': self.instance_id, 'project_id': project, 'resource_id': resource,
            'kind': kind, 'category': category, 'issued_at': now.isoformat(),
            'key_id': self.key_id, 'receipt': deepcopy(receipt)}
        digest = asac_digest('signed-receipt', payload)
        return {'payload': payload, 'record_digest': digest,
                'signature': encode(self.signer.sign(digest.encode('ascii'))),
                'trust': deepcopy(self.manifest)}
