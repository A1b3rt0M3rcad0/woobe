"""Instance operator trust, scoped independently of publication claims."""
import base64
from uuid import UUID
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from shared.contracts.asac import asac_digest
from shared.contracts.asac_publication import GitPublicationClaim
from shared.contracts.errors import ValidationError
from shared.infra.admin_idempotency import principal_identity


def public_bytes(encoded):
    raw=base64.urlsafe_b64decode(encoded+'='*((4-len(encoded)%4)%4))
    if len(raw)!=32 or base64.urlsafe_b64encode(raw).decode().rstrip('=')!=encoded:
        raise ValueError('Invalid trusted builder key')
    return raw


class ASaCGitVerifier:
    def __init__(self, builders):
        if not isinstance(builders,list) or len(builders)>64:
            raise ValueError('Invalid Git builders')
        self.builders={}
        for item in builders:
            if not isinstance(item,dict) or set(item)!={'issuer','instance_id','principal','project_ids','repository','public_key','status'}:
                raise ValueError('Invalid Git builder fields')
            if not isinstance(item['issuer'],str) or not 1<=len(item['issuer'])<=128:
                raise ValueError('Invalid trusted builder issuer')
            GitPublicationClaim(repository=item['repository'],commit='a'*40)
            if item['issuer'] in self.builders or item['status'] not in {'active','revoked'}:
                raise ValueError('Ambiguous trusted builder')
            UUID(item['instance_id'])
            if not item['principal'].startswith('control:'):
                raise ValueError('Only an explicit Control Key principal may attest')
            UUID(item['principal'].split(':',1)[1])
            if not isinstance(item['project_ids'],list) or not item['project_ids'] or len(item['project_ids'])>128:
                raise ValueError('Explicit authorized Projects required')
            for identifier in item['project_ids']:
                UUID(identifier)
            self.builders[item['issuer']]={**item,'key':public_bytes(item['public_key'])}

    def verify(self, *, signed, principal, now):
        payload=signed.payload.model_dump(mode='json')
        builder=self.builders.get(payload['issuer'])
        try:
            if (not builder or builder['status']!='active' or builder['principal']!=principal_identity(principal)
                or builder['instance_id']!=payload['instance_id'] or payload['project_id'] not in builder['project_ids']
                or builder['repository']!=payload['repository'] or payload['issued_at']>now+30
                or payload['expires_at']<=now or not 0<payload['expires_at']-payload['issued_at']<=3600):
                raise ValueError('Builder scope unavailable')
            digest=asac_digest('git-attestation',payload)
            if digest!=signed.payload_digest:
                raise ValueError('Payload digest differs')
            signature=base64.urlsafe_b64decode(signed.signature+'==')
            if base64.urlsafe_b64encode(signature).decode().rstrip('=')!=signed.signature:
                raise ValueError('Noncanonical signature')
            Ed25519PublicKey.from_public_bytes(builder['key']).verify(signature,digest.encode('ascii'))
        except Exception:
            raise ValidationError('ASAC_GIT_ATTESTATION_INVALID: Trusted pipeline signature or scope is invalid') from None
        return payload
