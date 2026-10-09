from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, func
from tests.unit.agent.test_asac_evaluation_store import evaluation_fixture, candidate_fixture
from modules.agent.infra.database.asac_models import ASaCPublicationModel
from shared.contracts.asac_publication import PublishASaCCandidate, GitPublicationClaim
from shared.contracts.errors import ConflictError
from shared.infra.asac_publication_store import ASaCPublicationStore


@pytest.fixture
async def publication_fixture(evaluation_fixture):
    evaluations,args,candidate,request,runs,tables,sessions=evaluation_fixture
    # This phase is Agent-only; the shared persistence contract remains injected.
    async with sessions.begin() as session:
        await session.run_sync(lambda sync: ASaCPublicationModel.__table__.create(sync.connection()))
    receipt,_=await evaluations.accept(**args,candidate_id=candidate,request=request)
    await evaluations.execute(**args,evaluation_id=UUID(receipt["evaluation_id"]))
    publisher=SimpleNamespace(publish=AsyncMock(return_value={"release_id":uuid4(),"release_version":"v0.0.20261009.01",
        "runtime_digest":"sha256:"+"d"*64,"reused":False}))
    store=ASaCPublicationStore(evaluations=evaluations,publications=ASaCPublicationModel,publisher=publisher)
    publish=PublishASaCCandidate(operation_id=uuid4(),candidate_id=candidate,evaluation_id=UUID(receipt["evaluation_id"]),reason="Qualified test publication")
    yield store,args,publish,evaluations,sessions,tables


@pytest.mark.asyncio
async def test_publication_original_replay_and_reuse_keep_new_provenance(publication_fixture):
    store,args,request,evaluations,sessions,tables=publication_fixture
    receipt=await store.publish(**args,request=request)
    assert receipt["state"]=="published" and receipt["published"] and not receipt["production_changed"]
    assert receipt["git"]=={"status":"unavailable"}
    assert await store.publish(**args,request=request)==receipt
    assert store.publisher.publish.await_count==1
    store.publisher.publish.return_value["reused"]=True
    new=request.model_copy(update={"operation_id":uuid4(),"git":GitPublicationClaim(repository="owner/repository",commit="a"*40)})
    other=await store.publish(**args,request=new)
    assert other["publication_id"]!=receipt["publication_id"] and other["release_id"]==receipt["release_id"]
    assert other["reused"] and other["git"]["status"]=="declared"
    assert await store.get(**args,publication_id=UUID(receipt["publication_id"]))==receipt
    with pytest.raises(ConflictError,match="OPERATION_CONFLICT"):
        await store.publish(**args,request=request.model_copy(update={"reason":"Different original request"}))


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value",[("state","failed"),("runtime_digest","changed"),("record_digest","changed"),("binding_digest","changed"),("cases",[])])
async def test_absent_or_incompatible_evaluation_cannot_publish(publication_fixture,field,value):
    store,args,request,evaluations,sessions,tables=publication_fixture
    async with sessions.begin() as session:
        row=await session.get(tables.ASaCEvaluationModel,request.evaluation_id)
        setattr(row,field,value)
    with pytest.raises(ConflictError,match="EVALUATION_REQUIRED"):
        await store.publish(**args,request=request)
    store.publisher.publish.assert_not_awaited()
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(ASaCPublicationModel))==0


@pytest.mark.asyncio
async def test_native_snapshot_mismatch_rolls_back_publication_receipt(publication_fixture):
    store,args,request,evaluations,sessions,tables=publication_fixture
    store.publisher.publish.return_value["runtime_digest"]="other"
    with pytest.raises(ConflictError,match="RUNTIME_CHANGED"):
        await store.publish(**args,request=request)
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(ASaCPublicationModel))==0


def test_publication_claims_cannot_forge_verified_git_or_embed_credentials():
    from pydantic import ValidationError
    for claim in [
        {"repository":"owner/repository","commit":"a"*40,"status":"verified"},
        {"repository":"https://secret@github.com/owner/repository","commit":"a"*40},
        {"repository":"https://github.com/owner/repository?token=secret","commit":"a"*40},
        {"repository":"owner/repository","commit":"not-a-commit"},
    ]:
        with pytest.raises(ValidationError):
            GitPublicationClaim.model_validate(claim)
    with pytest.raises(ValidationError):
        PublishASaCCandidate(operation_id=uuid4(),candidate_id=uuid4(),evaluation_id=uuid4(),reason="   ")
