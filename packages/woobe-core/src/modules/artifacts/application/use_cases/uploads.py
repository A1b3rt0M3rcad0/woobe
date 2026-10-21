from modules.artifacts.application.authorization import ArtifactAuthorization, principal_identity
from modules.artifacts.application.contracts.uploads import (
    BeginUpload, CommitUpload, RecordPart, UploadRequest,
)
from modules.artifacts.application.ports.uploads import UploadStore
from modules.artifacts.domain.models import Action, ArtifactError, ArtifactRef, opaque_id


class UploadUseCases:
    """Database phases only; transfer orchestration runs between transactions."""

    def __init__(self, store: UploadStore, authorization: ArtifactAuthorization,
                 *, max_upload_bytes: int):
        self._store = store
        self._authorization = authorization
        self._maximum = max_upload_bytes

    async def _authorize(self, request, action=Action.WRITE):
        await self._authorization.authorize(request.principal, request.scope,
                                             request.workspace_id, action)
        return principal_identity(request.principal)

    async def begin(self, request: BeginUpload):
        subject = await self._authorize(request)
        if request.origin not in {'upload', 'application', 'agent', 'tool', 'processing', 'copy'}:
            raise ValueError('Invalid publication origin')
        for value in (request.run_id, request.node_id):
            if value is not None:
                opaque_id(value)
        if request.producer_id is not None:
            opaque_id(request.producer_id)
        if request.origin == 'tool' and (request.producer_id is None or request.run_id is None):
            raise ValueError('Tool output provenance requires a producer and Run identity')
        if request.external_operation_ref is not None and (
            not request.external_operation_ref or len(request.external_operation_ref) > 512
            or any(ord(char) < 32 or ord(char) == 127 for char in request.external_operation_ref)
        ):
            raise ValueError('Invalid external operation reference')
        if len(request.source_refs) > 32:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'External Tool output has too many source references')
        for source in request.source_refs:
            if not isinstance(source, dict):
                raise ValueError('Artifact source lineage must contain reference objects')
            ArtifactRef(source.get('artifact_id'), source.get('revision_id'))
        if request.node_id is not None and request.run_id is None:
            raise ValueError('Node provenance requires a Run identity')
        if (request.source_representation_set_id is None) != (request.source_representation_entry_id is None):
            raise ValueError('Representation copy requires its exact generation and entry')
        if request.source_representation_set_id is not None:
            if request.origin != 'copy' or request.definition.artifact_id is not None:
                raise ValueError('Representation copies must create a new Artifact')
            await self._authorize(request, Action.READ)
        if request.definition.size_bytes > self._maximum:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Upload exceeds the configured byte limit')
        return await self._store.begin(request, subject)

    async def status(self, request: UploadRequest):
        return await self._store.load(request, await self._authorize(request, Action.READ))

    async def admit(self, request: UploadRequest):
        return await self._store.load(request, await self._authorize(request))

    async def record(self, request: RecordPart):
        return await self._store.record_part(request, await self._authorize(request))

    async def verify(self, request: UploadRequest):
        return await self._store.verify(request, await self._authorize(request))

    async def commit(self, request: CommitUpload):
        subject = await self._authorize(request)
        snapshot = await self._store.load(request, subject)
        if snapshot.source_representation_set_id is not None:
            await self._authorize(request, Action.READ)
        return await self._store.commit(request, subject)

    async def abort(self, request: UploadRequest):
        return await self._store.abort(request, await self._authorize(request))
