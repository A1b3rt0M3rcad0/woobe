from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4
from unittest.mock import AsyncMock
from sqlalchemy import select, func
import pytest
from pydantic import ValidationError as RequestValidationError
from tests.unit.agent.test_asac_candidate_store import candidate_fixture
from shared.contracts.asac_leases import ASaCLeaseScope, ASaCLeaseProof, AcquireASaCLease, ChangeASaCLease, RenewASaCLease, BreakASaCLease
from shared.contracts.errors import AuthorizationError, ConflictError, ValidationError
from shared.infra.asac_lease_store import ASaCLeaseStore, database_now

pytestmark=pytest.mark.asyncio


@pytest.fixture
async def leases(candidate_fixture):
    _,drafts,sessions,tables,args,stage=candidate_fixture
    async with sessions.begin() as session:
        await session.run_sync(lambda sync:tables.ASaCLeaseModel.__table__.create(sync.connection()))
    now=[datetime(2026,10,9,tzinfo=UTC)]
    clock=AsyncMock(side_effect=lambda session:now[0])
    store=ASaCLeaseStore(drafts=drafts,leases=tables.ASaCLeaseModel,maximum_ttl_seconds=30,maximum_duration_seconds=60,clock=clock)
    request=AcquireASaCLease(operation_id=uuid4(),scope='production',workflow_id=uuid4(),ttl_seconds=20)
    yield store,args,request,now,sessions,tables,stage


def proof(record):
    return ASaCLeaseProof(lease_id=record['lease_id'],workflow_id=record['workflow_id'],fencing_token=record['fencing_token'])


async def test_workflow_identity_is_not_credential_reuse_and_receipt_is_original(leases):
    store,args,request,now,sessions,tables,_=leases
    accepted=await store.acquire(**args,request=request)
    assert accepted['fencing_token']==1 and accepted['clock_authority']=='database'
    assert await store.acquire(**args,request=request)==accepted
    with pytest.raises(ConflictError,match='OPERATION_CONFLICT'):
        await store.acquire(**args,request=request.model_copy(update={'workflow_id':uuid4()}))
    for workflow in (request.workflow_id,uuid4()):
        with pytest.raises(ConflictError,match='LEASE_HELD'):
            await store.acquire(**args,request=request.model_copy(update={'operation_id':uuid4(),'workflow_id':workflow}))
    async with sessions.begin() as session:
        with pytest.raises(ConflictError,match='LEASE_HELD'):
            await store.check(session,**args,scope='production')
        await store.check(session,**args,scope='production',proofs=[proof(accepted)],required=True)
        with pytest.raises(ConflictError,match='WORKFLOW_MISMATCH'):
            await store.check(session,**args,scope='production',proofs=[proof(accepted).model_copy(update={'workflow_id':uuid4()})])
        with pytest.raises(ConflictError,match='WORKFLOW_MISMATCH'):
            await store.check(session,**{**args,'principal':args['principal'].model_copy(update={'user_id':uuid4()})},scope='production',proofs=[proof(accepted)])
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(tables.ASaCLeaseModel))==1


async def test_expiry_reacquisition_fences_original_workflow_without_resurrection(leases):
    store,args,request,now,sessions,tables,_=leases
    first=await store.acquire(**args,request=request)
    now[0]+=timedelta(seconds=21)
    assert (await store.get(**args,scope=ASaCLeaseScope(scope='production')))['state']=='expired'
    async with sessions.begin() as session:
        with pytest.raises(ConflictError,match='EXPIRED'):
            await store.check(session,**args,scope='production',proofs=[proof(first)])
        with pytest.raises(ConflictError,match='REQUIRED'):
            await store.check(session,**args,scope='production',required=True)
    second=await store.acquire(**args,request=request.model_copy(update={'operation_id':uuid4(),'workflow_id':uuid4()}))
    assert second['lease_id']!=first['lease_id'] and second['fencing_token']==2
    assert await store.acquire(**args,request=request)==first
    async with sessions.begin() as session:
        with pytest.raises(ConflictError,match='FENCED'):
            await store.check(session,**args,scope='production',proofs=[proof(first)])
        await store.check(session,**args,scope='production',proofs=[proof(second)],required=True)


async def test_renewal_uses_database_time_and_cannot_extend_original_maximum(leases):
    store,args,request,now,sessions,tables,_=leases
    accepted=await store.acquire(**args,request=request)
    renew=RenewASaCLease(scope='production',operation_id=uuid4(),**proof(accepted).model_dump(),ttl_seconds=30)
    for advance in (10,15,10):
        now[0]+=timedelta(seconds=advance)
        result=await store.change(**args,request=renew,action='renew')
        assert result['maximum_expires_at']==accepted['maximum_expires_at']
        assert datetime.fromisoformat(result['expires_at'])<=datetime.fromisoformat(result['maximum_expires_at'])
        assert await store.change(**args,request=renew,action='renew')==result
        renew=renew.model_copy(update={'operation_id':uuid4()})
    with pytest.raises(ConflictError,match='MAXIMUM_REACHED'):
        await store.change(**args,request=renew,action='renew')
    now[0]+=timedelta(seconds=26)
    with pytest.raises(ConflictError,match='EXPIRED'):
        await store.change(**args,request=renew,action='renew')
    async with sessions() as session:
        assert (await database_now(session)).tzinfo==UTC


async def test_unlock_break_and_actor_revocation_have_scoped_durable_receipts(leases):
    store,args,request,now,sessions,tables,_=leases
    first=await store.acquire(**args,request=request)
    release=ChangeASaCLease(scope='production',operation_id=uuid4(),**proof(first).model_dump())
    released=await store.change(**args,request=release,action='release')
    assert released['state']=='released' and await store.change(**args,request=release,action='release')==released
    second=await store.acquire(**args,request=request.model_copy(update={'operation_id':uuid4()}))
    broken=BreakASaCLease(scope='production',operation_id=uuid4(),lease_id=second['lease_id'],fencing_token=2,reason='Recover abandoned workflow')
    result=await store.change(**args,request=broken,action='break')
    assert result['state']=='broken' and result['reason']==broken.reason
    assert store.drafts.owner.inspect.call_args.kwargs['required_permission']=='project:access:write'
    assert await store.change(**args,request=broken,action='break')==result
    store.drafts.owner.inspect.side_effect=AuthorizationError('revoked')
    with pytest.raises(AuthorizationError):
        await store.acquire(**args,request=request)
    with pytest.raises(AuthorizationError):
        await store.change(**args,request=broken,action='break')


async def test_scope_validation_bounded_duration_and_receipt_failure_roll_back(leases,monkeypatch):
    store,args,request,now,sessions,tables,stage=leases
    with pytest.raises(ValidationError,match='DURATION_INVALID'):
        await store.acquire(**args,request=request.model_copy(update={'ttl_seconds':31}))
    with pytest.raises(RequestValidationError):
        AcquireASaCLease(**{**request.model_dump(),'client_time':'2040-01-01'})
    with pytest.raises(RequestValidationError):
        ASaCLeaseScope(scope='production',draft_id=uuid4())
    draft=request.model_copy(update={'scope':'draft','draft_id':stage.draft_id})
    original=store.drafts._receipt
    def fail(*args,**kwargs):
        raise ConflictError('controlled receipt failure')
    monkeypatch.setattr(store.drafts,'_receipt',fail)
    with pytest.raises(ConflictError,match='receipt failure'):
        await store.acquire(**args,request=draft)
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(tables.ASaCLeaseModel))==0
    monkeypatch.setattr(store.drafts,'_receipt',original)
    accepted=await store.acquire(**args,request=draft)
    async with sessions.begin() as session:
        await store.check(session,**args,scope='draft:'+str(stage.draft_id),proofs=[proof(accepted)])
        await store.check(session,**args,scope='production')
        with pytest.raises(ConflictError,match='FENCED'):
            await store.check(session,**args,scope='production',proofs=[proof(accepted)])


async def test_resource_and_draft_reservations_require_each_exact_proof(leases):
    store,args,request,now,sessions,tables,stage=leases
    root=await store.acquire(**args,request=request.model_copy(update={'scope':'resource'}))
    draft=await store.acquire(**args,request=request.model_copy(update={'operation_id':uuid4(),'scope':'draft','draft_id':stage.draft_id}))
    async with sessions.begin() as session:
        with pytest.raises(ConflictError,match='LEASE_HELD'):
            await store.check(session,**args,scope='draft:'+str(stage.draft_id),proofs=[proof(root)])
        await store.check(session,**args,scope='draft:'+str(stage.draft_id),proofs=[proof(root),proof(draft)],required=True)
        with pytest.raises(ValidationError,match='duplicate'):
            await store.check(session,**args,scope='draft:'+str(stage.draft_id),proofs=[proof(root),proof(root)])
        await store.check(session,**args,scope='production',proofs=[proof(root)],required=True)
    lease=request.model_copy(update={'operation_id':uuid4(),'scope':'draft','draft_id':uuid4()})
    from shared.contracts.errors import NotFoundError
    with pytest.raises(NotFoundError):
        await store.acquire(**args,request=lease)


@pytest.mark.parametrize('replacement',[False,True])
async def test_draft_write_rechecks_fencing_after_artifact_io_and_keeps_cas(leases,replacement):
    from shared.contracts.asac_requests import SaveASaCDraft
    store,args,request,now,sessions,tables,stage=leases
    store.drafts.leases=store
    accepted=await store.acquire(**args,request=request.model_copy(update={'scope':'draft','draft_id':stage.draft_id}))
    artifact=store.drafts.artifacts.retain_upload.return_value
    async def delayed_artifact(**kwargs):
        now[0]+=timedelta(seconds=21)
        if replacement:
            await store.acquire(**args,request=request.model_copy(update={'scope':'draft','draft_id':stage.draft_id,'operation_id':uuid4(),'workflow_id':uuid4()}))
        return artifact
    store.drafts.artifacts.retain_upload.side_effect=delayed_artifact
    save=SaveASaCDraft(operation_id=uuid4(),expected_generation=1,upload_id=uuid4(),artifact_digest=artifact['artifact_digest'],leases=[proof(accepted)])
    with pytest.raises(ConflictError,match='FENCED' if replacement else 'EXPIRED'):
        await store.drafts.save_draft(**args,draft_id=stage.draft_id,request=save)
    async with sessions() as session:
        line=await session.get(tables.ASaCDraftModel,stage.draft_id)
        assert line.generation==1
        assert await session.scalar(select(tables.ASaCOperationModel).where(tables.ASaCOperationModel.operation_id==save.operation_id)) is None


async def test_draft_lease_does_not_block_reads_or_other_draft_lines(leases):
    from shared.contracts.asac_requests import OpenASaCDraft, SaveASaCDraft
    store,args,request,now,sessions,tables,stage=leases
    store.drafts.leases=store
    await store.acquire(**args,request=request.model_copy(update={'scope':'draft','draft_id':stage.draft_id}))
    assert await store.drafts.list_drafts(**args)
    artifact=store.drafts.artifacts.retain_upload.return_value
    save=SaveASaCDraft(operation_id=uuid4(),expected_generation=1,upload_id=uuid4(),artifact_digest=artifact['artifact_digest'])
    with pytest.raises(ConflictError,match='LEASE_HELD'):
        await store.drafts.save_draft(**args,draft_id=stage.draft_id,request=save)
    store.drafts.artifacts.retain_upload.assert_not_awaited()
    other=await store.drafts.open_draft(**args,request=OpenASaCDraft(operation_id=uuid4(),resource_uid=(await store.drafts.list_drafts(**args))['drafts'][0]['resource_uid'],name='independent',source_export_id=uuid4()))
    saved=await store.drafts.save_draft(**args,draft_id=UUID(other['draft_id']),request=save)
    assert saved['generation']==2
