from dataclasses import replace
import hashlib

from modules.artifacts.application.contracts.api import UploadCreate
from modules.artifacts.application.contracts.uploads import BeginUpload, UploadPart, UploadRequest
from modules.artifacts.domain.models import ArtifactError
from shared.contracts.object_storage import ObjectStorageError, read_bounded


MAX_TEXT_BYTES = 256 * 1024


class FileService:
    def __init__(self, read, page, mutate, uploads, storage):
        self.resolve, self.list, self.mutate = read, page, mutate
        self._uploads, self._storage = uploads, storage

    async def write_text(self, request):
        if not isinstance(request.text, str) or len(request.text) > MAX_TEXT_BYTES:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Text write exceeds the configured inline limit')
        content = request.text.encode('utf-8')
        if len(content) > MAX_TEXT_BYTES:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Text write exceeds the configured inline byte limit')
        definition = UploadCreate(operation_id=request.operation_id, path=request.path,
            size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(), content_type='text/plain; charset=utf-8',
            artifact_id=request.artifact_id, expected_revision=request.expected_revision)
        view = await self._uploads.begin(BeginUpload(request.principal, request.scope, request.workspace_id,
            definition, request.origin, request.run_id, request.node_id))
        upload = UploadRequest(request.principal, request.scope, request.workspace_id, view.id)
        if content and view.receipt is None:
            await self._uploads.append(UploadPart(request.principal, request.scope, request.workspace_id,
                                                  view.id, 0, content))
        return await self._uploads.finalize(upload)

    async def read_bytes(self, request, *, max_bytes=MAX_TEXT_BYTES):
        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_TEXT_BYTES:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Inline read limit must be between 1 and 262144 bytes')
        snapshot = await self.resolve(request)
        revision = snapshot.revision
        if revision is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Directory content is unavailable')
        if revision.size_bytes > max_bytes:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'File exceeds the inline read limit')
        try:
            content = await read_bounded(self._storage(snapshot.storage_profile), revision.object_key, max_bytes=max_bytes)
        except ObjectStorageError as error:
            raise ArtifactError('ARTIFACT_STORAGE_UNAVAILABLE', 'Artifact content is unavailable', retryable=True) from error
        if len(content) != revision.size_bytes or hashlib.sha256(content).hexdigest() != revision.sha256:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Artifact content failed integrity verification')
        return content

    async def read_text(self, request, *, max_bytes=MAX_TEXT_BYTES):
        content = await self.read_bytes(request, max_bytes=max_bytes)
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError as error:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Artifact is not UTF-8 text') from error

    async def copy(self, request):
        # Inline editable copies have the same explicit bound as inline reads.
        # Larger copies use the resumable upload contract rather than buffering.
        snapshot = await self.resolve(request)
        if snapshot.revision is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Directory content is unavailable')
        content = await self.read_bytes(replace(request, revision_id=snapshot.revision.id))
        definition = UploadCreate(operation_id=request.operation_id, path=request.destination_path,
            size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(),
            content_type=snapshot.revision.content_type)
        view = await self._uploads.begin(BeginUpload(request.principal, request.scope,
            request.workspace_id, definition, origin='copy'))
        upload = UploadRequest(request.principal, request.scope, request.workspace_id, view.id)
        if content and view.receipt is None:
            await self._uploads.append(UploadPart(request.principal, request.scope, request.workspace_id,
                view.id, 0, content))
        return await self._uploads.finalize(upload)

    async def open_content(self, request, *, start=0, end=None):
        snapshot = await self.resolve(request)
        if snapshot.revision is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Directory content is unavailable')
        stop = snapshot.revision.size_bytes if end is None else end
        if not 0 <= start <= stop <= snapshot.revision.size_bytes:
            raise ArtifactError('ARTIFACT_INVALID_RANGE', 'Invalid artifact byte range')
        return snapshot, self._storage(snapshot.storage_profile).open(
            snapshot.revision.object_key, start=start, end=stop)
