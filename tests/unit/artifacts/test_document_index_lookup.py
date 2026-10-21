import pytest

from modules.artifacts.application.contracts.indexes import ReadArtifactIndex
from modules.artifacts.application.use_cases.indexes import DocumentIndexUseCases
from modules.artifacts.domain.models import Environment, Scope


class _Authorization:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def authorize(self, principal, scope, workspace_id, action):
        self.calls.append((principal, scope, workspace_id, action))
        if self.error:
            raise self.error


class _IndexStore:
    def __init__(self):
        self.request = None

    async def latest_for_revision(self, request):
        self.request = request
        return {'id': 'index-1', 'revision_id': request.revision_id}


@pytest.mark.asyncio
async def test_revision_index_lookup_authorizes_before_resolving_exact_revision():
    principal = object()
    scope = Scope('project-1', Environment.DRAFT)
    request = ReadArtifactIndex(principal, scope, 'artifact-workspace-1', 'artifact-1', 'revision-7')
    authorization, store = _Authorization(), _IndexStore()

    result = await DocumentIndexUseCases(store, authorization, None).latest_for_revision(request)

    assert result == {'id': 'index-1', 'revision_id': 'revision-7'}
    assert authorization.calls[0][:3] == (principal, scope, 'artifact-workspace-1')
    assert store.request is request


@pytest.mark.asyncio
async def test_revision_index_lookup_never_reads_for_an_unauthorized_workspace():
    store = _IndexStore()
    use_cases = DocumentIndexUseCases(store, _Authorization(PermissionError('denied')), None)
    request = ReadArtifactIndex(object(), Scope('project-1', Environment.DRAFT),
        'artifact-workspace-2', 'artifact-1', 'revision-7')

    with pytest.raises(PermissionError):
        await use_cases.latest_for_revision(request)

    assert store.request is None
