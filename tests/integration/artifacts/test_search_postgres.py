import hashlib
import importlib
from uuid import uuid4

from sqlalchemy import text

from modules.artifacts.background_boundary import build_processing_runner
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from tests.integration.artifacts.test_http_postgres import http_client as http_client
from tests.integration.artifacts.test_indexes_postgres import prepared_index
from tests.integration.artifacts.test_profiles_postgres import create_profile
from tests.integration.artifacts.test_representations_postgres import completed
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store
from woobe_workers.settings import WorkerSettings


async def prepare_search_document(http_client, engine, object_store, monkeypatch, *, content, process=True):
    client, wid, ref, _original, path, body, job, params, recipe = await prepared_index(
        http_client, engine, object_store, monkeypatch, content=content)
    composer = importlib.import_module('modules.artifacts.composition.composers.search_documents')
    monkeypatch.setattr(composer, 'DATABASE_ENGINE', engine)
    if process:
        await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('search-' + uuid4().hex)
        complete = await completed(client, path, job, params)
        assert complete['status'] == 'succeeded', complete
    return client, wid, ref, params, path, body, recipe, job


async def test_portuguese_path_literal_source_ref_and_empty_search(http_client, engine, object_store, monkeypatch):
    content = ('# Apêndice incomum\n\nAção extraordinária com referência 7391.\n\n'
        'Código exato: `x--y := 0xAF_42`.\n\nOutra ação extraordinária.\n\n'
        'Token normalizado: ＷＯＯＢＥ.')
    client, wid, ref, params, path, body, recipe, job = await prepare_search_document(
        http_client, engine, object_store, monkeypatch, content=content, process=False)
    endpoint = f'/v1/artifact-workspaces/{wid}/search'

    by_path = await client.get(endpoint, params={**params, 'query': 'manual', 'mode': 'text'})
    assert by_path.status_code == 200 and by_path.json()['items'], by_path.text
    unprocessed = by_path.json()['items'][0]
    assert unprocessed['path'] == 'manual.md' and unprocessed['match_location'] == 'path'
    assert unprocessed['coverage'] == 'unsupported' and unprocessed['source']['representation_set_id'] is None

    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('search-' + uuid4().hex)
    complete = await completed(client, path, job, params)
    assert complete['status'] == 'succeeded', complete

    response = await client.get(endpoint, params={**params, 'query': 'AÇÃO extraordinária'})
    assert response.status_code == 200, response.text
    page = response.json()
    assert page['items'] and all(item['revision_id'] == ref['revision_id'] for item in page['items'])
    assert all(item['source']['source_sha256'] == hashlib.sha256(content.encode()).hexdigest()
        for item in page['items'])
    assert all(len(item['snippet']) <= 512 for item in page['items'])
    source = page['items'][0]['source']
    read = await client.post('/v1/artifact-sources/read', params=params, json={'source': source})
    assert read.status_code == 200 and 'ação extraordinária' in read.json()['text'].casefold(), read.text

    literal = await client.get(endpoint, params={**params, 'query': 'x--y := 0xAF_42', 'mode': 'literal'})
    assert literal.status_code == 200 and literal.json()['items'], literal.text
    assert any('0xAF_42' in item['snippet'] for item in literal.json()['items'])

    normalized = await client.get(endpoint, params={**params, 'query': 'WOOBE', 'mode': 'text'})
    assert normalized.status_code == 200 and normalized.json()['items'], normalized.text

    by_path = await client.get(endpoint, params={**params, 'query': 'manual', 'mode': 'text'})
    assert by_path.status_code == 200 and by_path.json()['items'], by_path.text
    assert all(item['match_location'] == 'path' and item['path'] == 'manual.md'
        for item in by_path.json()['items'])

    duplicate = await client.post(f'/v1/artifact-workspaces/{wid}/artifacts', json={
        'operation_id': uuid4().hex, 'kind': 'text', 'path': 'appendix/manual.md',
        'text': 'Conteúdo de outra pasta.'})
    assert duplicate.status_code == 201, duplicate.text
    duplicate_ref = duplicate.json()['receipt']
    queued = await client.post(f"/v1/artifacts/{duplicate_ref['artifact_id']}/processing", params=params,
        json={**body, 'operation_id': uuid4().hex, 'revision_id': duplicate_ref['revision_id']})
    assert queued.status_code == 202, queued.text
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('search-duplicate-' + uuid4().hex)
    complete = await completed(client, f"/v1/artifacts/{duplicate_ref['artifact_id']}/processing",
        queued.json(), params)
    assert complete['status'] == 'succeeded', complete
    duplicate_paths = await client.get(endpoint, params={**params, 'query': 'manual', 'mode': 'text'})
    assert duplicate_paths.status_code == 200, duplicate_paths.text
    assert {item['path'] for item in duplicate_paths.json()['items']} == {'manual.md', 'appendix/manual.md'}
    assert len({item['artifact_id'] for item in duplicate_paths.json()['items']}) == 2

    missing = await client.get(endpoint, params={**params, 'query': 'termo inexistente 998877'})
    assert missing.status_code == 200 and missing.json()['items'] == []
    assert (await client.get(endpoint, params={**params, 'query': 'x', 'mode': 'literal'})).status_code == 422

    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text('SET LOCAL enable_seqscan=off'))
        plans = {}
        explanations = (
            ('fts', "EXPLAIN SELECT id FROM artifacts.source_segments WHERE search_vector @@ websearch_to_tsquery('simple', :query)", 'extraordinária'),
            ('literal', "EXPLAIN SELECT id FROM artifacts.source_segments WHERE search_normalized ILIKE :query ESCAPE '\\'", r'%0xAF\_42%'),
            ('path', "EXPLAIN SELECT id FROM artifacts.head_history WHERE to_tsvector('simple'::regconfig, normalize(regexp_replace(path, '[^[:alnum:]]+', ' ', 'g'), NFKC)) @@ websearch_to_tsquery('simple', :query)", 'manual'),
        )
        for name, statement, query in explanations:
            plans[name] = '\n'.join((await uow.session.execute(text(statement), {'query': query})).scalars())
        assert 'ix_artifact_source_segment_search_vector' in plans['fts'], plans['fts']
        assert 'ix_artifact_source_segment_search_literal' in plans['literal'], plans['literal']
        assert 'ix_artifact_history_search_path' in plans['path'], plans['path']


async def test_search_cursor_pins_revision_and_generation_and_rejects_tampering_and_foreign_workspace(
        http_client, engine, object_store, monkeypatch):
    content = ('# Apêndice\n\nAção alfa 271828.\n\nAção beta 314159.\n\nAção gama 161803.')
    client, wid, ref, params, path, body, recipe, _job = await prepare_search_document(
        http_client, engine, object_store, monkeypatch, content=content)
    endpoint = f'/v1/artifact-workspaces/{wid}/search'
    first = await client.get(endpoint, params={**params, 'query': 'ação', 'limit': 1})
    assert first.status_code == 200 and first.json()['has_more'], first.text
    token = first.json()['next_cursor']
    assert token

    # Publish another extraction of this revision after the first page. The
    # cursor must keep using its original immutable search snapshot.
    control = http_client[4]
    revised_profile = await create_profile(client, control,
        recipe={**recipe, 'parameters': {'preserve_blank_lines': False}})
    assert revised_profile.status_code == 201, revised_profile.text
    queued = await client.post(path, params=params, json={**body, 'operation_id': uuid4().hex,
        'profile_id': revised_profile.json()['id'], 'profile_revision': 1})
    assert queued.status_code == 202, queued.text
    await build_processing_runner(engine, WorkerSettings.model_validate({})).run_once('search-reindex-' + uuid4().hex)
    complete = await completed(client, path, queued.json(), params)
    assert complete['status'] == 'succeeded', complete

    updated = await client.put(f"/v1/artifact-workspaces/{wid}/artifacts/{ref['artifact_id']}/content", json={
        'operation_id': uuid4().hex, 'path': 'manual.md', 'expected_revision': ref['revision_id'],
        'text': 'Revisão nova sem o termo anterior.'})
    assert updated.status_code == 200, updated.text

    second = await client.get(endpoint, params={**params, 'query': 'ação', 'limit': 1, 'cursor': token})
    assert second.status_code == 200 and second.json()['items'], second.text
    assert all(item['revision_id'] == ref['revision_id'] for item in second.json()['items'])
    first_generation = first.json()['items'][0]['source']['representation_set_id']
    assert all(item['source']['representation_set_id'] == first_generation
        for item in second.json()['items'])

    tampered = await client.get(endpoint, params={**params, 'query': 'ação', 'cursor': token + 'x'})
    assert tampered.status_code == 400 and tampered.json()['code'] == 'ARTIFACT_INVALID_CURSOR', tampered.text

    foreign = await client.get(f"/v1/artifact-workspaces/{uuid4().hex}/search",
        params={**params, 'query': 'ação'})
    assert foreign.status_code == 403 and foreign.json()['code'] == 'ARTIFACT_ACCESS_DENIED', foreign.text
