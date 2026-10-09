from datetime import UTC,datetime,timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID,uuid4
import pytest
from sqlalchemy import JSON,String,select,func
from sqlalchemy.orm import Mapped,mapped_column
from shared.infra.database.base import BaseModel
from shared.infra.asac_deployment_store import ASaCDeploymentStore
from shared.infra.asac_publication_store import ASaCPublicationStore
from shared.infra.asac_lease_store import ASaCLeaseStore
from shared.contracts.asac_deployment import PlanASaCDeployment,ApplyASaCDeployment
from shared.contracts.asac_publication import PublishASaCCandidate
from shared.contracts.asac_leases import AcquireASaCLease,ASaCLeaseProof
from shared.contracts.errors import ConflictError,AuthorizationError
from tests.unit.agent.test_asac_evaluation_store import evaluation_fixture,candidate_fixture
from modules.agent.infra.database.asac_environment_selector import AgentASaCEnvironmentSelector


class DeploymentTestOutboxModel(BaseModel):
    __tablename__='asac_deployment_test_outbox'
    aggregate_type: Mapped[str]=mapped_column(String)
    aggregate_id: Mapped[UUID]
    event_type: Mapped[str]=mapped_column(String)
    event_version: Mapped[int]
    routing_key: Mapped[str]=mapped_column(String)
    payload: Mapped[dict]=mapped_column(JSON)
    metadata_: Mapped[dict]=mapped_column(JSON)
    idempotency_key: Mapped[str]=mapped_column(String,unique=True)
    correlation_id: Mapped[UUID]
    causation_id: Mapped[UUID]
    status: Mapped[str]=mapped_column(String)
    attempts: Mapped[int]


@pytest.fixture
async def deployment_fixture(evaluation_fixture):
    evaluations,args,candidate,request,runs,tables,sessions=evaluation_fixture
    async with sessions.begin() as session:
        for model in (tables.ASaCPublicationModel,tables.ASaCEnvironmentSelectionModel,tables.ASaCLeaseModel,
                      tables.ASaCDeploymentPlanModel,tables.ASaCDeploymentModel,DeploymentTestOutboxModel):
            await session.run_sync(lambda sync:model.__table__.create(sync.connection()))
        row=await session.get(tables.ASaCCandidateModel,candidate)
        row.runtime_digest_scope='agent-execution-snapshot@2' if evaluations.drafts.kind=='Agent' else 'network-execution-runtime@2'
        for env in ('staging','production'):
            session.add(tables.ASaCEnvironmentSelectionModel(project_id=args['project_id'],resource_id=args['resource_id'],
                environment=env,generation=7,snapshot_id=uuid4(),execution_fingerprint='a'*64))
    accepted,_=await evaluations.accept(**args,candidate_id=candidate,request=request)
    await evaluations.execute(**args,evaluation_id=UUID(accepted['evaluation_id']))
    release_id=uuid4()
    publications=ASaCPublicationStore(evaluations=evaluations,publications=tables.ASaCPublicationModel,
        publisher=SimpleNamespace(publish=AsyncMock(return_value={'release_id':release_id,'release_version':'1.2.3','runtime_digest':'sha256:'+'d'*64,'reused':False})))
    pub=await publications.publish(**args,request=PublishASaCCandidate(operation_id=uuid4(),candidate_id=candidate,
        evaluation_id=UUID(accepted['evaluation_id']),reason='Qualified release'))
    drafts=evaluations.drafts
    drafts.leases=ASaCLeaseStore(drafts=drafts,leases=tables.ASaCLeaseModel)
    bindings=SimpleNamespace(verify=AsyncMock())
    selector=SimpleNamespace(inspect=AsyncMock(return_value={'runtime_digest':'sha256:'+'d'*64,'fingerprint':'d'*64}),
        check_selection=AsyncMock(),apply=AsyncMock(),add_outbox=AgentASaCEnvironmentSelector().add_outbox)
    store=ASaCDeploymentStore(publications=publications,plans=tables.ASaCDeploymentPlanModel,
        deployments=tables.ASaCDeploymentModel,selections=tables.ASaCEnvironmentSelectionModel,
        selector=selector,outbox=DeploymentTestOutboxModel,bindings=bindings)
    plan=PlanASaCDeployment(operation_id=uuid4(),release_id=release_id,publication_id=pub['publication_id'],
        expected_generation=7,reason='Activate qualified release')
    lease=await drafts.leases.acquire(**args,request=AcquireASaCLease(operation_id=uuid4(),scope='production',workflow_id=uuid4(),ttl_seconds=120))
    yield store,args,plan,lease,tables,sessions


def application(plan,lease,**changes):
    return ApplyASaCDeployment(operation_id=uuid4(),plan_id=plan['plan_id'],environment='production',
        leases=[ASaCLeaseProof(**{key:lease[key] for key in ('lease_id','workflow_id','fencing_token')})],**changes)


@pytest.mark.asyncio
async def test_plan_apply_replay_outbox_and_original_operation_are_exact(deployment_fixture):
    store,args,request,lease,tables,sessions=deployment_fixture
    plan=await store.plan(**args,request=request)
    assert plan['state']=='planned' and not plan['executed'] and plan['expected_generation']==7
    assert await store.plan(**args,request=request)==plan
    store.selector.apply.assert_not_awaited()
    apply=application(plan,lease)
    result=await store.apply(**args,request=apply)
    assert result['generation_before']==7 and result['generation_after']==8 and result['selection_changed']
    assert result['release_id']==str(request.release_id) and result['plan_digest']==plan['plan_digest']
    assert await store.apply(**args,request=apply)==result
    assert await store.get(**args,identifier=UUID(result['deployment_id']))==result
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(DeploymentTestOutboxModel))==1
        event=await session.get(DeploymentTestOutboxModel,UUID(result['outbox_id']))
        assert event.payload==result
        selected=await session.scalar(select(tables.ASaCEnvironmentSelectionModel).where(tables.ASaCEnvironmentSelectionModel.environment=='production'))
        assert selected.snapshot_id==request.release_id and selected.selection_authority=='asac'
        assert (await session.scalar(select(tables.ASaCEnvironmentSelectionModel).where(tables.ASaCEnvironmentSelectionModel.environment=='staging'))).generation==7
    assert store.selector.apply.await_count==1
    with pytest.raises(ConflictError,match='ALREADY_APPLIED'):
        await store.apply(**args,request=application(plan,lease))


@pytest.mark.asyncio
async def test_aba_environment_changes_fence_a_frozen_plan(deployment_fixture):
    store,args,request,lease,tables,sessions=deployment_fixture
    plan=await store.plan(**args,request=request)
    async with sessions.begin() as session:
        row=await session.scalar(select(tables.ASaCEnvironmentSelectionModel).where(tables.ASaCEnvironmentSelectionModel.environment=='production'))
        row.generation+=2 # A -> B -> A retains the same ID but advances history.
    with pytest.raises(ConflictError,match='DEPLOYMENT_STALE'):
        await store.apply(**args,request=application(plan,lease))
    store.selector.apply.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('failure',['runtime','binding','policy','expiry','authority','lease'])
async def test_changed_or_unavailable_evidence_never_selects_a_release(deployment_fixture,failure):
    store,args,request,lease,tables,sessions=deployment_fixture
    plan=await store.plan(**args,request=request)
    apply=application(plan,lease)
    if failure=='runtime': store.selector.inspect.return_value['runtime_digest']='sha256:'+'f'*64
    if failure=='binding': store.bindings.verify.side_effect=ConflictError('binding changed')
    if failure=='policy': store.policy=SimpleNamespace(inspect=AsyncMock(return_value={'managed':True,'generation':1}))
    if failure=='expiry':
        async with sessions.begin() as session:
            (await session.get(tables.ASaCDeploymentPlanModel,UUID(plan['plan_id']))).expires_at=datetime.now(UTC)-timedelta(seconds=1)
    if failure=='authority': store.drafts.owner.inspect.side_effect=AuthorizationError('authority revoked')
    if failure=='lease': apply.leases[0].workflow_id=uuid4()
    with pytest.raises((ConflictError,AuthorizationError)):
        await store.apply(**args,request=apply)
    store.selector.apply.assert_not_awaited()
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(tables.ASaCDeploymentModel))==0
        assert await session.scalar(select(func.count()).select_from(DeploymentTestOutboxModel))==0


@pytest.mark.asyncio
async def test_documentary_failure_rolls_back_selection_and_outbox(deployment_fixture,monkeypatch):
    store,args,request,lease,tables,sessions=deployment_fixture
    plan=await store.plan(**args,request=request)
    def fail(*args,**kwargs): raise ConflictError('injected receipt failure')
    monkeypatch.setattr(store.drafts,'_receipt',fail)
    with pytest.raises(ConflictError,match='receipt failure'):
        await store.apply(**args,request=application(plan,lease))
    async with sessions() as session:
        row=await session.scalar(select(tables.ASaCEnvironmentSelectionModel).where(tables.ASaCEnvironmentSelectionModel.environment=='production'))
        assert row.generation==7 and row.selection_authority=='legacy'
        assert await session.scalar(select(func.count()).select_from(tables.ASaCDeploymentModel))==0
        assert await session.scalar(select(func.count()).select_from(DeploymentTestOutboxModel))==0


@pytest.mark.asyncio
async def test_authoring_reservation_does_not_block_environment_selection(deployment_fixture):
    store,args,request,lease,tables,sessions=deployment_fixture
    await store.drafts.leases.acquire(**args,request=AcquireASaCLease(operation_id=uuid4(),scope='resource',workflow_id=uuid4(),ttl_seconds=120))
    plan=await store.plan(**args,request=request)
    assert (await store.apply(**args,request=application(plan,lease)))['generation_after']==8
