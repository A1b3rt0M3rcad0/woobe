from uuid import uuid4

from sqlalchemy import text

from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from tests.integration.artifacts.test_http_postgres import http_client as http_client, provision
from tests.integration.artifacts.test_jobs_postgres import runner
from tests.integration.artifacts.test_uploads_postgres import object_store as object_store


async def test_processing_http_is_scoped_and_uses_the_existing_worker_path(http_client, engine, object_store):
    client, app, definition, actor, control, control_id = http_client
    workspace = await provision(client, definition)
    wid = workspace['id']
    published = await client.post('/v1/artifact-workspaces/' + wid + '/artifacts',
        json={'operation_id': uuid4().hex, 'kind': 'text', 'path': 'processing.txt', 'text': 'source bytes'})
    assert published.status_code == 201, published.text
    ref = published.json()['receipt']
    base = '/v1/artifacts/' + ref['artifact_id'] + '/processing'
    body = {'operation_id': uuid4().hex, 'revision_id': ref['revision_id']}
    requested = await client.post(base, json=body, params={'artifact_workspace_id': wid})
    assert requested.status_code == 202, requested.text
    job = requested.json()
    replay = await client.post(base, json=body, params={'artifact_workspace_id': wid})
    assert replay.json()['id'] == job['id']
    status_path = base + '/' + job['id']
    wrong = await client.get(status_path, params={'artifact_workspace_id': str(uuid4())})
    assert wrong.status_code == 403
    wrong_source = await client.get('/v1/artifacts/' + str(uuid4()) + '/processing/' + job['id'],
                                    params={'artifact_workspace_id': wid})
    assert wrong_source.status_code == 403
    await runner(engine, object_store).run_once('http-worker')
    complete = await client.get(status_path, params={'artifact_workspace_id': wid})
    assert complete.status_code == 200 and complete.json()['status'] == 'succeeded', complete.text
    assert complete.json()['result']['mode'] == 'store_only'
    assert 'principal_snapshot' not in complete.text and 'object_key' not in complete.text and 'fencing_token' not in complete.text
    another = await client.post(base, json={**body, 'operation_id': uuid4().hex}, params={'artifact_workspace_id': wid})
    cancelled = await client.post(base + '/' + another.json()['id'] + '/cancel', params={'artifact_workspace_id': wid})
    assert cancelled.status_code == 202 and cancelled.json()['status'] == 'cancelled', cancelled.text
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text("UPDATE core.api_keys SET interfaces='[\"http\"]' WHERE id=:id"), {'id': actor.api_key_id})
    assert (await client.get(status_path, params={'artifact_workspace_id': wid})).status_code == 403
