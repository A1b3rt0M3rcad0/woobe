import asyncio
from dataclasses import replace
import importlib
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from modules.artifacts.application.contracts.processing import ComponentReference, ProcessingRecipe
from modules.artifacts.application.processing_registry import ComponentDescriptor, ProcessingRegistry
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from tests.integration.artifacts.test_http_postgres import http_client as http_client, provision
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store


async def create_profile(client, control, *, identity=None, revision=1, recipe=None):
    value = {'id': identity or 'profile-' + uuid4().hex, 'revision': revision,
             'recipe': recipe or {'mode': 'store_only'}}
    return await client.post('/v1/artifact-processing-profiles', json=value,
                              headers={'Authorization': 'Bearer ' + control})


async def test_profiles_are_scoped_immutable_and_default_selection_is_cas(http_client, engine):
    client, app, definition, actor, control, control_id = http_client
    identity = 'profile-' + uuid4().hex
    first, replay = await asyncio.gather(create_profile(client, control, identity=identity),
                                         create_profile(client, control, identity=identity))
    assert first.status_code == replay.status_code == 201, first.text
    assert first.json()['fingerprint'] == replay.json()['fingerprint'] and first.json()['ready']
    conflict = await create_profile(client, control, identity=identity,
        recipe={'mode': 'store_only', 'parameters': {'preserve_blank_lines': False}})
    assert conflict.status_code == 409, conflict.text
    newer = await create_profile(client, control, identity=identity, revision=2,
        recipe={'mode': 'store_only', 'parameters': {'preserve_blank_lines': False}})
    assert newer.status_code == 201 and newer.json()['fingerprint'] != first.json()['fingerprint']
    workspace = await provision(client, definition)
    base = '/v1/artifact-workspaces/' + workspace['id'] + '/processing-profile'
    selected = await client.get(base)
    assert selected.status_code == 200 and selected.json()['mode'] == 'store_only'
    bound = await client.put(base, json={'expected_version': 1, 'profile_id': identity, 'profile_revision': 1})
    assert bound.status_code == 200 and bound.json()['version'] == 2, bound.text
    selected = await client.get(base)
    assert selected.json()['profile']['revision'] == 1
    explicit = await client.get(base, params={'profile_id': identity, 'profile_revision': 2})
    assert explicit.json()['profile']['revision'] == 2
    stale = await client.put(base, json={'expected_version': 1, 'profile_id': identity, 'profile_revision': 2})
    assert stale.status_code == 409
    missing = await client.put(base, json={'expected_version': 2, 'profile_id': 'not-found', 'profile_revision': 1})
    assert missing.status_code == 404
    reset = await client.put(base, json={'expected_version': 2})
    assert reset.status_code == 200 and reset.json()['default_profile_id'] is None
    assert (await client.get(base)).json()['mode'] == 'store_only'
    runtime_create = await client.post('/v1/artifact-processing-profiles', json={'id': 'denied', 'revision': 1, 'recipe': {}})
    assert runtime_create.status_code == 403
    wrong_scope = await client.get('/v1/artifact-processing-profiles/' + identity + '/revisions/1', params={'environment': 'production'})
    assert wrong_scope.status_code == 403
    with pytest.raises(DBAPIError):
        async with ArtifactsUnitOfWork(engine) as uow:
            await uow.session.execute(text('UPDATE artifacts.processing_profiles SET fingerprint=:fingerprint WHERE project_id=:project AND environment=\'staging\' AND id=:id'),
                {'fingerprint': '0' * 64, 'project': actor.project_id, 'id': identity})
    with pytest.raises(IntegrityError):
        async with ArtifactsUnitOfWork(engine) as uow:
            await uow.session.execute(text('UPDATE artifacts.workspaces SET default_profile_id=:id,default_profile_revision=1,environment=\'production\' WHERE id=:workspace'),
                {'id': identity, 'workspace': workspace['id']})


async def test_profile_pages_filters_and_import_do_not_execute_a_processor(http_client, monkeypatch):
    client, app, definition, actor, control, control_id = http_client
    unavailable = ComponentDescriptor('optional-uninstalled', '1', 'processor', 'original', 'canonical',
        frozenset({'application/pdf'}), available=False, diagnostic='dependency_not_installed')
    registry = ProcessingRegistry((unavailable,))
    for name in ('create_processing_profile','get_processing_profile','list_processing_profiles', 'select_processing_profile'):
        module = importlib.import_module('modules.artifacts.composition.composers.' + name)
        monkeypatch.setattr(module, 'PROCESSING_REGISTRY', registry)
    recipe = ProcessingRecipe(mode='extract', processor=ComponentReference(name='optional-uninstalled', version='1'))
    response = await create_profile(client, control, recipe=recipe.model_dump(mode='json'))
    assert response.status_code == 201 and not response.json()['ready'], response.text
    assert 'dependency_not_installed' in response.json()['diagnostics'][0]
    optional_id = response.json()['id']
    for _ in range(2):
        assert (await create_profile(client, control)).status_code == 201
    page = await client.get('/v1/artifact-processing-profiles', params={'limit': 1})
    assert page.status_code == 200 and page.json()['has_more'], page.text
    ids = set()
    while True:
        ids.update(item['id'] for item in page.json()['items'])
        if not page.json()['has_more']:
            break
        page = await client.get('/v1/artifact-processing-profiles', params={'limit': 1, 'cursor': page.json()['next_cursor']})
    assert len(ids) >= 3 and optional_id in ids
    invalid = await client.get('/v1/artifact-processing-profiles', params={'cursor': 'tampered'})
    assert invalid.status_code == 400
    invalid_recipe = await create_profile(client, control, recipe={'api_key': 'cannot persist secrets'})
    assert invalid_recipe.status_code == 422
    wrong_limit = replace(unavailable, max_pages=1)
    module = importlib.import_module('modules.artifacts.composition.composers.create_processing_profile')
    monkeypatch.setattr(module, 'PROCESSING_REGISTRY', ProcessingRegistry((wrong_limit,)))
    response = await create_profile(client, control, recipe=recipe.model_dump(mode='json'))
    assert response.status_code == 413
    # Existing immutable configuration remains readable if its plugin disappears.
    get_module = importlib.import_module('modules.artifacts.composition.composers.get_processing_profile')
    monkeypatch.setattr(get_module, 'PROCESSING_REGISTRY', ProcessingRegistry())
    response = await client.get('/v1/artifact-processing-profiles/' + optional_id + '/revisions/1')
    assert response.status_code == 200
    assert not response.json()['ready'] and response.json()['diagnostics'] == ['registered_recipe_unavailable']


async def test_profile_revision_bounds_are_validated_before_postgres_conversion(http_client, engine):
    client, app, definition, actor, control, control_id = http_client
    response = await client.get('/v1/artifact-processing-profiles/profile/revisions/9223372036854775808')
    assert response.status_code == 422, response.text
    workspace = await provision(client, definition)
    response = await client.put('/v1/artifact-workspaces/' + workspace['id'] + '/processing-profile',
        json={'expected_version': 1, 'profile_id': 'profile', 'profile_revision': 9223372036854775808})
    assert response.status_code == 422, response.text
    with pytest.raises(IntegrityError):
        async with ArtifactsUnitOfWork(engine) as uow:
            await uow.session.execute(text("INSERT INTO artifacts.processing_profiles(project_id,environment,id,revision,fingerprint,recipe) VALUES (:project,'invalid','bad',1,:fingerprint,'{}')"),
                {'project': actor.project_id, 'fingerprint': 'a' * 64})
