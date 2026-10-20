from modules.artifacts.application.authorization import ArtifactAuthorization, principal_identity
from modules.artifacts.application.contracts.uploads import (
    BeginUpload, CommitUpload, RecordPart, UploadRequest,
)
from modules.artifacts.application.ports.uploads import UploadStore
from modules.artifacts.domain.models import Action, ArtifactError


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
        return await self._store.commit(request, await self._authorize(request))

    async def abort(self, request: UploadRequest):
        return await self._store.abort(request, await self._authorize(request))
