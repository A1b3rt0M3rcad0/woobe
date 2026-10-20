from modules.artifacts.application.authorization import ArtifactAuthorization, principal_identity
from modules.artifacts.application.contracts.api import CursorEnvelope
from modules.artifacts.application.contracts.files import ListFiles, MutateFile, ReadFile
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.ports.files import FileStore
from modules.artifacts.domain.models import Action, ArtifactError, Page, logical_path, opaque_id


class FileUseCases:
    def __init__(self, store: FileStore, authorization: ArtifactAuthorization, cursors: CursorCodec):
        self._store, self._authorization, self._cursors = store, authorization, cursors

    async def read(self, request: ReadFile):
        opaque_id(request.artifact_id)
        if request.revision_id is not None:
            opaque_id(request.revision_id)
        await self._authorization.authorize(request.principal, request.scope, request.workspace_id, Action.READ)
        return await self._store.read(request)

    async def page(self, request: ListFiles):
        if request.directory:
            logical_path(request.directory)
        if not 1 <= request.limit <= 200:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Artifact page limit must be between 1 and 200')
        workspace = await self._authorization.authorize(request.principal, request.scope, request.workspace_id, Action.READ)
        fingerprint = self._cursors.fingerprint({'project': request.scope.project_id,
            'environment': request.scope.environment.value, 'workspace': workspace.id,
            'principal': principal_identity(request.principal), 'directory': request.directory, 'purpose': 'artifacts'})
        cursor = self._cursors.decode(request.cursor, fingerprint=fingerprint, purpose='artifacts') if request.cursor else None
        version = cursor.catalog_version if cursor else workspace.catalog_version
        rows = await self._store.page(request.scope, workspace.id, directory=request.directory,
            catalog_version=version, after=cursor.last_id if cursor else None, limit=request.limit + 1)
        items, more = rows[:request.limit], len(rows) > request.limit
        next_cursor = self._cursors.encode(CursorEnvelope(scope_fingerprint=fingerprint,
            last_id=items[-1].id, catalog_version=version, purpose='artifacts')) if more else None
        return Page(items, more, next_cursor)

    async def mutate(self, request: MutateFile):
        opaque_id(request.operation_id)
        if request.kind not in {'mkdir', 'move', 'delete'}:
            raise ValueError('Unsupported file mutation')
        action = Action.DELETE if request.kind == 'delete' else Action.WRITE
        await self._authorization.authorize(request.principal, request.scope, request.workspace_id, action)
        if request.kind == 'mkdir':
            if request.artifact_id is not None or request.expected_version is not None or request.path is None:
                raise ValueError('Directory creation requires a path and no existing artifact')
        else:
            opaque_id(request.artifact_id)
            if type(request.expected_version) is not int or request.expected_version < 1:
                raise ValueError('Mutation requires expected artifact version')
        if request.path is not None:
            logical_path(request.path)
        if request.kind == 'move' and request.path is None:
            raise ValueError('Move requires a destination path')
        if request.kind == 'delete' and request.path is not None:
            raise ValueError('Deletion identifies an artifact, not a destination path')
        return await self._store.mutate(request, principal_identity(request.principal))
