from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from modules.artifacts.application.contracts.document_models import DocumentModelOutput, DocumentModelUsage
from modules.artifacts.application.contracts.jobs import ClaimProcessingJob
from modules.artifacts.application.contracts.processing import ProcessingRecipe
from modules.artifacts.domain.models import ArtifactError, ArtifactRef
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.document_model_calls import DocumentModelCallRepository
from modules.artifacts.infra.database.jobs import ProcessingJobRepository
from modules.artifacts.infra.database.model_operation_models import ArtifactDocumentModelCallModel
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from tests.integration.artifacts.test_jobs_postgres import setup, execute
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store


async def ledger_lease(engine, project, store):
    # Storage admission fixture exercises the real durable call ledger only;
    # governed provider integration is qualified separately, never fabricated.
    _, request = await setup(engine, project, store)
    async with ArtifactsUnitOfWork(engine) as uow:
        source = await CatalogRepository(uow).revision(request.scope, request.workspace_id,
            ArtifactRef(request.artifact_id, request.definition.revision_id))
        job = await ProcessingJobRepository(uow).request(request, source, ProcessingRecipe(), None, None,
            model_binding={'fingerprint': 'b'*64, 'fixture': 'ledger-only'})
    await execute(engine, 'deliver', 50)
    lease = await execute(engine, 'claim', ClaimProcessingJob(uuid4().hex))
    assert lease.id == job.id
    return lease


async def call(engine, method, *args, **kwargs):
    async with ArtifactsUnitOfWork(engine) as uow:
        return await getattr(DocumentModelCallRepository(uow), method)(*args, **kwargs)


def admission(lease, key='summary'):
    return {'lease': lease, 'operation_key': key, 'operation': 'summarize',
        'input_fingerprint': 'c'*64, 'input_bytes': 200, 'max_output_tokens': 64}


async def test_completed_model_response_is_durable_reused_and_cannot_change_input(engine, artifacts_database, object_store):
    lease = await ledger_lease(engine, artifacts_database['project_id'], object_store)
    receipt = await call(engine, 'admit', **admission(lease))
    assert receipt['state'] == 'admitted' and receipt['input_tokens'] is None
    await call(engine, 'dispatched', lease, receipt['id'], receipt['nonce'])
    with pytest.raises(ArtifactError) as error:
        await call(engine, 'dispatched', lease, receipt['id'], receipt['nonce'])
    assert error.value.code == 'EXTERNAL_OPERATION_UNCERTAIN'
    output = DocumentModelOutput.model_validate({'summaries': [{'text': 'Inferred', 'fragment_ids': ['fragment']}]})
    observed = await call(engine, 'observed', lease, call_id=receipt['id'], nonce=receipt['nonce'],
        usage=DocumentModelUsage(input_tokens=17, output_tokens=5), output=output)
    assert observed['state'] == 'completed' and observed['cost_usd'] is None
    assert await call(engine, 'admit', **admission(lease)) == observed
    with pytest.raises(ArtifactError) as error:
        await call(engine, 'admit', **{**admission(lease), 'input_fingerprint': 'd'*64})
    assert error.value.code == 'ARTIFACT_IDEMPOTENCY_CONFLICT'
    with pytest.raises(DBAPIError):
        async with ArtifactsUnitOfWork(engine) as uow:
            await uow.session.execute(text("UPDATE artifacts.processing_jobs SET model_binding='{}' WHERE id=:id"), {'id': lease.id})


async def test_uncertain_sent_call_never_retries_and_can_later_account_known_usage(engine, artifacts_database, object_store):
    lease = await ledger_lease(engine, artifacts_database['project_id'], object_store)
    receipt = await call(engine, 'admit', **admission(lease))
    await call(engine, 'dispatched', lease, receipt['id'], receipt['nonce'])
    await call(engine, 'observed', lease, call_id=receipt['id'], nonce=receipt['nonce'],
        usage=DocumentModelUsage(), uncertain=True, error_code='EXTERNAL_OPERATION_UNCERTAIN')
    with pytest.raises(ArtifactError) as error:
        await call(engine, 'admit', **admission(lease))
    assert error.value.code == 'EXTERNAL_OPERATION_UNCERTAIN'
    # Acknowledgement can account real I/O after authority/lease was lost.
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text("UPDATE artifacts.processing_jobs SET status='uncertain' WHERE id=:id"), {'id': lease.id})
    result = await call(engine, 'observed', lease, call_id=receipt['id'], nonce=receipt['nonce'],
        usage=DocumentModelUsage(input_tokens=19, output_tokens=2), error_code='MODEL_OUTPUT_INVALID')
    assert result['state'] == 'failed' and result['input_tokens'] == 19
    async with ArtifactsUnitOfWork(engine) as uow:
        row = await uow.session.scalar(select(ArtifactDocumentModelCallModel).where(ArtifactDocumentModelCallModel.id == receipt['id']))
        assert row.observation_revision == 2 and row.response is None and row.cost_usd is None
    with pytest.raises(ArtifactError):
        await call(engine, 'observed', replace(lease, workspace_id='foreign'), call_id=receipt['id'],
            nonce=receipt['nonce'], usage=DocumentModelUsage())


async def test_aggregate_call_budget_and_nonce_ownership_are_enforced(engine, artifacts_database, object_store):
    lease = await ledger_lease(engine, artifacts_database['project_id'], object_store)
    for i in range(4):
        receipt = await call(engine, 'admit', **admission(lease, str(i)))
    with pytest.raises(ArtifactError) as error:
        await call(engine, 'admit', **admission(lease, 'fifth'))
    assert error.value.code == 'MODEL_BUDGET_EXCEEDED'
    with pytest.raises(ArtifactError) as error:
        await call(engine, 'dispatched', lease, receipt['id'], 'foreign-nonce')
    assert error.value.code == 'ARTIFACT_ACCESS_DENIED'
    with pytest.raises(ArtifactError):
        await call(engine, 'admit', **{**admission(lease), 'max_output_tokens': 4097})
