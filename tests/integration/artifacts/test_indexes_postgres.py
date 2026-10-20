import hashlib
import importlib
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
import pytest

from modules.artifacts.background_boundary import build_processing_runner
from modules.artifacts.infra.database.index_models import ArtifactDocumentIndexModel as IndexRoot, ArtifactDocumentNodeModel as Node
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from modules.artifacts.infra.database.representation_models import ArtifactRepresentationSetModel as Generation
from tests.integration.artifacts.test_http_postgres import http_client as http_client
from tests.integration.artifacts.test_profiles_postgres import create_profile
from tests.integration.artifacts.test_representations_postgres import prepared, completed
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store
from woobe_workers.settings import WorkerSettings


async def prepared_index(http_client, engine, store, monkeypatch, *, content=None, media='text/markdown', processor='native-text'):
    client, wid, ref, original, path, body, job, params = await prepared(http_client, engine, store, monkeypatch)
    cancelled = await client.post(path + '/' + job['id'] + '/cancel', params=params)
    assert cancelled.status_code == 202
    for name in ('get_document_index', 'get_document_node', 'list_document_nodes'):
        module = importlib.import_module('modules.artifacts.composition.composers.' + name)
        monkeypatch.setattr(module, 'DATABASE_ENGINE', engine)
    text = content or '# 章一 😀\n\nIntrodução com ação.\n\n### Repetido\n\nTexto A.\n\n### Repetido\n\nTexto B.\n\n## Outra seção\n\nConclusão.\n'
    content = text.encode() if isinstance(text, str) else text
    base = f'/v1/artifact-workspaces/{wid}/uploads'
    filename = 'manual.pdf' if media == 'application/pdf' else 'manual.txt' if media == 'text/plain' else 'manual.md'
    upload = await client.post(base, json={'operation_id': uuid4().hex, 'path': filename,
        'size_bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(), 'content_type': media})
    assert upload.status_code == 201, upload.text
    uploaded = await client.put(base + '/' + upload.json()['id'] + '/parts', params={'offset': 0},
        content=content, headers={'Content-Type': 'application/octet-stream'})
    assert uploaded.status_code == 200, uploaded.text
    published = await client.post(base + '/' + upload.json()['id'] + '/finalize')
    assert published.status_code == 200, published.text
    ref = published.json()['receipt']
    recipe = {'mode': 'extract_index', 'processor': {'name': processor, 'version': '1'},
              'indexer': {'name': 'structural', 'version': '1'}}
    profile = await create_profile(client, http_client[4], recipe=recipe)
    assert profile.status_code == 201 and profile.json()['ready'], profile.text
    path = '/v1/artifacts/' + ref['artifact_id'] + '/processing'
    body = {'operation_id': uuid4().hex, 'revision_id': ref['revision_id'],
            'profile_id': profile.json()['id'], 'profile_revision': 1}
    requested = await client.post(path, params=params, json=body)
    assert requested.status_code == 202, requested.text
    return client, wid, ref, text, path, body, requested.json(), params, recipe


async def page_children(client, base, params, parent, *, limit=2):
    items, cursor = [], None
    while True:
        response = await client.get(base + '/nodes', params={**params, 'parent_id': parent,
            'limit': limit, **({'cursor': cursor} if cursor else {})})
        assert response.status_code == 200, response.text
        page = response.json()
        items.extend(page['items'])
        if not page['has_more']:
            return items
        cursor = page['next_cursor']


async def test_real_structural_worker_tree_signed_pages_exact_sources_reprocess_and_historical_revision(http_client, engine, object_store, monkeypatch):
    client, wid, ref, original, path, body, job, params, recipe = await prepared_index(http_client, engine, object_store, monkeypatch)
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('native-structural-tree')
    complete = await completed(client, path, job, params)
    assert complete['status'] == 'succeeded', complete
    result = complete['result']
    assert result['mode'] == 'extract_index' and result['document_index_id'] and result['representation_set_id']
    base = '/v1/document-indexes/' + result['document_index_id']
    response = await client.get(base, params=params)
    assert response.status_code == 200, response.text
    index = response.json()
    assert index['engine'] == 'structural' and index['tree_kind'] == 'headings' and index['read_only']
    assert index['source_sha256'] == hashlib.sha256(original.encode()).hexdigest()
    assert 'object_key' not in response.text and 'fencing_token' not in response.text
    roots = await client.get(base + '/nodes', params=params)
    assert roots.status_code == 200 and len(roots.json()['items']) == 1, roots.text
    root = roots.json()['items'][0]
    assert root['id'] == index['root_node_id'] and not root['has_own_text'] and root['source'] is None
    assert (await client.get(base + '/nodes/' + root['id'] + '/content', params=params)).status_code == 404
    chapters = await page_children(client, base, params, root['id'])
    assert len(chapters) == 1 and chapters[0]['title'] == '章一 😀'
    children = await page_children(client, base, params, chapters[0]['id'], limit=1)
    repeated = [node for node in children if node['title'] == 'Repetido']
    assert len(repeated) == 2 and repeated[0]['id'] != repeated[1]['id']
    assert all(node['depth'] == 2 for node in children)
    leaves = await page_children(client, base, params, repeated[0]['id'])
    text_leaves = [node for node in leaves if node['title'].startswith('Texto A.')]
    assert len(text_leaves) == 1 and text_leaves[0]['has_own_text']
    leaf = text_leaves[0]
    source = leaf['source']
    assert source['document_index_id'] == index['id'] and source['node_id'] == leaf['id']
    content = await client.get(base + '/nodes/' + leaf['id'] + '/content', params={**params, 'max_chars': 4})
    assert content.status_code == 200 and content.json()['text'] == 'Text', content.text
    assert content.json()['truncated']
    forged = {**source, 'node_id': repeated[1]['id']}
    assert (await client.post('/v1/artifact-sources/read', params=params, json={'source': forged})).status_code == 404
    first_page = await client.get(base + '/nodes', params={**params, 'parent_id': chapters[0]['id'], 'limit': 1})
    cursor = first_page.json()['next_cursor']
    changed_parent = await client.get(base + '/nodes', params={**params, 'parent_id': root['id'], 'cursor': cursor})
    assert changed_parent.status_code == 400
    async with ArtifactsUnitOfWork(engine) as uow:
        assert await uow.session.scalar(select(func.count()).select_from(IndexRoot).where(IndexRoot.workspace_id == wid)) == 1
        assert await uow.session.scalar(select(func.count()).select_from(Node).where(Node.document_index_id == index['id'])) == index['node_count']
    with pytest.raises(DBAPIError):
        async with ArtifactsUnitOfWork(engine) as uow:
            await uow.session.execute(text("UPDATE artifacts.document_nodes SET title='tampered' WHERE document_index_id=:id"), {'id': index['id']})
    # Same exact ready generation/index is reused without parsing.
    from modules.artifacts.infra.processing.native_text import NativeTextProcessor
    process = NativeTextProcessor.process
    async def unexpected(*args, **kwargs):
        raise AssertionError('ready indexed result must avoid parsing again')
    monkeypatch.setattr(NativeTextProcessor, 'process', unexpected)
    cached = await client.post(path, params=params, json={**body, 'operation_id': uuid4().hex})
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('cached-native-tree')
    cached = await completed(client, path, cached.json(), params)
    assert cached['status'] == 'succeeded' and cached['result']['document_index_id'] == index['id'], cached
    monkeypatch.setattr(NativeTextProcessor, 'process', process)
    revised_profile = await create_profile(client, http_client[4], recipe={**recipe, 'parameters': {'preserve_blank_lines': False}})
    assert revised_profile.status_code == 201, revised_profile.text
    newer = await client.post(path, params=params, json={**body, 'operation_id': uuid4().hex, 'profile_id': revised_profile.json()['id']})
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('new-native-tree')
    newer = await completed(client, path, newer.json(), params)
    assert newer['status'] == 'succeeded' and newer['result']['document_index_id'] != index['id'], newer
    changed = await client.put(f"/v1/artifact-workspaces/{wid}/artifacts/{ref['artifact_id']}/content", json={
        'operation_id': uuid4().hex, 'path': 'manual.md', 'expected_revision': ref['revision_id'], 'text': 'Nova revisão.'})
    assert changed.status_code == 200, changed.text
    assert (await client.get(base, params=params)).status_code == 200
    historic = await client.get(base + '/nodes/' + leaf['id'] + '/content', params=params)
    assert historic.status_code == 200 and 'Texto A.' in historic.json()['text'], historic.text
    assert historic.json()['source']['revision_id'] == ref['revision_id']


async def test_large_native_leaf_reads_only_bounded_unicode_segments_without_whole_document_load(http_client, engine, object_store, monkeypatch):
    original = ('漢😀 ação ' * 100 + '\n') * 100
    client, wid, ref, original, path, body, job, params, recipe = await prepared_index(http_client, engine,
        object_store, monkeypatch, content=original, media='text/plain')
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('large-native-leaf')
    complete = await completed(client, path, job, params)
    assert complete['status'] == 'succeeded', complete
    base = '/v1/document-indexes/' + complete['result']['document_index_id']
    index = (await client.get(base, params=params)).json()
    assert index['tree_kind'] == 'blocks'
    leaves = await page_children(client, base, params, index['root_node_id'])
    assert len(leaves) == 1
    opened = []
    open_stream = object_store.open
    def observed(key, **kwargs):
        opened.append((key, kwargs))
        return open_stream(key, **kwargs)
    monkeypatch.setattr(object_store, 'open', observed)
    response = await client.get(base + '/nodes/' + leaves[0]['id'] + '/content', params={
        **params, 'offset': 70001, 'max_chars': 19})
    assert response.status_code == 200, response.text
    assert response.json()['text'] == original[70001:70020]
    assert response.json()['next_offset'] == 70020
    assert opened and all('/block-text-' in key and 0 < options['end'] - options['start'] <= 16_384 for key, options in opened)


@pytest.mark.parametrize('fault', ['index_manifest', 'final_transaction'])
async def test_index_failure_cannot_publish_partial_generation_or_ready_event(http_client, engine, object_store, monkeypatch, fault):
    from dataclasses import replace
    from modules.artifacts.infra.database.indexes import DocumentIndexRepository
    client, wid, ref, original, path, body, job, params, recipe = await prepared_index(http_client, engine, object_store, monkeypatch)
    runner = build_processing_runner(engine, WorkerSettings.model_validate({}))
    if fault == 'index_manifest':
        phase = runner._publication_phase
        async def corrupt(name, request):
            if name == 'seal_index':
                request = replace(request, value={**request.value, 'metadata_fingerprint': '0' * 64})
            return await phase(name, request)
        runner._publication_phase = corrupt
    else:
        commit = DocumentIndexRepository.commit_ready
        async def fail_after_ready(self, *args):
            await commit(self, *args)
            raise RuntimeError('Injected rollback after ready generation and index mutations')
        monkeypatch.setattr(DocumentIndexRepository, 'commit_ready', fail_after_ready)
    await runner.run_once('index-fault-worker')
    complete = await completed(client, path, job, params)
    assert complete['status'] in {'failed', 'queued'} and complete['result'] is None, complete
    if complete['status'] == 'queued':
        assert (await client.post(path + '/' + job['id'] + '/cancel', params=params)).status_code == 202
    async with ArtifactsUnitOfWork(engine) as uow:
        assert await uow.session.scalar(select(func.count()).select_from(Generation).where(Generation.workspace_id == wid, Generation.status == 'ready')) == 0
        assert await uow.session.scalar(select(func.count()).select_from(IndexRoot).where(IndexRoot.workspace_id == wid, IndexRoot.status == 'ready')) == 0
        from modules.artifacts.infra.database.models import ArtifactEventModel, RevisionModel, WorkspaceModel
        from modules.artifacts.infra.database.representation_models import ArtifactStoredObjectModel
        assert await uow.session.scalar(select(func.count()).select_from(ArtifactEventModel).where(
            ArtifactEventModel.workspace_id == wid, ArtifactEventModel.kind.in_(['artifact.representations.ready','artifact.document_index.ready']))) == 0
        workspace = await uow.session.get(WorkspaceModel, wid)
        originals = await uow.session.scalar(select(func.sum(RevisionModel.size_bytes)).where(RevisionModel.workspace_id == wid))
        outputs = await uow.session.scalar(select(func.sum(ArtifactStoredObjectModel.size_bytes)).where(
            ArtifactStoredObjectModel.workspace_id == wid, ArtifactStoredObjectModel.accounting_bucket == 'used'))
        assert outputs > 0 and workspace.used_bytes == originals + outputs and workspace.reserved_bytes == 0


async def test_index_sealed_recovery_skips_rebuilding_and_current_scope_protects_nodes(http_client, engine, object_store, monkeypatch):
    from datetime import UTC, datetime, timedelta
    from modules.artifacts.application.contracts.jobs import ProcessingLeaseLost
    from modules.artifacts.infra.database.models import ProcessingJobModel
    from modules.artifacts.application.services import index_pipeline
    client, wid, ref, original, path, body, job, params, recipe = await prepared_index(http_client, engine, object_store, monkeypatch)
    runner = build_processing_runner(engine, WorkerSettings.model_validate({}))
    finish, captured = runner._finish, []
    async def lose_ack(phase):
        captured.append(phase)
        return True
    runner._finish = lose_ack
    await runner.run_once('index-before-lost-completion')
    assert len(captured) == 1 and captured[0].publication.get('document_index_id')
    index_id = captured[0].publication['document_index_id']
    async with ArtifactsUnitOfWork(engine) as uow:
        index = await uow.session.get(IndexRoot, index_id)
        assert index.sealed and index.status == 'building'
        (await uow.session.get(ProcessingJobModel, job['id'])).lease_until = datetime.now(UTC) - timedelta(seconds=1)
    assert (await client.get('/v1/document-indexes/' + index_id, params=params)).status_code == 404
    with pytest.raises(ProcessingLeaseLost):
        await finish(captured[0])
    def unexpected(*args, **kwargs):
        raise AssertionError('sealed structural index must not be rebuilt')
    monkeypatch.setattr(index_pipeline, 'build_structural_index', unexpected)
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('index-after-lost-completion')
    complete = await completed(client, path, job, params)
    assert complete['status'] == 'succeeded' and complete['result']['document_index_id'] == index_id, complete
    base = '/v1/document-indexes/' + index_id
    index = (await client.get(base, params=params)).json()
    assert (await client.get(base, params={**params, 'artifact_workspace_id': uuid4().hex})).status_code == 403
    nodes = await client.get(base + '/nodes', params=params)
    assert nodes.status_code == 200
    async with ArtifactsUnitOfWork(engine) as uow:
        assert (await uow.session.get(IndexRoot, index_id)).publication_fencing_token == 2
        await uow.session.execute(text("UPDATE core.api_keys SET interfaces='[\"http\"]' WHERE id=:id"), {'id': http_client[3].api_key_id})
    assert (await client.get(base, params=params)).status_code == 403
    assert (await client.get(base + '/nodes/' + index['root_node_id'], params=params)).status_code == 403


async def test_real_native_pdf_uses_explicit_physical_page_fallback_including_empty_scanned_pages(http_client, engine, object_store, monkeypatch):
    from tests.fixtures.artifacts.pdf_sources import synthetic_pdf
    client, wid, ref, original, path, body, job, params, recipe = await prepared_index(http_client, engine, object_store,
        monkeypatch, content=synthetic_pdf(), media='application/pdf', processor='native-pdf')
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('native-pdf-page-tree')
    complete = await completed(client, path, job, params)
    assert complete['status'] == 'succeeded', complete
    base = '/v1/document-indexes/' + complete['result']['document_index_id']
    response = await client.get(base, params=params)
    assert response.status_code == 200, response.text
    index = response.json()
    assert index['tree_kind'] == 'pages' and index['coverage'] == 'partial'
    pages = await page_children(client, base, params, index['root_node_id'], limit=3)
    assert len(pages) == 12 and all(page['kind'] == 'page' and page['source'] is None for page in pages)
    assert pages[0]['title'] == 'Página física 1 (i)'
    assert pages[11]['title'] == 'Página física 12 (10)'
    physical_twelve = await page_children(client, base, params, pages[11]['id'])
    textual = [node for node in physical_twelve if node['has_own_text']]
    assert textual and all(node['source']['locator']['page_index'] == 11 for node in textual)
    assert all(node['extraction_method'] == 'native' and not node['inferred'] for node in textual)
    assert all(node['source']['locator']['page_number'] == 12 for node in textual)
    read = await client.get(base + '/nodes/' + textual[0]['id'] + '/content', params=params)
    assert read.status_code == 200 and 'física 12' in read.json()['text'], read.text
    assert (await page_children(client, base, params, pages[3]['id'])) == []
