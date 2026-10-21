from dataclasses import replace
from uuid import uuid4

import pytest

from modules.artifacts.application.contracts.jobs import ProcessingRequest, RequestProcessing
from modules.artifacts.application.contracts.processing import ComponentReference, ProcessingRecipe, ProfileCreate
from modules.artifacts.application.document_codec import decode_canonical
from modules.artifacts.application.contracts.uploads import UploadRequest
from modules.artifacts.background_boundary import build_processing_runner
from modules.artifacts.composition import processing
from modules.artifacts.infra.database.models import ProcessingJobModel, RevisionModel
from modules.artifacts.infra.database.profiles import ProfileRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from modules.artifacts.infra.processing.docling_manifest import docling_readiness
from shared.contracts.object_storage import read_bounded
from tests.fixtures.artifacts.pdf_sources import synthetic_pdf
from tests.integration.artifacts.test_jobs_postgres import execute, read_request
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store, setup, part
from woobe_workers.settings import WorkerSettings


@pytest.mark.parametrize('protected', [False, True])
@pytest.mark.parametrize('processor', ['native-pdf', pytest.param('docling-native',
    marks=pytest.mark.skipif(not docling_readiness()[0], reason='optional real Docling extra is not installed'))])
async def test_real_pdf_upload_worker_canonical_provenance_and_protection_error(engine, artifacts_database, object_store, monkeypatch, protected, processor):
    content = synthetic_pdf(encrypted=protected)
    api, begin, upload = await setup(engine, artifacts_database['project_id'], object_store, content, quota=1_048_576)
    await api.abort(upload)
    begin = replace(begin, definition=begin.definition.model_copy(update={
        'operation_id': uuid4().hex, 'path': 'manual.pdf', 'content_type': 'application/pdf'}))
    view = await api.begin(begin)
    upload = UploadRequest(begin.principal, begin.scope, begin.workspace_id, view.id)
    await api.append(part(upload, 0, content))
    receipt = (await api.finalize(upload)).receipt
    registry = processing.PROCESSING_REGISTRY
    recipe = registry.normalize(ProcessingRecipe(mode='extract', processor=ComponentReference(name=processor,
        version='1' if processor == 'native-pdf' else '2.140.0')))
    profile_id = uuid4().hex
    async with ArtifactsUnitOfWork(engine) as uow:
        await ProfileRepository(uow).create(begin.scope, ProfileCreate(id=profile_id, revision=1, recipe=recipe))
    request = RequestProcessing(begin.principal, begin.scope, begin.workspace_id, receipt.artifact_id,
        ProcessingRequest(operation_id=uuid4().hex, revision_id=receipt.revision_id, profile_id=profile_id, profile_revision=1))
    job = await execute(engine, 'request', request, registry=registry)
    monkeypatch.setattr(processing, 'upload_storage', lambda profile: object_store)
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('native-pdf-worker')
    complete = await execute(engine, 'read', read_request(request, job), registry=registry)
    async with ArtifactsUnitOfWork(engine) as uow:
        source = await uow.session.get(RevisionModel, receipt.revision_id)
        source_key = source.object_key
        row = await uow.session.get(ProcessingJobModel, job.id)
        checkpoints = row.checkpoints
    assert await read_bounded(object_store, source_key, max_bytes=1_048_576) == content
    if protected:
        assert complete.status == 'failed' and complete.error_code == 'PDF_PASSWORD_REQUIRED'
        assert not complete.retryable and 'extract' not in checkpoints
    else:
        assert complete.status == 'succeeded' and complete.result.coverage == 'partial'
        assert complete.result.page_count == 12
        canonical = await read_bounded(object_store, checkpoints['extract']['key'], max_bytes=1_048_576)
        document = decode_canonical(canonical)
        block = next(block for block in document.blocks if block.locator.page_index == 11)
        assert block.locator.page_number == 12 and 'física 12' in block.text
        assert document.pages[0].label == 'i' and document.pages[4].status == 'needs_ocr'
