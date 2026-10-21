import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID
from uuid import uuid4

import pytest

from modules.artifacts.application.contracts.files import FileSnapshot
from modules.artifacts.domain.models import Artifact, Environment, Revision, Scope, Workspace
from shared.security.principal import ProjectApiPrincipal
from woobe_api.http.artifacts import routes


@pytest.mark.asyncio
async def test_workspace_export_manifest_streams_exact_hashes_and_download_links(monkeypatch):
    project_id, workspace_id, artifact_id, revision_id = map(str, (uuid4(), uuid4(), uuid4(), uuid4()))
    scope = Scope(project_id, Environment.STAGING)
    principal = ProjectApiPrincipal(
        api_key_id=uuid4(), project_id=UUID(project_id), key_prefix='test',
        authenticated_at=datetime.now(UTC),
    )
    workspace = Workspace(
        workspace_id, scope, 'tenant', 'customer-42', 'Documents', catalog_version=17,
    )
    artifact = Artifact(artifact_id, workspace_id, 'reports/annual report.pdf',
        revision_id=revision_id, version=4)
    revision = Revision(
        revision_id, artifact_id,
        f'projects/{project_id}/environments/staging/artifact-workspaces/{workspace_id}/'
        f'artifacts/{artifact_id}/revisions/{revision_id}/original',
        'application/pdf', 3, hashlib.sha256(b'pdf').hexdigest(), 'upload',
    )

    class Page:
        items = (artifact,)
        has_more = False
        next_cursor = None

    class Files:
        async def list(self, request):
            assert request.catalog_version == 17
            return Page()

        async def resolve(self, request):
            assert request.catalog_version == 17
            return FileSnapshot(artifact, revision, 'local')

    class Representations:
        async def resolve(self, request):
            from modules.artifacts.domain.models import ArtifactError
            raise ArtifactError('REPRESENTATION_NOT_READY', 'no derivative')

    async def no_index(request):
        from modules.artifacts.domain.models import ArtifactError
        raise ArtifactError('SOURCE_UNAVAILABLE', 'no index')

    async def get_workspace(request):
        return workspace

    monkeypatch.setattr(routes, 'get_workspace_composer', lambda: get_workspace)
    monkeypatch.setattr(routes, 'build_file_service', Files)
    monkeypatch.setattr(routes, 'build_representation_service', Representations)
    monkeypatch.setattr(routes, 'get_latest_document_index_composer', lambda: no_index)

    response = await routes.export_manifest(workspace_id, (principal, scope))
    chunks = [chunk async for chunk in response.body_iterator]
    payload = b''.join(chunks)
    records = [json.loads(line) for line in payload.splitlines()]
    assert records[0]['format'] == 'woobe.artifact-export.ndjson.v1'
    assert records[0]['catalog_version'] == 17
    original = next(item for item in records if item['record'] == 'original')
    assert original['revision_id'] == revision_id
    assert original['sha256'] == hashlib.sha256(b'pdf').hexdigest()
    assert 'artifact_workspace_id=' + workspace_id in original['content_url']
    assert 'object_key' not in original
    end = records[-1]
    assert end['record'] == 'end'
    assert end['records'] == len(records) - 1
    assert end['sha256'] == hashlib.sha256(b''.join(
        line + b'\n' for line in payload.splitlines()[:-1]
    )).hexdigest()


@pytest.mark.asyncio
async def test_workspace_export_manifest_includes_verified_derivative_and_index_records(monkeypatch):
    project_id, workspace_id, artifact_id, revision_id = map(str, (uuid4(), uuid4(), uuid4(), uuid4()))
    scope = Scope(project_id, Environment.DRAFT)
    principal = ProjectApiPrincipal(
        api_key_id=uuid4(), project_id=UUID(project_id), key_prefix='test',
        authenticated_at=datetime.now(UTC),
    )
    workspace = Workspace(workspace_id, scope, 'tenant', 'restore-test', 'Restore test', catalog_version=3)
    artifact = Artifact(artifact_id, workspace_id, 'notes.md', revision_id=revision_id)
    revision = Revision(
        revision_id, artifact_id,
        f'projects/{project_id}/environments/draft/artifact-workspaces/{workspace_id}/'
        f'artifacts/{artifact_id}/revisions/{revision_id}/original',
        'text/markdown', 4, hashlib.sha256(b'note').hexdigest(), 'upload',
    )
    generation = SimpleNamespace(
        id='representation-1', source_sha256=revision.sha256,
        recipe_fingerprint='a' * 64, processing_fingerprint='b' * 64,
        manifest_sha256='c' * 64, generation_number=2, coverage='complete', entry_count=1,
    )
    entry = SimpleNamespace(
        id='entry-1', path='markdown/notes.md', kind='markdown', size_bytes=4,
        sha256=hashlib.sha256(b'note').hexdigest(), content_type='text/markdown',
    )
    index = SimpleNamespace(
        id='index-1', engine='native-structural', engine_version='1',
        tree_kind='headings', coverage='complete', manifest_sha256='d' * 64, node_count=2,
    )

    class Page:
        items = (artifact,)
        has_more = False
        next_cursor = None

    class EntryPage:
        items = (entry,)
        has_more = False
        next_cursor = None

    class Files:
        async def list(self, request):
            return Page()

        async def resolve(self, request):
            return FileSnapshot(artifact, revision, 'local')

    class Representations:
        async def resolve(self, request):
            return SimpleNamespace(generation=generation)

        async def list_entries(self, request):
            assert request.representation_set_id == generation.id
            return EntryPage()

    async def get_workspace(request):
        return workspace

    async def get_index(request):
        return index

    monkeypatch.setattr(routes, 'get_workspace_composer', lambda: get_workspace)
    monkeypatch.setattr(routes, 'build_file_service', Files)
    monkeypatch.setattr(routes, 'build_representation_service', Representations)
    monkeypatch.setattr(routes, 'get_latest_document_index_composer', lambda: get_index)

    response = await routes.export_manifest(workspace_id, (principal, scope))
    rows = [json.loads(line) async for line in response.body_iterator]
    by_type = {item['record']: item for item in rows if item['record'] != 'end'}
    assert by_type['representation_set']['manifest_sha256'] == 'c' * 64
    assert by_type['representation_entry']['sha256'] == entry.sha256
    assert '/entries/entry-1/content?' in by_type['representation_entry']['content_url']
    assert by_type['document_index']['document_index_id'] == index.id
    assert by_type['document_index']['manifest_sha256'] == 'd' * 64
