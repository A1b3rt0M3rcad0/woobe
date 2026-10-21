from dataclasses import replace
import hashlib
import time

from modules.artifacts.application.contracts.api import UploadCreate
from modules.artifacts.application.contracts.files import WriteBytes
from modules.artifacts.application.contracts.uploads import BeginUpload, UploadPart, UploadRequest
from modules.artifacts.domain.models import ArtifactError
from shared.contracts.object_storage import ObjectStorageError, read_bounded
from shared.observability.metrics import runtime_metrics


MAX_TEXT_BYTES = 256 * 1024
MAX_VISUAL_BYTES = 4 * 1024 * 1024
MAX_EXTERNAL_OUTPUT_BYTES = 8 * 1024 * 1024
UPLOAD_PART_BYTES = 8 * 1024 * 1024


def _record_failure(operation: str, started: float, error: Exception) -> None:
    runtime_metrics.observe_artifact_operation(
        operation=operation,
        outcome="denied" if getattr(error, "code", None) == "ARTIFACT_ACCESS_DENIED" else "error",
        duration_seconds=time.perf_counter() - started,
    )


class FileService:
    def __init__(self, read, page, mutate, uploads, storage):
        self.resolve, self._list_page, self.mutate = read, page, mutate
        self._uploads, self._storage = uploads, storage

    async def list(self, request):
        started = time.perf_counter()
        try:
            result = await self._list_page(request)
        except ArtifactError as error:
            runtime_metrics.observe_artifact_operation(
                operation="list",
                outcome="denied" if error.code == "ARTIFACT_ACCESS_DENIED" else "error",
                duration_seconds=time.perf_counter() - started,
            )
            raise
        runtime_metrics.observe_artifact_operation(
            operation="list", outcome="success", duration_seconds=time.perf_counter() - started,
        )
        return result

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

    async def write_external_output(self, request: WriteBytes):
        if not isinstance(request.content, bytes) or len(request.content) > MAX_EXTERNAL_OUTPUT_BYTES:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'External Tool output exceeds the configured byte limit')
        if not request.producer_id:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'External Tool output has no producer identity')
        digest = hashlib.sha256(request.content).hexdigest()
        definition = UploadCreate(
            operation_id=request.operation_id,
            path=request.path,
            size_bytes=len(request.content),
            sha256=digest,
            content_type=request.content_type,
        )
        begin = BeginUpload(
            request.principal,
            request.scope,
            request.workspace_id,
            definition,
            origin='tool',
            run_id=request.run_id,
            node_id=request.node_id,
            producer_id=request.producer_id,
            external_operation_ref=request.external_operation_ref,
            source_refs=request.source_refs,
        )
        view = await self._uploads.begin(begin)
        upload = UploadRequest(request.principal, request.scope, request.workspace_id, view.id)
        if request.content and view.receipt is None:
            for offset in range(view.offset, len(request.content), UPLOAD_PART_BYTES):
                chunk = request.content[offset:offset + UPLOAD_PART_BYTES]
                await self._uploads.append(UploadPart(
                    request.principal,
                    request.scope,
                    request.workspace_id,
                    view.id,
                    offset,
                    chunk,
                ))
        return await self._uploads.finalize(upload)

    async def read_bytes(self, request, *, max_bytes=MAX_TEXT_BYTES):
        started = time.perf_counter()
        if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_TEXT_BYTES:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Inline read limit must be between 1 and 262144 bytes')
        try:
            snapshot = await self.resolve(request)
            revision = snapshot.revision
            if revision is None:
                raise ArtifactError('SOURCE_UNAVAILABLE', 'Directory content is unavailable')
            if revision.size_bytes > max_bytes:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'File exceeds the inline read limit')
            content = await read_bounded(self._storage(snapshot.storage_profile), revision.object_key, max_bytes=max_bytes)
        except ObjectStorageError as error:
            _record_failure("read", started, error)
            raise ArtifactError('ARTIFACT_STORAGE_UNAVAILABLE', 'Artifact content is unavailable', retryable=True) from error
        except ArtifactError as error:
            runtime_metrics.observe_artifact_operation(
                operation="read",
                outcome="denied" if error.code == "ARTIFACT_ACCESS_DENIED" else "error",
                duration_seconds=time.perf_counter() - started,
            )
            raise
        if len(content) != revision.size_bytes or hashlib.sha256(content).hexdigest() != revision.sha256:
            error = ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Artifact content failed integrity verification')
            _record_failure("read", started, error)
            raise error
        runtime_metrics.observe_artifact_operation(
            operation="read", outcome="success", duration_seconds=time.perf_counter() - started,
            byte_count=len(content), byte_direction="read",
        )
        return content

    async def read_visual_bytes(self, request, *, max_bytes=MAX_VISUAL_BYTES):
        started = time.perf_counter()
        try:
            if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_VISUAL_BYTES:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Visual input limit exceeds the configured bound')
            snapshot = await self.resolve(request)
            revision = snapshot.revision
            if revision is None:
                raise ArtifactError('SOURCE_UNAVAILABLE', 'Artifact content is unavailable')
            content_type = revision.content_type.split(';', 1)[0].strip().lower()
            if content_type not in {'image/png', 'image/jpeg', 'image/webp'}:
                raise ArtifactError('FILE_TRANSFER_UNSUPPORTED', 'Artifact media type is not supported as visual input')
            if revision.size_bytes > max_bytes:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Visual Artifact exceeds the configured byte limit')
            content = await read_bounded(
                self._storage(snapshot.storage_profile), revision.object_key, max_bytes=max_bytes,
            )
        except ObjectStorageError as error:
            _record_failure("read", started, error)
            raise ArtifactError('ARTIFACT_STORAGE_UNAVAILABLE', 'Artifact content is unavailable', retryable=True) from error
        except ArtifactError as error:
            _record_failure("read", started, error)
            raise
        if len(content) != revision.size_bytes or hashlib.sha256(content).hexdigest() != revision.sha256:
            error = ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Artifact content failed integrity verification')
            _record_failure("read", started, error)
            raise error
        runtime_metrics.observe_artifact_operation(
            operation="read", outcome="success", duration_seconds=time.perf_counter() - started,
            byte_count=len(content), byte_direction="read",
        )
        return snapshot, content

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
        started = time.perf_counter()
        try:
            snapshot = await self.resolve(request)
            if snapshot.revision is None:
                raise ArtifactError('SOURCE_UNAVAILABLE', 'Directory content is unavailable')
            stop = snapshot.revision.size_bytes if end is None else end
            if not 0 <= start <= stop <= snapshot.revision.size_bytes:
                raise ArtifactError('ARTIFACT_INVALID_RANGE', 'Invalid artifact byte range')
            stream = self._storage(snapshot.storage_profile).open(
                snapshot.revision.object_key, start=start, end=stop)
        except ArtifactError as error:
            _record_failure("download", started, error)
            raise
        except ObjectStorageError as error:
            _record_failure("download", started, error)
            raise ArtifactError('ARTIFACT_STORAGE_UNAVAILABLE', 'Artifact content is unavailable', retryable=True) from error

        async def observed_stream():
            transferred = 0
            outcome = "success"
            try:
                async for chunk in stream:
                    transferred += len(chunk)
                    yield chunk
            except Exception:
                outcome = "error"
                raise
            finally:
                if transferred != stop - start:
                    outcome = "error"
                runtime_metrics.observe_artifact_operation(
                    operation="download", outcome=outcome,
                    duration_seconds=time.perf_counter() - started,
                    byte_count=transferred, byte_direction="transfer",
                )

        return snapshot, observed_stream()

    async def create_temporary_url(self, request, *, expires_seconds=60):
        if type(expires_seconds) is not int or not 1 <= expires_seconds <= 60:
            raise ArtifactError('ARTIFACT_INVALID_RANGE', 'Artifact download URL expiry exceeds 60 seconds')
        snapshot = await self.resolve(request)
        if snapshot.revision is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Directory content is unavailable')
        signer = getattr(self._storage(snapshot.storage_profile), 'presign_get', None)
        if not callable(signer):
            raise ArtifactError('ARTIFACT_STORAGE_UNAVAILABLE', 'Storage profile does not support temporary download URLs')
        try:
            url = await signer(snapshot.revision.object_key, expires_seconds=expires_seconds)
        except Exception as error:
            raise ArtifactError('ARTIFACT_STORAGE_UNAVAILABLE', 'Temporary Artifact URL is unavailable', retryable=True) from error
        return snapshot, url
