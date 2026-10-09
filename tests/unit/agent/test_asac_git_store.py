"""Git custody is an independently authorized append-only receipt."""
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select
from tests.unit.agent.test_asac_publication_store import publication_fixture, evaluation_fixture, candidate_fixture
from tests.unit.core.test_asac_git_verifier import git_fixture
from shared.contracts.asac_git import AcceptGitAttestation
from shared.contracts.errors import ConflictError
from shared.infra.asac_git_store import ASaCGitStore

@pytest.fixture
async def custody_fixture(publication_fixture):
    publications,args,publish,evaluations,sessions,tables=publication_fixture
    original=await publications.publish(**args,request=publish)
    _,signed,_,_=git_fixture()
    async with sessions.begin() as session:
        publication=await session.get(publications.publications,UUID(original['publication_id']))
        revision=await session.scalar(select(publications.drafts.revisions).where(
            publications.drafts.revisions.revision_id==publication.revision_id))
        revision.author_artifact_id=uuid4()
        revision.document={**revision.document,'author_artifact_digest':'sha256:'+'c'*64}
        payload={**signed.payload.model_dump(mode='json'),'project_id':str(args['project_id']),
            'resource_id':str(args['resource_id']),'publication_id':original['publication_id'],
            'kind':publications.drafts.kind,'revision_id':publication.revision_id,
            'record_digest':publication.evidence['record_digest'],
            'definition_digest':publication.evidence['definition_digest']}
    # Signature/scope authority has separate cryptographic tests. This suite
    # exercises the owner transaction and its exact immutable-content binding.
    verifier=SimpleNamespace(verify=Mock(return_value=payload))
    store=ASaCGitStore(publications,verifier)
    signed.payload=signed.payload.model_validate(payload)
    request=AcceptGitAttestation(operation_id=uuid4(),attestation=signed)
    yield store,args,request,original,verifier,sessions,tables

@pytest.mark.asyncio
async def test_custody_receipt_is_immutable_and_replay_does_not_reverify_expired_signature(custody_fixture):
    store,args,request,original,verifier,sessions,tables=custody_fixture
    receipt=await store.accept(**args,request=request)
    assert receipt['git']['status']=='verified' and receipt['original_publication_unchanged']
    assert not receipt['published'] and not receipt['production_changed']
    assert receipt['verification_scope']=='trusted_pipeline_at_acceptance'
    verifier.verify.side_effect=AssertionError('Original replay must not reverify time-dependent proof')
    assert await store.accept(**args,request=request)==receipt
    assert await store.get(**args,attestation_id=request.operation_id)==receipt
    assert await store.publications.get(**args,publication_id=UUID(original['publication_id']))==original
    assert verifier.verify.call_count==1
    with pytest.raises(ConflictError,match='OPERATION_CONFLICT'):
        await store.accept(**args,request=request.model_copy(update={
            'attestation':request.attestation.model_copy(update={'signature':'A'*86})}))

@pytest.mark.asyncio
async def test_wrong_definition_or_absent_custody_never_marks_git_verified(custody_fixture):
    store,args,request,original,verifier,sessions,tables=custody_fixture
    verifier.verify.return_value={**verifier.verify.return_value,'definition_digest':'sha256:'+'f'*64}
    with pytest.raises(ConflictError,match='CONTENT_MISMATCH'):
        await store.accept(**args,request=request)
    async with sessions.begin() as session:
        revision=await session.scalar(select(store.drafts.revisions).where(
            store.drafts.revisions.revision_id==request.attestation.payload.revision_id))
        revision.author_artifact_id=None
    with pytest.raises(ConflictError,match='SOURCE_UNAVAILABLE'):
        await store.accept(**args,request=request)
    assert await store.publications.get(**args,publication_id=UUID(original['publication_id']))==original
