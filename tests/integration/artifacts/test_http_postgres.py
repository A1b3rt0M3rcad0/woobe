from datetime import UTC, datetime, timedelta
import hashlib
import importlib
import json
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.artifacts.domain.models import Action, Scope, WorkspaceGrant
from modules.artifacts.infra.database.authorization import GrantRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.security.api_keys import issue_control_api_key, issue_runtime_api_key
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store
from tests.integration.artifacts.test_workspaces_postgres import prepare_namespace
from tests.integration.security.test_control_key_guard_postgres import _guard


def test_workspace_http_projection_does_not_expose_internal_retention_timestamps():
    from datetime import UTC, datetime

    from modules.artifacts.domain.models import Environment, Workspace
    from woobe_api.http.artifacts.transport import workspace_payload

    workspace = Workspace(
        id="projection-workspace",
        scope=Scope("projection-project", Environment.STAGING),
        external_namespace="projection",
        external_key="retention",
        name="Projection",
        archived_at=datetime.now(UTC),
    )
    payload = workspace_payload(workspace)
    assert "archived_at" not in payload
    assert "deletion_requested_at" not in payload


@pytest.fixture
async def http_client(engine, artifacts_database, object_store, monkeypatch):
    monkeypatch.setenv('WOOBE_TRUSTED_HOSTS', 'localhost,127.0.0.1,test')
    monkeypatch.setenv('WOOBE_CORS_ORIGINS', 'http://localhost:5173')
    actor, scope, definition = await prepare_namespace(engine, artifacts_database['project_id'])
    runtime = issue_runtime_api_key('staging')
    control = issue_control_api_key()
    control_id = uuid4()
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text('UPDATE core.api_keys SET key_prefix=:prefix,key_hash=:digest,key_version=:version WHERE id=:id'),
            {'prefix': runtime.public_prefix, 'digest': runtime.digest, 'version': runtime.key_version, 'id': actor.api_key_id})
        identity_workspace = await uow.session.scalar(text('SELECT workspace_id FROM core.projects WHERE id=:id'), {'id': UUID(scope.project_id)})
        await uow.session.execute(text("INSERT INTO identity.workspaces(id,name,slug,status) VALUES (:id,'Artifact HTTP fixture',:slug,'active') ON CONFLICT (id) DO NOTHING"),
            {'id': identity_workspace, 'slug': 'artifact-http-' + str(identity_workspace)})
        await uow.session.execute(text("""INSERT INTO core.workspace_control_keys
            (id,workspace_id,credential_id,name,key_prefix,key_hash,key_version,permissions,status,expires_at)
            VALUES (:id,:workspace,:id,'Artifact HTTP control',:prefix,:digest,:version,'[]','active',:expires)"""),
            {'id': control_id, 'workspace': identity_workspace, 'prefix': control.public_prefix,
             'digest': control.digest, 'version': control.key_version, 'expires': datetime.now(UTC) + timedelta(hours=1)})
        await uow.session.execute(text("""INSERT INTO core.workspace_control_key_project_grants
            (id,control_key_id,project_id,permissions,conditions) VALUES (:id,:key,:project,CAST(:permissions AS jsonb),'{"environments":["staging"]}')"""),
            {'id': uuid4(), 'key': control_id, 'project': UUID(scope.project_id),
             'permissions': json.dumps(['artifacts:' + value for value in ('read','write','delete','manage','process','search','transfer')])})
    for name in ('create_workspace','get_workspace','list_workspaces','resolve_workspace','update_workspace',
                 'create_workspace_grant','revoke_workspace_grant','get_file','list_files','mutate_file',
                 'begin_upload','get_upload','admit_upload','record_upload','verify_upload','commit_upload','abort_upload',
                 'create_processing_profile','get_processing_profile','list_processing_profiles',
                 'bind_processing_profile','select_processing_profile',
                 'request_processing','get_processing_job','cancel_processing_job'):
        module = importlib.import_module('modules.artifacts.composition.composers.' + name)
        monkeypatch.setattr(module, 'DATABASE_ENGINE', engine)
    for name in ('files', 'uploads'):
        module = importlib.import_module('modules.artifacts.composition.' + name)
        monkeypatch.setattr(module, 'upload_storage', lambda profile: object_store)
    import main
    monkeypatch.setattr(main, 'SETTINGS', main.SETTINGS.model_copy(update={
        'trusted_hosts': 'localhost,127.0.0.1,test', 'cors_origins': 'http://localhost:5173'}))
    app = main.create_app()
    app.state.security_guard = _guard(async_sessionmaker(engine, expire_on_commit=False), app.state.settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test',
        headers={'Authorization': 'Bearer ' + runtime.value},
        params={'project_id': scope.project_id, 'environment': scope.environment.value}) as client:
        yield client, app, definition, actor, control.value, control_id


async def provision(client, definition, **kwargs):
    response = await client.post('/v1/artifact-workspaces', json=definition.model_dump(mode='json'), **kwargs)
    assert response.status_code == 201, response.text
    return response.json()


async def test_real_http_provision_resume_download_rename_and_exact_history(http_client):
    client, app, definition, actor, control, control_id = http_client
    workspace = await provision(client, definition)
    assert workspace == await provision(client, definition)
    wid = workspace['id']
    base = f'/v1/artifact-workspaces/{wid}'
    resolved = await client.get('/v1/artifact-workspaces/resolve', params={
        'external_namespace': definition.external_namespace, 'external_key': definition.external_key})
    assert resolved.json()['id'] == wid
    content = 'Conteúdo através de HTTP\n'.encode()
    operation = uuid4().hex
    intent = {'operation_id': operation, 'path': 'relatórios/ação.txt', 'size_bytes': len(content),
              'sha256': hashlib.sha256(content).hexdigest(), 'content_type': 'text/plain'}
    response = await client.post(base + '/uploads', json=intent, headers={'Idempotency-Key': operation})
    assert response.status_code == 201, response.text
    uid = response.json()['id']
    for offset, chunk in ((0, content[:7]), (7, content[7:])):
        response = await client.put(base + f'/uploads/{uid}/parts', params={'offset': offset},
                                    content=chunk, headers={'Content-Type': 'application/octet-stream'})
        assert response.status_code == 200, response.text
    first = await client.post(base + f'/uploads/{uid}/finalize')
    assert first.status_code == 200, first.text
    replay = await client.post(base + f'/uploads/{uid}/finalize')
    assert replay.json()['receipt'] == first.json()['receipt']
    ref = first.json()['receipt']
    download = f"/v1/artifacts/{ref['artifact_id']}/revisions/{ref['revision_id']}/content"
    response = await client.get(download, params={'artifact_workspace_id': wid}, headers={'Range': 'bytes=2-8', 'Origin': 'http://localhost:5173'})
    assert response.status_code == 206, response.text
    assert response.content == content[2:9]
    assert response.headers['content-range'] == f'bytes 2-8/{len(content)}'
    assert 'no-store' in response.headers['cache-control']
    assert 'filename*=UTF-8' in response.headers['content-disposition']
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
    assert 'Content-Range' in response.headers['access-control-expose-headers']
    metadata = await client.get(base + f"/artifacts/{ref['artifact_id']}")
    assert metadata.status_code == 200, metadata.text
    assert all(field not in metadata.text for field in (
        'object_key', 'storage_version_id', 'external_operation_ref', 'source_refs',
        'archived_at', 'deletion_requested_at',
    ))
    move = await client.patch(base + f"/artifacts/{ref['artifact_id']}", json={
        'operation_id': uuid4().hex, 'expected_version': 1, 'path': 'relatórios/renomeado.txt'})
    assert move.status_code == 200 and move.json()['id'] == ref['artifact_id'], move.text
    full = await client.get(download, params={'artifact_workspace_id': wid})
    assert full.status_code == 200 and full.content == content
    history = await client.get(download.removesuffix('/content'), params={'artifact_workspace_id': wid})
    assert history.json()['sha256'] == intent['sha256']
    listing = await client.get(base + '/artifacts', params={'directory': 'relatórios', 'limit': 1})
    assert listing.status_code == 200 and listing.json()['items'][0]['id'] == ref['artifact_id']


async def test_http_control_permissions_runtime_interface_and_cross_scope_denials(http_client, engine):
    client, app, definition, actor, control, control_id = http_client
    workspace = await provision(client, definition, headers={'Authorization': 'Bearer ' + control})
    wid = workspace['id']
    # Control Keys are valid on reviewed direct Artifacts APIs, independently of Runtime Keys.
    response = await client.get(f'/v1/artifact-workspaces/{wid}', headers={'Authorization': 'Bearer ' + control})
    assert response.status_code == 200, response.text
    for params in ({'project_id': str(uuid4())}, {'environment': 'production'}):
        response = await client.get(f'/v1/artifact-workspaces/{wid}', params=params,
                                    headers={'Authorization': 'Bearer ' + control})
        assert response.status_code in {403, 404}, response.text
        response = await client.get(f'/v1/artifact-workspaces/{wid}', params=params)
        assert response.status_code in {403, 404}, response.text
    response = await client.get(f'/v1/artifact-workspaces/{wid}')
    assert response.status_code == 200, response.text
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text("UPDATE core.api_keys SET interfaces='[\"http\"]' WHERE id=:id"), {'id': actor.api_key_id})
    response = await client.get(f'/v1/artifact-workspaces/{wid}')
    assert response.status_code == 403, response.text
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text('UPDATE core.workspace_control_key_project_grants SET permissions=\'[]\' WHERE control_key_id=:id'), {'id': control_id})
    response = await client.get(f'/v1/artifact-workspaces/{wid}', headers={'Authorization': 'Bearer ' + control})
    assert response.status_code in {403,404}, response.text


async def test_http_cursor_ranges_limits_capabilities_cors_and_revocation(http_client, engine):
    client, app, definition, actor, control, control_id = http_client
    workspace = await provision(client, definition)
    wid = workspace['id']
    base = f'/v1/artifact-workspaces/{wid}'
    refs = []
    for index in range(2):
        response = await client.post(base + '/artifacts', json={'operation_id': uuid4().hex,
            'kind': 'text', 'path': f'{index}.txt', 'text': 'abcdef'})
        assert response.status_code == 201, response.text
        refs.append(response.json()['receipt'])
    page = await client.get(base + '/artifacts', params={'limit': 1})
    assert page.status_code == 200 and page.json()['has_more'], page.text
    response = await client.get(base + '/artifacts', params={'cursor': page.json()['next_cursor'] + 'x'})
    assert response.status_code == 400 and response.json()['code'] == 'ARTIFACT_INVALID_CURSOR'
    ref = refs[0]
    path = f"/v1/artifacts/{ref['artifact_id']}/revisions/{ref['revision_id']}/content"
    for invalid in ('bytes=100-200', 'bytes=0-1,3-4', 'bytes=-0', 'invalid'):
        response = await client.get(path, params={'artifact_workspace_id': wid}, headers={'Range': invalid})
        assert response.status_code == 416 and response.headers['content-range'] == 'bytes */6'
    response = await client.get(path, params={'artifact_workspace_id': wid}, headers={'Range': 'bytes=-2'})
    assert response.status_code == 206 and response.content == b'ef'
    response = await client.get(path, params={'artifact_workspace_id': wid}, headers={'Range': 'bytes=0-1', 'If-Range': '"other"'})
    assert response.status_code == 200 and response.content == b'abcdef'
    response = await client.get('/v1/artifact-capabilities')
    assert response.status_code == 200, response.text
    assert 'native-text' in response.json()['processors'] and not response.json()['signed_upload_urls']
    preflight = await client.options(path, headers={'Origin': 'http://localhost:5173',
        'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'authorization,range,if-range'})
    assert preflight.status_code == 200, preflight.text
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text("UPDATE core.api_keys SET status='revoked' WHERE id=:id"), {'id': actor.api_key_id})
    response = await client.get(path, params={'artifact_workspace_id': wid})
    assert response.status_code == 401, response.text
    response = await client.get(path, params={'artifact_workspace_id': wid}, headers={'Authorization': ''})
    assert response.status_code == 401


async def test_browser_login_logout_revokes_new_download_resolution(http_client, engine, monkeypatch):
    from modules.identity.infra.services.authentication_service import AuthenticationService
    from shared.infra.crypto import hash_password
    from woobe_api.http.identity import auth_endpoints

    client, app, definition, actor, control, control_id = http_client
    workspace = await provision(client, definition)
    wid = workspace['id']
    response = await client.post(f'/v1/artifact-workspaces/{wid}/artifacts', json={
        'operation_id': uuid4().hex, 'kind': 'text', 'path': 'browser.txt', 'text': 'private browser bytes'})
    ref = response.json()['receipt']
    path = f"/v1/artifacts/{ref['artifact_id']}/revisions/{ref['revision_id']}/content"
    uid, password = uuid4(), uuid4().hex + 'A!'
    email = str(uid) + '@example.test'
    async with ArtifactsUnitOfWork(engine) as uow:
        identity_workspace = await uow.session.scalar(text('SELECT workspace_id FROM core.projects WHERE id=:id'), {'id': actor.project_id})
        await uow.session.execute(text("INSERT INTO identity.users(id,email,password,status) VALUES (:id,:email,:password,'active')"),
                                  {'id': uid, 'email': email, 'password': hash_password(password)})
        await uow.session.execute(text("INSERT INTO identity.workspace_members(id,user_id,workspace_id,role,status,joined_at) VALUES (:id,:user,:workspace,'owner','active',now())"),
                                  {'id': uuid4(), 'user': uid, 'workspace': identity_workspace})
        await GrantRepository(uow).add(WorkspaceGrant(str(uuid4()), 'user-' + str(uid),
            Scope(str(actor.project_id), 'staging'), frozenset({Action.READ}), workspace_id=wid))
    authentication = AuthenticationService(engine, app.state.access_token_codec, app.state.settings)
    monkeypatch.setattr(auth_endpoints, 'authentication_service', lambda request: authentication)
    response = await client.post('/identity/auth/login', json={'email': email, 'password': password})
    assert response.status_code == 200, response.text
    saved_token = client.cookies.get(app.state.settings.access_cookie_name)
    assert saved_token
    del client.headers['authorization']
    response = await client.get(path, params={'artifact_workspace_id': wid})
    assert response.status_code == 200 and response.content == b'private browser bytes', response.text
    response = await client.post('/identity/auth/logout')
    assert response.status_code == 200, response.text
    response = await client.get(path, params={'artifact_workspace_id': wid})
    assert response.status_code == 401, response.text
    response = await client.get(path, params={'artifact_workspace_id': wid}, headers={'Authorization': 'Bearer ' + saved_token})
    assert response.status_code == 401, response.text


async def test_http_part_bound_and_ownership_before_body_and_grant_revocation(http_client, engine):
    client, app, definition, actor, control, control_id = http_client
    workspace = await provision(client, definition)
    wid = workspace['id']
    base = f'/v1/artifact-workspaces/{wid}'
    content = b'z' * 32
    intent = {'operation_id': uuid4().hex, 'path': 'data.bin', 'size_bytes': len(content),
              'sha256': hashlib.sha256(content).hexdigest(), 'content_type': 'application/octet-stream'}
    response = await client.post(base + '/uploads', json=intent)
    assert response.status_code == 201, response.text
    uid = response.json()['id']
    consumed = []

    async def body():
        consumed.append(True)
        yield b'not authorized'

    response = await client.put(base + f'/uploads/{uuid4().hex}/parts', params={'offset': 0}, content=body())
    assert response.status_code == 403 and not consumed, response.text
    cap = (await client.get('/v1/artifact-capabilities')).json()
    response = await client.put(base + f'/uploads/{uid}/parts', params={'offset': 0},
                                content=b'z' * (cap['max_upload_part_bytes'] + 1))
    assert response.status_code == 413, response.text
    response = await client.put(base + f'/uploads/{uid}/parts', params={'offset': 0}, content=content)
    assert response.status_code == 200, response.text
    response = await client.post(base + f'/uploads/{uid}/finalize')
    assert response.status_code == 200, response.text
    ref = response.json()['receipt']
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text('UPDATE artifacts.grants SET revoked=true WHERE principal_id=:subject'),
                                  {'subject': 'runtime-' + str(actor.api_key_id)})
    response = await client.get(f"/v1/artifacts/{ref['artifact_id']}/revisions/{ref['revision_id']}/content",
                                params={'artifact_workspace_id': wid})
    assert response.status_code == 403 and response.json()['code'] == 'ARTIFACT_ACCESS_DENIED', response.text


async def test_http_workspace_cas_namespace_grants_text_revision_and_delete(http_client):
    client, app, definition, actor, control, control_id = http_client
    namespace = 'http-' + uuid4().hex
    granted = await client.post('/v1/artifact-workspace-grants', headers={'Authorization': 'Bearer ' + control},
        json={'subject_id': 'runtime-' + str(actor.api_key_id), 'external_namespace': namespace,
              'actions': ['read', 'write', 'delete', 'manage']})
    assert granted.status_code == 201, granted.text
    grant_id = granted.json()['id']
    workspace = await provision(client, definition.model_copy(update={'external_namespace': namespace}))
    base = '/v1/artifact-workspaces/' + workspace['id']
    response = await client.patch(base, json={'expected_version': 1, 'name': 'Updated'}, headers={'If-Match': '"99"'})
    assert response.status_code == 409, response.text
    response = await client.patch(base, json={'expected_version': 1, 'name': 'Updated'}, headers={'If-Match': '"1"'})
    assert response.status_code == 200 and response.json()['version'] == 2, response.text
    response = await client.patch(base, json={'expected_version': 1, 'name': 'stale'})
    assert response.status_code == 409, response.text
    response = await client.post(base + '/artifacts', json={'operation_id': uuid4().hex,
        'kind': 'directory', 'path': 'empty'})
    assert response.status_code == 201 and response.json()['kind'] == 'directory', response.text
    directory = response.json()
    response = await client.post(base + '/artifacts', json={'operation_id': uuid4().hex,
        'kind': 'text', 'path': 'empty/test.txt', 'text': 'first', 'run_id': 'invented'})
    assert response.status_code == 422, response.text
    response = await client.post(base + '/artifacts', json={'operation_id': uuid4().hex,
        'kind': 'text', 'path': 'empty/test.txt', 'text': 'first'})
    assert response.status_code == 201, response.text
    ref = response.json()['receipt']
    update = {'operation_id': uuid4().hex, 'expected_revision': ref['revision_id'],
              'path': 'empty/test.txt', 'text': 'second'}
    target = base + '/artifacts/' + ref['artifact_id']
    response = await client.put(target + '/content', json=update)
    assert response.status_code == 200, response.text
    assert response.json()['receipt']['revision_id'] != ref['revision_id']
    response = await client.put(target + '/content', json=update)
    assert response.status_code == 200, response.text
    response = await client.delete(base + '/artifacts/' + directory['id'],
        params={'expected_version': 1}, headers={'Idempotency-Key': uuid4().hex})
    assert response.status_code == 409, response.text
    response = await client.delete(target, params={'expected_version': 2}, headers={'Idempotency-Key': uuid4().hex})
    assert response.status_code == 200 and response.json()['deleted'], response.text
    assert (await client.get(target)).status_code == 404
    response = await client.delete('/v1/artifact-workspace-grants/' + grant_id,
                                   headers={'Authorization': 'Bearer ' + control})
    assert response.status_code == 200, response.text
    assert (await client.get(base)).status_code == 403
