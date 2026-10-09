"""Instance attestations over owner receipts; no lifecycle or grant authority.

An offline operator root signs the verification-key manifest. The API receives
only that public manifest and an online receipt key, never the root private key.
"""
import base64
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
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


def create_trust_manifest(*, instance_id, root_private_key, epoch, expires_at, keys):
    """Offline provisioning helper. Root seed never belongs to API settings."""
    root = Ed25519PrivateKey.from_private_bytes(decode(root_private_key, 32))
    public = root.public_key().public_bytes_raw()
    manifest = {'format':'woobe-asac-trust','schema_version':'1.0','instance_id':str(UUID(instance_id)),
        'epoch':epoch,'expires_at':expires_at,'root_public_key':encode(public),
        'root_fingerprint':fingerprint(public),
        'keys':sorted([{'key_id':fingerprint(decode(key['public_key'],32)),**deepcopy(key)}
                       for key in keys], key=lambda item:item['key_id'])}
    digest = asac_digest('trust-manifest',manifest)
    manifest.update(record_digest=digest,signature=encode(root.sign(digest.encode('ascii'))))
    return manifest


class ASaCReceiptSigner:
    def __init__(self, *, trust_manifest, receipt_private_key, clock=lambda: datetime.now(UTC)):
        fields={'format','schema_version','instance_id','epoch','expires_at','root_public_key',
                'root_fingerprint','keys','record_digest','signature'}
        if not isinstance(trust_manifest,dict) or set(trust_manifest)!=fields:
            raise ValueError('A complete offline-signed trust manifest is required')
        manifest=deepcopy(trust_manifest)
        if manifest['format']!='woobe-asac-trust' or manifest['schema_version']!='1.0':
            raise ValueError('Unsupported trust manifest version')
        self.instance_id=str(UUID(manifest['instance_id']))
        if self.instance_id!=manifest['instance_id'] or type(manifest['epoch']) is not int or not 1<=manifest['epoch']<=9223372036854775807:
            raise ValueError('Invalid instance identity or trust epoch')
        root_public=decode(manifest['root_public_key'],32)
        if fingerprint(root_public)!=manifest['root_fingerprint']:
            raise ValueError('Trust root fingerprint mismatch')
        unsigned={key:value for key,value in manifest.items() if key not in {'record_digest','signature'}}
        if asac_digest('trust-manifest',unsigned)!=manifest['record_digest']:
            raise ValueError('Trust manifest digest mismatch')
        try:
            Ed25519PublicKey.from_public_bytes(root_public).verify(
                decode(manifest['signature'],64),manifest['record_digest'].encode('ascii'))
        except InvalidSignature:
            raise ValueError('Trust root signature mismatch') from None
        self.signer=Ed25519PrivateKey.from_private_bytes(decode(receipt_private_key,32))
        signer_public=self.signer.public_key().public_bytes_raw()
        if root_public==signer_public:
            raise ValueError('Root and online receipt keys must be separate')
        self.key_id=fingerprint(signer_public)
        self.clock=clock
        self.expires=timestamp(manifest['expires_at'])
        keys=manifest['keys']
        if not isinstance(keys,list) or not 1<=len(keys)<=64:
            raise ValueError('A bounded verification-key manifest is required')
        seen=set()
        for key in keys:
            if not isinstance(key,dict) or set(key)!={'key_id','public_key','status','not_before','not_after'}:
                raise ValueError('Verification key has unknown or missing fields')
            public=decode(key['public_key'],32)
            if key['key_id'] in seen or fingerprint(public)!=key['key_id'] or public==root_public:
                raise ValueError('Duplicate, invalid or root verification key')
            seen.add(key['key_id'])
            if key['status'] not in {'active','retired','revoked'} or timestamp(key['not_before'])>=timestamp(key['not_after']):
                raise ValueError('Invalid verification key lifecycle')
        self.active=next((key for key in keys if key['key_id']==self.key_id),None)
        if self.active is None or self.active['status']!='active':
            raise ValueError('The online receipt key must be active in the offline manifest')
        self.manifest=manifest

    def attest(self, *, category, project_id, resource_id, kind, receipt):
        now=self.clock()
        if now.tzinfo is None:
            raise ValueError('Signing clock must have an explicit timezone')
        now=now.astimezone(UTC)
        if now>=self.expires or not timestamp(self.active['not_before'])<=now<timestamp(self.active['not_after']):
            raise ValueError('Receipt signing authority has expired or is not yet valid')
        if category not in {'revision','evaluation','publication','deployment','history'}:
            raise ValueError('Unsupported receipt category')
        if kind not in {'Agent','Network'} or not isinstance(receipt,dict):
            raise ValueError('Invalid owner receipt')
        project,resource=str(UUID(str(project_id))),str(UUID(str(resource_id)))
        if receipt.get('project_id',project)!=project or receipt.get('resource_id',resource)!=resource:
            raise ValueError('Receipt scope differs from the authorized owner')
        payload={'format':'woobe-signed-asac-receipt','schema_version':'1.0',
            'instance_id':self.instance_id,'project_id':project,'resource_id':resource,
            'kind':kind,'category':category,'issued_at':now.isoformat(),
            'key_id':self.key_id,'receipt':deepcopy(receipt)}
        digest=asac_digest('signed-receipt',payload)
        return {'payload':payload,'record_digest':digest,
            'signature':encode(self.signer.sign(digest.encode('ascii'))),'trust':deepcopy(self.manifest)}
