from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from modules.artifacts.application.contracts.files import ListFiles
from modules.artifacts.application.contracts.search import SearchDocuments, SearchQueryResult
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.use_cases.files import FileUseCases
from modules.artifacts.application.use_cases.search import ArtifactSearchUseCases
from modules.artifacts.domain.models import Artifact, ArtifactError, Environment, Scope, Workspace
from shared.security.principal import AuthenticatedPrincipal


def _principal():
    now = datetime.now(UTC)
    return AuthenticatedPrincipal(user_id=uuid4(), session_id=uuid4(),
        issued_at=now, expires_at=now + timedelta(hours=1))


class _Authorization:
    def __init__(self, workspace):
        self.workspace = workspace

    async def authorize(self, *_args):
        return self.workspace


class _Store:
    def __init__(self):
        self.page_versions = []
        self.search_requests = []

    async def page(self, _scope, workspace_id, *, directory, catalog_version, after, limit):
        self.page_versions.append(catalog_version)
        rows = (
            Artifact('artifact-a', workspace_id, 'a.txt', revision_id='revision-a'),
            Artifact('artifact-b', workspace_id, 'b.txt', revision_id='revision-b'),
        )
        return tuple(item for item in rows if after is None or item.id > after)[:limit]

    async def search(self, request):
        self.search_requests.append(request)
        return SearchQueryResult(search_version=1, hits=())


@pytest.mark.asyncio
async def test_listing_cursor_remains_bound_to_the_acceptance_catalog_version():
    scope = Scope('project-pin', Environment.STAGING)
    workspace = Workspace('workspace-pin', scope, 'pin-tests', 'workspace', 'Pinned', catalog_version=12)
    store = _Store()
    use_cases = FileUseCases(store, _Authorization(workspace), CursorCodec(b'x' * 32))
    principal = _principal()

    first = await use_cases.page(ListFiles(principal, scope, workspace.id, limit=1, catalog_version=7))
    assert first.has_more and store.page_versions == [7]
    await use_cases.page(ListFiles(principal, scope, workspace.id, limit=1,
        cursor=first.next_cursor, catalog_version=7))
    assert store.page_versions == [7, 7]

    with pytest.raises(ArtifactError) as switched:
        await use_cases.page(ListFiles(principal, scope, workspace.id, limit=1,
            cursor=first.next_cursor, catalog_version=8))
    assert switched.value.code == 'ARTIFACT_INVALID_CURSOR'
    with pytest.raises(ArtifactError):
        await use_cases.page(ListFiles(principal, scope, workspace.id, catalog_version=13))


@pytest.mark.asyncio
async def test_search_uses_acceptance_version_instead_of_current_catalog():
    scope = Scope('project-pin', Environment.STAGING)
    workspace = Workspace('workspace-pin', scope, 'pin-tests', 'workspace', 'Pinned', catalog_version=12)
    store = _Store()
    use_cases = ArtifactSearchUseCases(store, _Authorization(workspace), CursorCodec(b'y' * 32))

    result = await use_cases.search(SearchDocuments(_principal(), scope, workspace.id,
        query='chapter', catalog_version=7))
    assert result.catalog_version == 7
    assert store.search_requests[0].catalog_version == 7
