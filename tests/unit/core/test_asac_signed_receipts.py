"""Offline attestations have separate pinned roots and explicit key lifecycle."""
from datetime import UTC, datetime
from uuid import uuid4
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.exceptions import InvalidSignature
from shared.contracts.asac import asac_digest
from modules.core.infra.receipts.asac_signer import ASaCReceiptSigner, create_trust_manifest, encode, decode

NOW=datetime(2026,10,9,tzinfo=UTC)


def signer(**changes):
    root=Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    online=Ed25519PrivateKey.from_private_bytes(bytes(range(32,64)))
    args={'instance_id':str(uuid4()),'root_private_key':encode(root.private_bytes_raw()),
        'receipt_private_key':encode(online.private_bytes_raw()),'epoch':1,
        'expires_at':'2026-11-01T00:00:00Z','clock':lambda:NOW,
        'keys':[{'public_key':encode(online.public_key().public_bytes_raw()),'status':'active',
                 'not_before':'2026-10-01T00:00:00Z','not_after':'2026-12-01T00:00:00Z'}]}
    args.update(changes)
    manifest=create_trust_manifest(**{key:args[key] for key in ('instance_id','root_private_key','epoch','expires_at','keys')})
    return ASaCReceiptSigner(trust_manifest=manifest,receipt_private_key=args['receipt_private_key'],clock=args['clock']),root,online


def test_receipt_and_rotatable_key_manifest_have_independent_verifiable_signatures():
    service,root,online=signer()
    receipt={'state':'published','record_digest':'sha256:'+'f'*64,'complete':True}
    result=service.attest(category='publication',project_id=uuid4(),resource_id=uuid4(),kind='Agent',receipt=receipt)
    manifest={key:value for key,value in result['trust'].items() if key not in {'record_digest','signature'}}
    assert asac_digest('trust-manifest',manifest)==result['trust']['record_digest']
    root.public_key().verify(decode(result['trust']['signature'],64),result['trust']['record_digest'].encode())
    assert asac_digest('signed-receipt',result['payload'])==result['record_digest']
    online.public_key().verify(decode(result['signature'],64),result['record_digest'].encode())
    receipt['state']='tampered'
    assert result['payload']['receipt']['state']=='published'
    with pytest.raises(InvalidSignature):
        online.public_key().verify(decode(result['signature'],64),b'sha256:'+b'0'*64)


@pytest.mark.parametrize('changes',[{'epoch':True},{'epoch':0},{'keys':[]},
    {'root_private_key':'not-a-key'},{'expires_at':'2026-11-01'},
    {'receipt_private_key':encode(bytes(range(32)))}])
def test_malformed_or_shared_authority_is_not_silently_repaired(changes):
    with pytest.raises(ValueError): signer(**changes)


def test_expired_manifest_and_foreign_receipt_cannot_be_attested():
    expired,_,_=signer(expires_at='2026-10-08T00:00:00Z')
    with pytest.raises(ValueError,match='expired'):
        expired.attest(category='publication',project_id=uuid4(),resource_id=uuid4(),kind='Agent',receipt={})
    service,_,_=signer()
    with pytest.raises(ValueError,match='scope'):
        service.attest(category='publication',project_id=uuid4(),resource_id=uuid4(),kind='Agent',receipt={'project_id':str(uuid4())})


def test_shared_python_go_fixture_keeps_exact_record_and_manifest_digests():
    import json
    from pathlib import Path
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    fixture=json.loads((Path(__file__).parents[2]/'fixtures'/'asac-signed-receipt.json').read_text())
    result=fixture['signed'];trust=result['trust']
    unsigned={key:value for key,value in trust.items() if key not in {'record_digest','signature'}}
    assert asac_digest('trust-manifest',unsigned)==trust['record_digest']
    Ed25519PublicKey.from_public_bytes(decode(trust['root_public_key'],32)).verify(
        decode(trust['signature'],64),trust['record_digest'].encode())
    assert asac_digest('signed-receipt',result['payload'])==result['record_digest']
    Ed25519PublicKey.from_public_bytes(decode(trust['keys'][0]['public_key'],32)).verify(
        decode(result['signature'],64),result['record_digest'].encode())
    assert result['payload']['receipt']['fixture_number']==9007199254740993
