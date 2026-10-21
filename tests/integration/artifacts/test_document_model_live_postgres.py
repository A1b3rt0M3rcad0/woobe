"""Explicit opt-in live acceptance through the same Worker/runtime/Core path.

Run with --tb=no: credentials belong only in the secure environment binding.
A skipped test is not evidence that the provider path has been qualified.
"""
import os
from uuid import uuid4

import pytest
from sqlalchemy import select

from modules.artifacts.background_boundary import build_processing_runner
from modules.artifacts.infra.database.model_operation_models import ArtifactDocumentModelCallModel as Call
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from tests.integration.artifacts.test_document_model_pipeline_postgres import governed_reference
from tests.integration.artifacts.test_http_postgres import http_client as http_client
from tests.integration.artifacts.test_profiles_postgres import create_profile
from tests.integration.artifacts.test_representations_postgres import prepared, completed
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store
from woobe_workers.settings import WorkerSettings
from tests.support.artifact_model_live import live_model_settings


@pytest.mark.skipif(os.environ.get('WOOBE_ARTIFACT_RUN_LIVE_MODEL') != '1', reason='Authorized live-provider acceptance requires explicit opt-in')
async def test_authorized_provider_document_summary_through_governed_runtime(engine, http_client, object_store, monkeypatch):
    try:
        selected = live_model_settings()
    except ValueError as error:
        pytest.fail(str(error), pytrace=False)
    assert selected is not None
    client, wid, ref, original, path, body, old_job, params = await prepared(http_client, engine, object_store, monkeypatch)
    assert (await client.post(path + '/' + old_job['id'] + '/cancel', params=params)).status_code == 202
    settings = WorkerSettings.model_validate({})
    reference = await governed_reference(engine, http_client[3].project_id, settings,
        value=selected.credential, model_name=selected.model, provider=selected.provider, destination=selected.destination)
    del selected
    profile = await create_profile(client, http_client[4], recipe={
        'mode': 'extract_index', 'processor': {'name': 'native-text', 'version': '1'},
        'indexer': {'name': 'structural', 'version': '1'}, 'enricher': {'name': 'governed-model', 'version': '1'},
        'model': reference, 'limits': {'max_output_tokens': 512}})
    assert profile.status_code == 201
    requested = await client.post(path, params=params, json={**body,
        'operation_id': uuid4().hex, 'profile_id': profile.json()['id']})
    assert requested.status_code == 202
    await build_processing_runner(engine, settings).run_once('authorized-live-document-model')
    job = await completed(client, path, requested.json(), params)
    assert job['status'] == 'succeeded'
    assert job['result']['document_index_id'] and job['result']['representation_set_id']
    async with ArtifactsUnitOfWork(engine) as uow:
        call = await uow.session.scalar(select(Call).where(Call.job_id == job['id']))
        assert call.state == 'completed' and call.input_tokens is not None and call.output_tokens is not None
        assert call.output_tokens <= 512 and call.response['summaries']
