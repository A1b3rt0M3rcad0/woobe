import hashlib

from modules.artifacts.application.contracts.uploads import CommitUpload, RecordPart, UploadPart
from modules.artifacts.domain.models import ArtifactError, UploadStatus
from shared.contracts.object_storage import ObjectStorageError


MAX_PART_BYTES = 8 * 1024 * 1024


def validate_media(prefix: bytes, declared: str):
    """Conservative signature validation; no parser/processor readiness claims."""
    media = declared.split(';', 1)[0].strip().lower()
    detected = None
    for magic, kind in ((b'%PDF-', 'application/pdf'), (b'\x89PNG\r\n\x1a\n', 'image/png'),
                        (b'\xff\xd8\xff', 'image/jpeg'), (b'GIF87a', 'image/gif'),
                        (b'GIF89a', 'image/gif'), (b'PK\x03\x04', 'application/zip')):
        if prefix.startswith(magic):
            detected = kind
            break
    office = media in {'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                       'application/vnd.openxmlformats-officedocument.presentationml.presentation'}
    if detected is not None:
        valid = media in {detected, 'application/octet-stream'} or (detected == 'application/zip' and office)
    elif media.startswith('text/') or media == 'application/json':
        try:
            # A prefix may end mid-codepoint. The incremental decoder accepts
            # that boundary, but rejects invalid bytes and embedded NUL content.
            import codecs
            codecs.getincrementaldecoder('utf-8')().decode(prefix, final=False)
            valid = b'\x00' not in prefix
        except UnicodeDecodeError:
            valid = False
    else:
        valid = media == 'application/octet-stream' or not prefix
    if not valid:
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Declared media type does not match the uploaded bytes')


class UploadService:
    """Handlers commit before/after storage I/O; each operation reauthorizes."""

    def __init__(self, begin, status, admit, record, verify, commit, abort, storage):
        self._begin, self._status, self._admit, self._record = begin, status, admit, record
        self._verify, self._commit, self._abort = verify, commit, abort
        self._storage = storage

    @staticmethod
    def _live(snapshot):
        if snapshot.view.status in {UploadStatus.EXPIRED, UploadStatus.ABORTED, UploadStatus.FAILED}:
            raise ArtifactError('UPLOAD_EXPIRED', 'Upload is no longer active')

    async def begin(self, request):
        return (await self._begin(request)).view

    async def status(self, request):
        return (await self._status(request)).view

    async def admit(self, request):
        snapshot = await self._admit(request)
        self._live(snapshot)
        return snapshot.view

    async def abort(self, request):
        return (await self._abort(request)).view

    async def append(self, request: UploadPart):
        if (type(request.offset) is not int or request.offset < 0
                or not isinstance(request.content, bytes) or not 1 <= len(request.content) <= MAX_PART_BYTES):
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Upload part must contain 1–8388608 bytes at a nonnegative offset')
        snapshot = await self._admit(request)
        self._live(snapshot)
        digest = hashlib.sha256(request.content).hexdigest()
        if request.offset != snapshot.view.offset:
            if any(part['offset'] == request.offset and part['size'] == len(request.content)
                   and part['sha256'] == digest for part in snapshot.parts):
                return snapshot.view
            raise ArtifactError('UPLOAD_OFFSET_CONFLICT', 'Upload offset changed')
        if snapshot.view.status == UploadStatus.COMMITTED:
            raise ArtifactError('UPLOAD_OFFSET_CONFLICT', 'Upload is already committed')
        if len(snapshot.parts) >= 4096:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Upload part count limit exceeded')
        if request.offset + len(request.content) > snapshot.view.expected_size:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Part exceeds the expected upload size')
        prefix = snapshot.object_key.rsplit('/artifacts/', 1)[0]
        key = f'{prefix}/uploads/{snapshot.view.id}/parts/{request.offset}-{digest}'

        async def chunks():
            yield request.content

        try:
            await self._storage(snapshot.storage_profile).put(key, chunks(),
                size_bytes=len(request.content), sha256=digest, content_type='application/octet-stream')
        except ObjectStorageError as error:
            raise ArtifactError('ARTIFACT_STORAGE_UNAVAILABLE', 'Upload part could not be stored', retryable=True) from error
        recorded = await self._record(RecordPart(request.principal, request.scope, request.workspace_id,
            request.upload_id, request.offset, key, len(request.content), digest))
        self._live(recorded)
        return recorded.view

    async def finalize(self, request):
        snapshot = await self._verify(request)
        self._live(snapshot)
        if snapshot.view.receipt is not None:
            return snapshot.view
        store = self._storage(snapshot.storage_profile)

        async def assembled():
            prefix = bytearray()
            for part in snapshot.parts:
                digest, size = hashlib.sha256(), 0
                stream = store.open(part['key'])
                try:
                    async for chunk in stream:
                        if len(prefix) < 8192:
                            prefix.extend(chunk[:8192 - len(prefix)])
                        digest.update(chunk)
                        size += len(chunk)
                        yield chunk
                finally:
                    await stream.aclose()
                if size != part['size'] or digest.hexdigest() != part['sha256']:
                    raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Stored upload part failed integrity verification')
            validate_media(bytes(prefix), snapshot.content_type)

        try:
            metadata = await store.put(snapshot.object_key, assembled(),
                size_bytes=snapshot.view.expected_size, sha256=snapshot.sha256,
                content_type=snapshot.content_type)
        except ObjectStorageError as error:
            code = 'UPLOAD_INTEGRITY_MISMATCH' if error.code == 'integrity' else 'ARTIFACT_STORAGE_UNAVAILABLE'
            raise ArtifactError(code, 'Upload could not be verified or published', retryable=code != 'UPLOAD_INTEGRITY_MISMATCH') from error
        committed = await self._commit(CommitUpload(request.principal, request.scope, request.workspace_id,
            request.upload_id, metadata.size_bytes, metadata.sha256, metadata.content_type, metadata.version_id))
        self._live(committed)
        return committed.view
