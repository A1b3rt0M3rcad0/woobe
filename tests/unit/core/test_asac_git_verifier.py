import base64
from uuid import uuid4
from types import SimpleNamespace
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest
from shared.contracts.asac import asac_digest
from shared.contracts.asac_git import SignedGitAttestation
from shared.contracts.errors import ValidationError
from modules.core.infra.receipts.asac_git_verifier import ASaCGitVerifier


def git_fixture(principal_identity='control:'+str(uuid4())):
    key=Ed25519PrivateKey.from_private_bytes(bytes(range(32))) # deterministic test-only seed
    project,instance=str(uuid4()),str(uuid4())
    builder={'issuer':'ci','principal':principal_identity,'project_ids':[project],
             'instance_id':instance,'repository':'owner/repo','public_key':base64.urlsafe_b64encode(key.public_key().public_bytes_raw()).decode().rstrip('='),'status':'active'}
    payload={'format':'woobe-git-attestation','schema_version':'1.0','issuer':'ci',
        'instance_id':instance,'project_id':project,'resource_id':str(uuid4()),'publication_id':str(uuid4()),
        'kind':'Agent','revision_id':'rv_'+str(uuid4()),'record_digest':'sha256:'+'a'*64,
        'definition_digest':'sha256:'+'b'*64,'author_artifact_digest':'sha256:'+'c'*64,
        'repository':'owner/repo','commit':'d'*40,'workflow_run':'github-actions:1','issued_at':1000,'expires_at':2000}
    digest=asac_digest('git-attestation',payload)
    signed=SignedGitAttestation.model_validate({'payload':payload,'payload_digest':digest,'signature':base64.urlsafe_b64encode(key.sign(digest.encode())).decode().rstrip('=')})
    return ASaCGitVerifier([builder]),signed,builder,key


@pytest.mark.parametrize('mutation', ['signature','digest','issuer','principal','repository','project','instance','expired','revoked'])
def test_git_authority_refuses_forged_signature_scope_expiry_and_revocation(monkeypatch,mutation):
    import modules.core.infra.receipts.asac_git_verifier as module
    verifier,signed,builder,key=git_fixture()
    monkeypatch.setattr(module,'principal_identity',lambda principal:builder['principal'])
    now=1200
    if mutation=='signature': signed.signature='A'*86
    elif mutation=='digest': signed.payload_digest='sha256:'+'f'*64
    elif mutation=='principal': monkeypatch.setattr(module,'principal_identity',lambda principal:'control:'+str(uuid4()))
    elif mutation=='expired': now=2000
    elif mutation=='revoked': verifier.builders['ci']['status']='revoked'
    else:
        attribute={'project':'project_id','instance':'instance_id'}.get(mutation,mutation)
        setattr(signed.payload,attribute,uuid4() if mutation in {'project','instance'} else 'forged')
    with pytest.raises(ValidationError,match='ASAC_GIT_ATTESTATION_INVALID'):
        verifier.verify(signed=signed,principal=SimpleNamespace(),now=now)


def test_git_valid_authority_does_not_rewrite_publication_claims(monkeypatch):
    import modules.core.infra.receipts.asac_git_verifier as module
    verifier,signed,builder,key=git_fixture()
    monkeypatch.setattr(module,'principal_identity',lambda principal:builder['principal'])
    payload=verifier.verify(signed=signed,principal=SimpleNamespace(),now=1200)
    assert payload['commit']=='d'*40 and 'status' not in payload


def test_shared_git_signature_fixture_is_verified_by_python(monkeypatch):
    import json
    from pathlib import Path
    import modules.core.infra.receipts.asac_git_verifier as module
    signed=SignedGitAttestation.model_validate(json.loads(Path('tests/fixtures/asac_git_attestation.json').read_text()))
    key=Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    principal='control:'+str(uuid4())
    builder={'issuer':signed.payload.issuer,'instance_id':str(signed.payload.instance_id),
        'principal':principal,'project_ids':[str(signed.payload.project_id)],'repository':signed.payload.repository,
        'public_key':base64.urlsafe_b64encode(key.public_key().public_bytes_raw()).decode().rstrip('='),'status':'active'}
    monkeypatch.setattr(module,'principal_identity',lambda value:principal)
    assert ASaCGitVerifier([builder]).verify(signed=signed,principal=object(),now=1200)['commit']=='d'*40


@pytest.mark.parametrize('field,value',[
    ('repository','https://secret@github.com/owner/repo'),('issuer',''),
    ('project_ids',[]),('project_ids','not-a-list'),('status','unrecognized')])
def test_operator_builder_configuration_is_explicit_and_credential_free(field,value):
    _,_,builder,_=git_fixture()
    with pytest.raises((ValueError,TypeError)):
        ASaCGitVerifier([{**builder,field:value}])
