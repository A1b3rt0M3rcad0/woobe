from modules.artifacts.application.authorization import ArtifactAuthorization, principal_identity
from modules.artifacts.application.contracts.api import CursorEnvelope
from modules.artifacts.application.contracts.files import ListFiles, ListRevisions, MutateFile, ReadFile
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
        if request.run_id is not None:
            opaque_id(request.run_id)
            for node_id in request.output_node_ids:
                opaque_id(node_id)
            if request.revision_id is None:
                raise ArtifactError('SOURCE_UNAVAILABLE', 'Run output reads require an exact revision')
        if request.catalog_version is not None and (
            type(request.catalog_version) is not int or request.catalog_version < 0
        ):
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Invalid pinned catalog snapshot')
        if request.run_id is not None and request.catalog_version is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Run output reads require an accepted catalog snapshot')
        await self._authorization.authorize(request.principal, request.scope, request.workspace_id, Action.READ)
        snapshot = await self._store.read(request)
        if request.run_id is not None:
            revision = snapshot.revision
            if (revision is None or revision.run_id != request.run_id
                or (revision.node_id is not None and revision.node_id not in request.output_node_ids)):
                raise ArtifactError('SOURCE_UNAVAILABLE', 'The exact revision is not an authorized output of this Run')
        return snapshot

    async def page(self, request: ListFiles):
        if request.directory:
            logical_path(request.directory)
        if not 1 <= request.limit <= 200:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Artifact page limit must be between 1 and 200')
        workspace = await self._authorization.authorize(request.principal, request.scope, request.workspace_id, Action.READ)
        pinned_catalog_version = request.catalog_version
        catalog_version = pinned_catalog_version if pinned_catalog_version is not None else workspace.catalog_version
        if not 0 <= catalog_version <= workspace.catalog_version:
            raise ArtifactError('ARTIFACT_INVALID_CURSOR', 'Pinned artifact catalog snapshot is unavailable')
        fingerprint_context = {'project': request.scope.project_id,
            'environment': request.scope.environment.value, 'workspace': workspace.id,
            'principal': principal_identity(request.principal), 'directory': request.directory,
            'purpose': 'artifacts'}
        if pinned_catalog_version is not None:
            fingerprint_context['catalog_version'] = pinned_catalog_version
        fingerprint = self._cursors.fingerprint(fingerprint_context)
        cursor = self._cursors.decode(request.cursor, fingerprint=fingerprint, purpose='artifacts') if request.cursor else None
        version = cursor.catalog_version if cursor else catalog_version
        if pinned_catalog_version is not None and version != pinned_catalog_version:
            raise ArtifactError('ARTIFACT_INVALID_CURSOR', 'Cursor does not match the pinned catalog snapshot')
        rows = await self._store.page(request.scope, workspace.id, directory=request.directory,
            catalog_version=version, after=cursor.last_id if cursor else None, limit=request.limit + 1)
        items, more = rows[:request.limit], len(rows) > request.limit
        next_cursor = self._cursors.encode(CursorEnvelope(scope_fingerprint=fingerprint,
            last_id=items[-1].id, catalog_version=version, purpose='artifacts')) if more else None
        return Page(items, more, next_cursor)

    async def revision_page(self, request: ListRevisions):
        opaque_id(request.artifact_id)
        if not 1 <= request.limit <= 200:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Revision page limit must be between 1 and 200')
        workspace = await self._authorization.authorize(
            request.principal, request.scope, request.workspace_id, Action.READ,
        )
        fingerprint = self._cursors.fingerprint({
            'project': request.scope.project_id,
            'environment': request.scope.environment.value,
            'workspace': workspace.id,
            'artifact': request.artifact_id,
            'principal': principal_identity(request.principal),
            'purpose': 'revisions',
        })
        cursor = self._cursors.decode(request.cursor, fingerprint=fingerprint, purpose='revisions') if request.cursor else None
        rows = await self._store.revisions(
            request, after=cursor.last_id if cursor else None, limit=request.limit + 1,
        )
        items, more = rows[:request.limit], len(rows) > request.limit
        next_cursor = self._cursors.encode(CursorEnvelope(
            scope_fingerprint=fingerprint, last_id=items[-1].revision.id,
            catalog_version=0, purpose='revisions',
        )) if more else None
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
