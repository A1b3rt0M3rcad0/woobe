import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from uuid import uuid4

import pytest

from modules.artifacts.application.contracts.jobs import ProcessingRequest, RequestProcessing
from modules.artifacts.application.contracts.processing import ComponentReference, ProcessingRecipe, ProfileCreate
from modules.artifacts.application.contracts.uploads import UploadRequest
from modules.artifacts.application.document_codec import decode_canonical
from modules.artifacts.application.processing_registry import ProcessingRegistry
from modules.artifacts.background_boundary import build_processing_runner
from modules.artifacts.composition import processing
from modules.artifacts.infra.database.models import ProcessingJobModel, RevisionModel
from modules.artifacts.infra.database.profiles import ProfileRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from modules.artifacts.infra.processing.native_document import NativeDocumentProcessor
from modules.artifacts.infra.processing.native_registry import native_document_descriptor, tesseract_descriptor
from modules.artifacts.infra.processing.ocr_manifest import ocr_readiness
from shared.contracts.object_storage import read_bounded
from tests.integration.artifacts.test_jobs_postgres import execute, read_request
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store, setup, part
from woobe_workers.settings import WorkerSettings


DATA = os.environ.get('WOOBE_ARTIFACT_TEST_OCR_DATA_DIR')
EXECUTABLE = os.environ.get('WOOBE_ARTIFACT_TEST_TESSERACT_EXECUTABLE', '/usr/bin/tesseract')
pytestmark = pytest.mark.skipif(not ocr_readiness(DATA, EXECUTABLE)[0], reason='real qualified OCR installation is not configured')


async def prepare_ocr(engine, project_id, store, content, media, monkeypatch):
    api, begin, upload = await setup(engine, project_id, store, content, quota=4_194_304)
    await api.abort(upload)
    begin = replace(begin, definition=begin.definition.model_copy(update={
        'operation_id': uuid4().hex, 'path': 'source.data', 'content_type': media}))
    view = await api.begin(begin)
    upload = UploadRequest(begin.principal, begin.scope, begin.workspace_id, view.id)
    await api.append(part(upload, 0, content))
    reference = (await api.finalize(upload)).receipt
    registry = ProcessingRegistry((native_document_descriptor(), tesseract_descriptor(DATA, EXECUTABLE)))
    recipe = registry.normalize(ProcessingRecipe(mode='extract',
        processor=ComponentReference(name='native-document', version='1'),
        ocr=ComponentReference(name='native-tesseract', version='1')))
    assert recipe.parameters.languages == ('por', 'eng')
    identity = uuid4().hex
    async with ArtifactsUnitOfWork(engine) as uow:
        await ProfileRepository(uow).create(begin.scope, ProfileCreate(id=identity, revision=1, recipe=recipe))
    request = RequestProcessing(begin.principal, begin.scope, begin.workspace_id, reference.artifact_id,
        ProcessingRequest(operation_id=uuid4().hex, revision_id=reference.revision_id, profile_id=identity, profile_revision=1))
    monkeypatch.setattr(processing, 'PROCESSING_REGISTRY', registry)
    monkeypatch.setattr(processing, 'upload_storage', lambda profile: store)
    settings = WorkerSettings.model_validate({'artifact_ocr_data_dir': DATA,
        'artifact_tesseract_executable': EXECUTABLE, 'artifact_processing_lease_seconds': 3})
    job = await execute(engine, 'request', request, registry=registry)
    return request, job, registry, settings


@pytest.mark.parametrize('media,hybrid_page', [('image/png', False), ('application/pdf', False), ('application/pdf', True)])
async def test_real_ocr_job_preserves_original_and_publishes_verified_private_visual_checkpoint(engine, artifacts_database, object_store, monkeypatch, media, hybrid_page):
    from tests.fixtures.artifacts.ocr_sources import PORTUGUESE, hybrid_page_pdf, hybrid_pdf, portuguese_image
    content = hybrid_page_pdf() if hybrid_page else portuguese_image() if media == 'image/png' else hybrid_pdf()
    request, job, registry, settings = await prepare_ocr(engine, artifacts_database['project_id'], object_store, content, media, monkeypatch)
    await build_processing_runner(engine, settings).run_once('actual-ocr-worker')
    complete = await execute(engine, 'read', read_request(request, job), registry=registry)
    assert complete.status == 'succeeded' and complete.result.coverage == 'partial'
    async with ArtifactsUnitOfWork(engine) as uow:
        source = await uow.session.get(RevisionModel, request.definition.revision_id)
        source_key = source.object_key
        row = await uow.session.get(ProcessingJobModel, job.id)
        checkpoint = row.checkpoints['extract']
    assert await read_bounded(object_store, source_key, max_bytes=4_194_304) == content
    document = decode_canonical(await read_bounded(object_store, checkpoint['key'], max_bytes=4_194_304))
    assert [block.text for block in document.blocks if block.extraction_method == 'ocr'] == list(PORTUGUESE)
    metadata = checkpoint['asset_manifest']
    manifest_bytes = await read_bounded(object_store, metadata['key'], max_bytes=4_194_304)
    assert hashlib.sha256(manifest_bytes).hexdigest() == metadata['sha256']
    manifest = json.loads(manifest_bytes)
    assert len(manifest['assets']) == checkpoint['asset_count'] == len(document.assets) == 1
    for entry in manifest['assets']:
        value = await read_bounded(object_store, entry['key'], max_bytes=67_108_864)
        assert hashlib.sha256(value).hexdigest() == entry['asset']['sha256']
        assert len(value) == entry['asset']['size_bytes']
    assert complete.result.representation_set_id is not None  # coherent immutable bundle is now published


async def test_lost_ocr_checkpoint_ack_resumes_without_rerunning_real_recognition(engine, artifacts_database, object_store, monkeypatch):
    from tests.fixtures.artifacts.ocr_sources import portuguese_image
    request, job, registry, settings = await prepare_ocr(engine, artifacts_database['project_id'], object_store,
        portuguese_image(), 'image/png', monkeypatch)
    calls = []
    original = NativeDocumentProcessor.process
    async def counted(self, *args, **kwargs):
        calls.append(True)
        return await original(self, *args, **kwargs)
    monkeypatch.setattr(NativeDocumentProcessor, 'process', counted)
    phase = processing._worker_phase
    def lose_ack(engine, settings, method):
        handler = phase(engine, settings, method)
        async def call(command):
            value = await handler(command)
            if method == 'checkpoint' and command.stage == 'extract':
                raise ConnectionError('injected after durable real OCR and visual checkpoint')
            return value
        return call
    monkeypatch.setattr(processing, '_worker_phase', lose_ack)
    await build_processing_runner(engine, settings).run_once('ocr-before-ack-loss')
    async with ArtifactsUnitOfWork(engine) as uow:
        row = await uow.session.get(ProcessingJobModel, job.id)
        assert row.status == 'queued' and row.checkpoints['extract']['asset_count'] == 1
        row.available_at = datetime.now(UTC) - timedelta(seconds=1)
    monkeypatch.setattr(processing, '_worker_phase', phase)
    await build_processing_runner(engine, settings).run_once('ocr-after-restart')
    complete = await execute(engine, 'read', read_request(request, job), registry=registry)
    assert complete.status == 'succeeded' and complete.attempt == 2 and len(calls) == 1


async def test_cancelled_ocr_job_confirms_only_after_owned_processing_resources_stop(engine, artifacts_database, object_store, monkeypatch):
    from tests.fixtures.artifacts.ocr_sources import portuguese_image
    request, job, registry, settings = await prepare_ocr(engine, artifacts_database['project_id'], object_store,
        portuguese_image(dense=True), 'image/png', monkeypatch)
    entered = asyncio.Event()
    original = NativeDocumentProcessor.process
    async def active(self, *args, **kwargs):
        entered.set()
        return await original(self, *args, **kwargs)
    monkeypatch.setattr(NativeDocumentProcessor, 'process', active)
    task = asyncio.create_task(build_processing_runner(engine, settings).run_once('ocr-cancel'))
    await asyncio.wait_for(entered.wait(), timeout=10)
    cancel = await execute(engine, 'cancel', read_request(request, job), registry=registry)
    assert cancel.status == 'cancel_requested'
    await asyncio.wait_for(task, timeout=20)
    complete = await execute(engine, 'read', read_request(request, job), registry=registry)
    assert complete.status == 'cancelled' and complete.result is None
