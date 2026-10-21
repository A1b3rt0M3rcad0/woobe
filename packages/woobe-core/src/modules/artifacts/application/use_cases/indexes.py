from modules.artifacts.application.authorization import principal_identity
from modules.artifacts.application.contracts.api import CursorEnvelope
from modules.artifacts.application.contracts.indexes import DocumentNodePage
from modules.artifacts.domain.models import Action, ArtifactError, opaque_id


class DocumentIndexUseCases:
    def __init__(self, store, authorization, cursors):
        self._store, self._authorization, self._cursors = store, authorization, cursors

    async def _authorize(self, request):
        opaque_id(request.index_id)
        await self._authorization.authorize(request.principal, request.scope, request.workspace_id, Action.READ)

    async def read(self, request):
        await self._authorize(request)
        return await self._store.read(request)

    async def latest_for_revision(self, request):
        await self._authorization.authorize(request.principal, request.scope, request.workspace_id, Action.READ)
        return await self._store.latest_for_revision(request)

    async def node(self, request):
        await self._authorize(request)
        opaque_id(request.node_id)
        return await self._store.node(request)

    async def nodes(self, request):
        await self._authorize(request)
        if request.parent_id is not None:
            opaque_id(request.parent_id)
        if not 1 <= request.limit <= 200:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Document node page limit must be between 1 and 200')
        fingerprint = self._cursors.fingerprint({'project': request.scope.project_id,
            'environment': request.scope.environment.value, 'workspace': request.workspace_id,
            'index': request.index_id, 'parent': request.parent_id, 'title_query': request.title_query,
            'principal': principal_identity(request.principal)})
        cursor = self._cursors.decode(request.cursor, fingerprint=fingerprint, purpose='index_nodes') if request.cursor else None
        after = int(cursor.last_id) if cursor is not None else None
        items = await self._store.nodes(request, after)
        more, items = len(items) > request.limit, items[:request.limit]
        token = self._cursors.encode(CursorEnvelope(scope_fingerprint=fingerprint, purpose='index_nodes',
            last_id=str(items[-1].ordinal), catalog_version=0)) if more else None
        return DocumentNodePage(items=items, has_more=more, next_cursor=token)
