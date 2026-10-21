import hashlib
from uuid import uuid4

import pytest

from modules.artifacts.background_boundary import build_processing_runner
from modules.artifacts.domain.models import ArtifactError
from modules.artifacts.infra.indexers.pageindex_runner import PageIndexRunner
from tests.fixtures.artifacts.pdf_sources import pageindex_outline_pdf
from tests.integration.artifacts.test_http_postgres import http_client as http_client, provision
from tests.integration.artifacts.test_indexes_postgres import page_children, prepared_index
from tests.integration.artifacts.test_representations_postgres import completed
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store
from woobe_workers.settings import WorkerSettings


@pytest.mark.asyncio
async def test_real_pageindex_worker_publishes_pinned_outline_and_reuses_the_exact_generation(
        http_client, engine, object_store, monkeypatch):
    original = pageindex_outline_pdf()
    client, workspace_id, revision, _text, path, body, job, params, recipe = await prepared_index(
        http_client, engine, object_store, monkeypatch, content=original, media='application/pdf',
        processor='native-pdf', indexer={'name': PageIndexRunner.name, 'version': PageIndexRunner.version})
    assert recipe['indexer']['name'] == 'pageindex-flash'
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('pageindex-local-outline')
    complete = await completed(client, path, job, params)
    assert complete['status'] == 'succeeded', complete
    result = complete['result']
    base = '/v1/document-indexes/' + result['document_index_id']
    response = await client.get(base, params=params)
    assert response.status_code == 200, response.text
    index = response.json()
    assert index['engine'] == 'pageindex-flash' and index['engine_version'] == PageIndexRunner.version
    assert index['tree_kind'] == 'headings' and index['coverage'] == 'complete'
    foreign_definition = http_client[2].model_copy(update={'external_key': 'foreign-' + uuid4().hex})
    foreign_workspace = await provision(client, foreign_definition)
    foreign_params = {**params, 'artifact_workspace_id': foreign_workspace['id']}
    assert (await client.get(base, params=foreign_params)).status_code in {403, 404}
    assert (await client.get(base + '/nodes', params=foreign_params)).status_code in {403, 404}
    roots = await client.get(base + '/nodes', params=params)
    root = roots.json()['items'][0]
    root_children = await page_children(client, base, params, root['id'], limit=10)
    sections = [node for node in root_children if node['kind'] == 'section']
    assert [node['title'] for node in sections] == ['1 Introduction', '2 Methods']
    assert any(node['title'] == 'Sample Technical Report' and node['kind'] == 'block'
        for node in root_children)
    introduction = sections[0]
    assert introduction['source']['locator']['page_index'] == 1
    assert introduction['source']['locator']['page_number'] == 2
    read = await client.get(base + '/nodes/' + introduction['id'] + '/content', params=params)
    assert read.status_code == 200 and '1 Introduction' in read.json()['text']
    method_children = await page_children(client, base, params, sections[1]['id'], limit=10)
    methods = [node for node in method_children if node['kind'] == 'section']
    assert [node['title'] for node in methods] == ['2.1 Data', '2.2 Review']
    assert all(node['depth'] == 2 for node in methods)
    assert index['source_sha256'] == hashlib.sha256(original).hexdigest()
    assert workspace_id and revision['revision_id']

    async def unexpected(*args, **kwargs):
        raise AssertionError('a sealed PageIndex generation must be reused without starting the adapter')
    monkeypatch.setattr(PageIndexRunner, 'index', unexpected)
    cached = await client.post(path, params=params, json={**body, 'operation_id': uuid4().hex})
    assert cached.status_code == 202, cached.text
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('pageindex-cache-hit')
    reused = await completed(client, path, cached.json(), params)
    assert reused['status'] == 'succeeded'
    assert reused['result']['document_index_id'] == index['id']


@pytest.mark.asyncio
async def test_explicit_structural_fallback_records_the_engine_that_ran(
        http_client, engine, object_store, monkeypatch):
    original = pageindex_outline_pdf()
    client, _workspace_id, _revision, _text, path, _body, job, params, _recipe = await prepared_index(
        http_client, engine, object_store, monkeypatch, content=original, media='application/pdf',
        processor='native-pdf', indexer={'name': PageIndexRunner.name, 'version': PageIndexRunner.version})
    async def unavailable(*args, **kwargs):
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Injected deterministic adapter failure')
    monkeypatch.setattr(PageIndexRunner, 'index', unavailable)
    # The fallback is opt-in and participates in the immutable recipe identity.
    from tests.integration.artifacts.test_profiles_postgres import create_profile
    profile = await create_profile(client, http_client[4], recipe={
        'mode': 'extract_index', 'processor': {'name': 'native-pdf', 'version': '1'},
        'indexer': {'name': PageIndexRunner.name, 'version': PageIndexRunner.version},
        'parameters': {'indexer_fallback': 'structural'}})
    assert profile.status_code == 201 and profile.json()['ready'], profile.text
    uploaded = await client.post(path, params=params, json={'operation_id': uuid4().hex,
        'revision_id': _revision['revision_id'], 'profile_id': profile.json()['id'], 'profile_revision': 1})
    assert uploaded.status_code == 202, uploaded.text
    runner = build_processing_runner(engine, WorkerSettings.model_validate({}))
    complete = None
    for attempt in range(3):
        await runner.run_once(f'pageindex-explicit-fallback-{attempt}')
        complete = await completed(client, path, uploaded.json(), params)
        if complete['status'] != 'queued':
            break
    assert complete['status'] == 'succeeded', complete
    index = await client.get('/v1/document-indexes/' + complete['result']['document_index_id'], params=params)
    assert index.status_code == 200 and index.json()['engine'] == 'structural'
