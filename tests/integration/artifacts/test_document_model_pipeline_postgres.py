"""Real storage/database/Core governance with a deterministic provider port.

These tests do not qualify a live provider; that acceptance is separate.
"""
import importlib
import json
from uuid import UUID, uuid4

import pytest

from langchain_core.messages import AIMessage
from sqlalchemy import select

from modules.agent.entrypoint import build_operation_model_runtime
from modules.agent.domain.entities import ProviderModel
from modules.agent.infra.database.models import ProviderCredentialModel
from modules.agent.infra.database.provider_model_repositories import SQLAlchemyProviderModelRepository
from modules.artifacts.background_boundary import build_processing_runner
from modules.artifacts.infra.database.models import ProcessingJobModel
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from modules.core.infra.database.configuration_resolution import ConfigurationResolution
from modules.metering.infra.database.models import UsageEventModel
from tests.integration.artifacts.test_http_postgres import http_client as http_client
from tests.integration.artifacts.test_profiles_postgres import create_profile
from tests.integration.artifacts.test_representations_postgres import prepared, completed
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store
from tests.unit.agent.test_operation_model_runtime import RecordingFactory, RecordingModel
from woobe_workers.settings import WorkerSettings


async def governed_reference(engine, project, settings, *, value='pipeline-private-fixture-material', model_name='fixture-model',
                             provider='openai', destination='https://api.openai.com/v1'):
    project, credential = UUID(str(project)), uuid4()
    async with ArtifactsUnitOfWork(engine) as uow:
        configuration = ConfigurationResolution(uow.session, encryption_key=settings.encryption_key)
        name = 'DOCUMENT_MODEL_' + uuid4().hex.upper()
        key = await configuration.declare(project_id=project, key=name)
        key_id = UUID(key['id'])
        await configuration.write_value(project_id=project, key_id=key_id, environment='staging', expected_revision=0, value=value)
        uow.session.add(ProviderCredentialModel(id=credential, project_id=project, provider=provider,
            name='Scoped document fixture ' + credential.hex, meta={'base_url': destination}, authentication={'type': 'api_key', 'fields': {
                'api_key': {'source': 'project_environment', 'key': name}}}))
        await uow.session.flush()
        model = await SQLAlchemyProviderModelRepository(uow.session).save(ProviderModel(project_id=project,
            provider_credential_id=credential, name='Document fixture model ' + credential.hex, model=model_name, model_type='language'))
        await configuration.grant_use(project_id=project, key_id=key_id, consumer_kind='provider_credential',
            consumer_scope=str(credential), destination=destination, environments=['staging'],
            field_paths=['/authentication/fields/api_key'], expected_revision=0, actor='fixture-owner')
    return {'configuration_key_id': str(key_id), 'configuration_revision': 1,
        'model_id': str(model.id), 'model_revision': 1}


class SummaryModel(RecordingModel):
    async def ainvoke(self, messages):
        self.messages = messages
        self.secret = await self.options['api_key'].resolve(self.options['base_url'] + '/chat/completions')
        payload = json.loads(messages[1].content)
        return AIMessage(content=json.dumps({'summaries': [{'text': 'Resumo inferido do trecho.',
            'fragment_ids': [payload['fragments'][0]['id']]}]}),
            usage_metadata={'input_tokens': 17, 'output_tokens': 5, 'total_tokens': 22})


class SummaryFactory(RecordingFactory):
    def create_chat_model(self, **options):
        model = SummaryModel(options)
        self.instances.append(model)
        return model


@pytest.mark.parametrize(('provider', 'destination'), [
    ('openai', 'https://api.openai.com/v1'),
    ('deepseek', 'https://api.deepseek.com'),
    ('openai_compatible', 'https://models.example/v1'),
])
async def test_governed_worker_summary_source_cache_and_idempotent_metering(engine, http_client, object_store, monkeypatch, provider, destination):
    client, wid, ref, original, path, body, old_job, params = await prepared(http_client, engine, object_store, monkeypatch)
    assert (await client.post(path + '/' + old_job['id'] + '/cancel', params=params)).status_code == 202
    settings = WorkerSettings.model_validate({})
    reference = await governed_reference(engine, http_client[3].project_id, settings, provider=provider, destination=destination)
    recipe = {'mode': 'extract_index', 'processor': {'name': 'native-text', 'version': '1'},
        'indexer': {'name': 'structural', 'version': '1'}, 'enricher': {'name': 'governed-model', 'version': '1'},
        'model': reference}
    profile = await create_profile(client, http_client[4], recipe=recipe)
    assert profile.status_code == 201, profile.text
    assert not profile.json()['ready'] and 'model_binding_not_verified' in profile.json()['diagnostics']
    body = {**body, 'operation_id': uuid4().hex, 'profile_id': profile.json()['id']}
    response = await client.post(path, params=params, json=body)
    assert response.status_code == 202, response.text
    job = response.json()
    factory = SummaryFactory()
    gateway = importlib.import_module('modules.artifacts.composition.document_model_gateway')
    monkeypatch.setattr(gateway, 'operation_model_runtime', lambda: build_operation_model_runtime(model_factory=factory))
    runner = build_processing_runner(engine, settings)
    await runner.run_once('governed-summary')
    done = await completed(client, path, job, params)
    assert done['status'] == 'succeeded', done
    assert len(factory.instances) == 1 and factory.instances[0].secret == 'pipeline-private-fixture-material'
    assert factory.instances[0].http_async_client.closed
    assert factory.instances[0].options['base_url'] == destination
    generation = done['result']['representation_set_id']
    base = f"/v1/artifacts/{ref['artifact_id']}/revisions/{ref['revision_id']}/representations/{generation}"
    entries = await client.get(base + '/entries', params=params)
    assert entries.status_code == 200, entries.text
    summary = next(item for item in entries.json()['items'] if item['path'] == 'summary.json')
    response = await client.get(base + '/entries/' + summary['id'] + '/content', params=params)
    assert response.status_code == 200, response.text
    inferred = response.json()
    assert inferred['inferred'] and inferred['trust'] == 'untrusted_model_derivative'
    source = inferred['summaries'][0]['sources'][0]
    read = await client.post('/v1/artifact-sources/read', params=params, json={'source': source})
    assert read.status_code == 200, read.text
    assert read.json()['text'] in original
    # Delivery is durable and can run without another processing job.
    await runner.run_once('metering-delivery')
    await runner.run_once('metering-redelivery')
    async with ArtifactsUnitOfWork(engine) as uow:
        row = await uow.session.get(ProcessingJobModel, job['id'])
        assert row.model_binding and 'pipeline-private-fixture-material' not in str(row.model_binding)
        assert row.model_binding['definition']['provider'] == provider
        assert row.model_binding['definition']['destination'] == destination
        events = (await uow.session.execute(select(UsageEventModel).where(UsageEventModel.project_id == http_client[3].project_id,
            UsageEventModel.data['job_id'].astext == job['id']))).scalars().all()
        assert len(events) == 1 and events[0].input_tokens == 17 and events[0].trace_id is None
    # A new operation with the exact accepted binding/source/recipe reuses the
    # coherent ready generation, without another provider call or usage event.
    response = await client.post(path, params=params, json={**body, 'operation_id': uuid4().hex})
    assert response.status_code == 202, response.text
    await runner.run_once('governed-cache')
    cached = await completed(client, path, response.json(), params)
    assert cached['status'] == 'succeeded', cached
    assert cached['result']['representation_set_id'] == generation and len(factory.instances) == 1


class FaultModel(SummaryModel):
    async def ainvoke(self, messages):
        self.secret = await self.options['api_key'].resolve(self.options['base_url'] + '/chat/completions')
        if self.options['fault'] == 'timeout':
            raise TimeoutError('Disposable transport timeout')
        return AIMessage(content='{"summaries":[{"text":"Untrusted response","fragment_ids":["foreign-document"]}]}',
            usage_metadata={'input_tokens': 23, 'output_tokens': 7, 'total_tokens': 30})


class FaultFactory(RecordingFactory):
    def __init__(self, fault):
        super().__init__()
        self.fault = fault

    def create_chat_model(self, **options):
        model = FaultModel({**options, 'fault': self.fault})
        self.instances.append(model)
        return model


@pytest.mark.parametrize('fault', ['invalid', 'timeout', 'revoked'])
async def test_failed_model_output_timeout_and_revocation_preserve_typed_state_and_usage(engine, http_client, object_store, monkeypatch, fault):
    from sqlalchemy import text
    from modules.artifacts.infra.database.model_operation_models import ArtifactDocumentModelCallModel as Call
    from modules.artifacts.infra.database.representation_models import ArtifactRepresentationSetModel as Generation
    client, wid, ref, original, path, body, old_job, params = await prepared(http_client, engine, object_store, monkeypatch)
    assert (await client.post(path + '/' + old_job['id'] + '/cancel', params=params)).status_code == 202
    settings = WorkerSettings.model_validate({})
    reference = await governed_reference(engine, http_client[3].project_id, settings)
    profile = await create_profile(client, http_client[4], recipe={
        'mode': 'extract', 'processor': {'name': 'native-text', 'version': '1'},
        'enricher': {'name': 'governed-model', 'version': '1'}, 'model': reference})
    assert profile.status_code == 201, profile.text
    response = await client.post(path, params=params, json={**body,
        'operation_id': uuid4().hex, 'profile_id': profile.json()['id']})
    assert response.status_code == 202, response.text
    job = response.json()
    if fault == 'revoked':
        async with ArtifactsUnitOfWork(engine) as uow:
            await uow.session.execute(text("UPDATE agent.provider_credentials SET status='revoked' WHERE id=(SELECT provider_credential_id FROM agent.provider_models WHERE id=:model)"),
                {'model': UUID(reference['model_id'])})
    factory = FaultFactory(fault)
    gateway = importlib.import_module('modules.artifacts.composition.document_model_gateway')
    monkeypatch.setattr(gateway, 'operation_model_runtime', lambda: build_operation_model_runtime(model_factory=factory))
    runner = build_processing_runner(engine, settings)
    await runner.run_once('governed-failure-' + fault)
    done = await completed(client, path, job, params)
    assert done['status'] == ('uncertain' if fault == 'timeout' else 'failed'), done
    assert done['error_code'] == {'invalid': 'MODEL_OUTPUT_INVALID', 'timeout': 'EXTERNAL_OPERATION_UNCERTAIN',
        'revoked': 'MODEL_BINDING_UNAVAILABLE'}[fault]
    await runner.run_once('usage-after-failure')
    async with ArtifactsUnitOfWork(engine) as uow:
        row = await uow.session.scalar(select(Call).where(Call.job_id == job['id']))
        if fault == 'revoked':
            assert row is None and not factory.instances
        else:
            assert row.state == ('uncertain' if fault == 'timeout' else 'failed')
            assert row.input_tokens == (None if fault == 'timeout' else 23)
            assert row.output_tokens == (None if fault == 'timeout' else 7)
            assert row.cost_usd is None and row.response is None
            assert factory.instances[0].http_async_client.closed
        assert not await uow.session.scalar(select(Generation).where(Generation.job_id == job['id'], Generation.status == 'ready'))
    await runner.run_once('no-blind-provider-retry')
    assert len(factory.instances) == (0 if fault == 'revoked' else 1)


async def test_concurrent_projects_keep_credentials_payloads_results_and_caches_scoped(engine, artifacts_database, object_store, monkeypatch):
    import asyncio
    from dataclasses import replace
    from sqlalchemy import text
    from modules.artifacts.application.contracts.jobs import ProcessingRequest, RequestProcessing
    from modules.artifacts.application.contracts.processing import ProcessingRecipe, ProfileCreate
    from modules.artifacts.composition import processing
    from modules.artifacts.composition.processing import _worker_phase
    from modules.artifacts.composition.resources import PROCESSING_REGISTRY
    from modules.artifacts.infra.database.model_operation_models import ArtifactDocumentModelCallModel as Call
    from modules.artifacts.infra.database.profiles import ProfileRepository
    from tests.integration.artifacts.test_files_postgres import prepare
    other_project = uuid4()
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text("INSERT INTO core.projects (id,workspace_id,name,slug,status,data) VALUES (:id,:workspace,'Model isolation fixture',:slug,'active','{}')"),
            {'id': other_project, 'workspace': uuid4(), 'slug': 'model-isolation-' + other_project.hex})
    settings = WorkerSettings.model_validate({})
    jobs, secrets = [], {}
    for project in (artifacts_database['project_id'], str(other_project)):
        files, write = await prepare(engine, project, object_store)
        label = 'document-for-project-' + project
        write = replace(write, text=label)
        published = await files.write_text(write)
        secret = 'private-isolation-fixture-' + project
        secrets[secret] = label
        reference = await governed_reference(engine, project, settings, value=secret)
        recipe = PROCESSING_REGISTRY.normalize(ProcessingRecipe.model_validate({
            'mode': 'extract', 'processor': {'name': 'native-text', 'version': '1'},
            'enricher': {'name': 'governed-model', 'version': '1'}, 'model': reference}))
        profile = ProfileCreate(id='isolation-' + uuid4().hex, revision=1, recipe=recipe)
        # Seed an approved immutable profile; public profile administration is
        # qualified separately. Job admission and live runtime authority remain real.
        async with ArtifactsUnitOfWork(engine) as uow:
            await uow.session.execute(text('UPDATE artifacts.workspaces SET quota_bytes=1048576 WHERE id=:id'), {'id': write.workspace_id})
            await ProfileRepository(uow).create(write.scope, profile)
        job = await _worker_phase(engine, settings, 'request')(RequestProcessing(write.principal, write.scope,
            write.workspace_id, published.receipt.artifact_id, ProcessingRequest(operation_id=uuid4().hex,
                revision_id=published.receipt.revision_id, profile_id=profile.id, profile_revision=1)))
        jobs.append(job)
    factory = SummaryFactory()
    gateway = importlib.import_module('modules.artifacts.composition.document_model_gateway')
    monkeypatch.setattr(gateway, 'operation_model_runtime', lambda: build_operation_model_runtime(model_factory=factory))
    monkeypatch.setattr(processing, 'upload_storage', lambda profile: object_store)
    runner = build_processing_runner(engine, settings)
    other_runner = build_processing_runner(engine, settings)
    # Match the real Worker registry: every concurrent slot owns its runner/UOWs.
    async def slot(owned_runner, name):
        for _ in range(10):
            identity = await owned_runner.run_once(name)
            if identity is not None:
                return identity
        raise AssertionError('A runnable isolated job was not claimed within ten polls')
    owners = await asyncio.gather(slot(runner, 'isolated-project-a'), slot(other_runner, 'isolated-project-b'))
    assert set(owners) == {job.id for job in jobs} and len(factory.instances) == 2
    for model in factory.instances:
        payload = json.loads(model.messages[1].content)
        assert payload['fragments'][0]['text'] == secrets[model.secret]
        assert model.http_async_client.closed
    async with ArtifactsUnitOfWork(engine) as uow:
        rows = (await uow.session.execute(select(ProcessingJobModel).where(ProcessingJobModel.id.in_([job.id for job in jobs])))).scalars().all()
        assert all(row.status == 'succeeded' for row in rows), [(row.status, row.error_code) for row in rows]
        assert len({row.result['representation_set_id'] for row in rows}) == 2
        assert len({row.processing_fingerprint for row in rows}) == 2
        calls = (await uow.session.execute(select(Call).where(Call.job_id.in_([job.id for job in jobs])))).scalars().all()
        assert len(calls) == 2 and len({call.binding_fingerprint for call in calls}) == 2
        assert len({call.input_fingerprint for call in calls}) == 2


async def test_paid_model_checkpoint_survives_failed_summary_storage_without_second_call(engine, http_client, object_store, monkeypatch):
    from sqlalchemy import text
    from modules.artifacts.infra.database.model_operation_models import ArtifactDocumentModelCallModel as Call
    from shared.contracts.object_storage import ObjectStorageError
    client, wid, ref, original, path, body, old_job, params = await prepared(http_client, engine, object_store, monkeypatch)
    assert (await client.post(path + '/' + old_job['id'] + '/cancel', params=params)).status_code == 202
    settings = WorkerSettings.model_validate({})
    reference = await governed_reference(engine, http_client[3].project_id, settings)
    profile = await create_profile(client, http_client[4], recipe={
        'mode': 'extract', 'processor': {'name': 'native-text', 'version': '1'},
        'enricher': {'name': 'governed-model', 'version': '1'}, 'model': reference})
    assert profile.status_code == 201, profile.text
    response = await client.post(path, params=params, json={**body,
        'operation_id': uuid4().hex, 'profile_id': profile.json()['id']})
    assert response.status_code == 202, response.text
    job = response.json()
    factory = SummaryFactory()
    gateway = importlib.import_module('modules.artifacts.composition.document_model_gateway')
    monkeypatch.setattr(gateway, 'operation_model_runtime', lambda: build_operation_model_runtime(model_factory=factory))
    actual_put = object_store.put
    async def fail_summary(key, *args, **kwargs):
        if '/summary-' in key:
            raise ObjectStorageError('unavailable', 'Disposable summary-storage fault after model acknowledgement')
        return await actual_put(key, *args, **kwargs)
    monkeypatch.setattr(object_store, 'put', fail_summary)
    await build_processing_runner(engine, settings).run_once('paid-call-before-storage-fault')
    pending = await completed(client, path, job, params)
    assert pending['status'] == 'queued' and pending['retryable'], pending
    async with ArtifactsUnitOfWork(engine) as uow:
        call = await uow.session.scalar(select(Call).where(Call.job_id == job['id']))
        assert call.state == 'completed' and call.input_tokens == 17
        await uow.session.execute(text('UPDATE artifacts.processing_jobs SET available_at=clock_timestamp() WHERE id=:id'), {'id': job['id']})
    monkeypatch.setattr(object_store, 'put', actual_put)
    # A freshly composed runner reloads the durable result, without any in-memory
    # provider cache or another transmission under the new fencing token.
    await build_processing_runner(engine, settings).run_once('recover-paid-model-checkpoint')
    done = await completed(client, path, job, params)
    assert done['status'] == 'succeeded' and done['attempt'] == 2, done
    assert len(factory.instances) == 1
    async with ArtifactsUnitOfWork(engine) as uow:
        call = await uow.session.scalar(select(Call).where(Call.job_id == job['id']))
        assert call.fencing_token == 1 and call.state == 'completed' and call.observation_revision == 1
