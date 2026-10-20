from modules.artifacts.application.authorization import principal_identity
from modules.artifacts.application.contracts.api import CursorEnvelope
from modules.artifacts.application.contracts.representations import RepresentationEntryPage
from modules.artifacts.domain.models import Action, ArtifactError, logical_path, opaque_id


class RepresentationUseCases:
    def __init__(self, store, authorization, cursors):
        self._store, self._authorization, self._cursors = store, authorization, cursors

    async def _authorize(self, request):
        opaque_id(request.workspace_id)
        await self._authorization.authorize(request.principal, request.scope, request.workspace_id, Action.READ)

    async def read(self, request):
        await self._authorize(request)
        return await self._store.read(request)

    async def source(self, request):
        await self._authorize(request)
        return await self._store.source(request)

    async def entries(self, request):
        await self._authorize(request)
        if request.representation_set_id is None:
            raise ArtifactError('REPRESENTATION_NOT_READY', 'Listing requires an exact representation generation')
        if not 1 <= request.limit <= 200:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Representation page limit must be between 1 and 200')
        if request.directory:
            logical_path(request.directory)
        fingerprint = self._cursors.fingerprint({'scope': request.scope.project_id,
            'environment': request.scope.environment.value, 'workspace': request.workspace_id,
            'artifact': request.artifact_id, 'revision': request.revision_id,
            'generation': request.representation_set_id, 'directory': request.directory,
            'principal': principal_identity(request.principal)})
        cursor = self._cursors.decode(request.cursor, fingerprint=fingerprint, purpose='representation_entries') if request.cursor else None
        _, rows = await self._store.entries(request, cursor.last_id if cursor else None)
        items, more = rows[:request.limit], len(rows) > request.limit
        token = self._cursors.encode(CursorEnvelope(scope_fingerprint=fingerprint, last_id=items[-1].id,
            catalog_version=0, purpose='representation_entries')) if more else None
        return RepresentationEntryPage(items=items, has_more=more, next_cursor=token)
