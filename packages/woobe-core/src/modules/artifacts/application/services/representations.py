import hashlib

from modules.artifacts.application.contracts.api import SourceReference
from modules.artifacts.application.contracts.representations import SourceReadView
from modules.artifacts.domain.models import ArtifactError


class RepresentationService:
    def __init__(self, read, entries, source, storage, uploads=None):
        self.resolve, self.list_entries, self._source, self._storage = read, entries, source, storage
        self._uploads = uploads

    async def read_source(self, request):
        proof = await self._source(request)
        storage = self._storage(proof['storage_profile'])
        metadata = await storage.stat(proof['key'])
        if (metadata.version_id, metadata.size_bytes, metadata.sha256) != (
                proof['version_id'], proof['size_bytes'], proof['sha256']):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Source text object changed')
        parts = []
        for segment in proof['segments']:
            stream = storage.open(proof['key'], start=segment['byte_start'], end=segment['byte_end'])
            content = bytearray()
            try:
                async for chunk in stream:
                    if len(content) + len(chunk) > segment['byte_end'] - segment['byte_start']:
                        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Source segment exceeds its byte interval')
                    content.extend(chunk)
            finally:
                await stream.aclose()
            if (len(content) != segment['byte_end'] - segment['byte_start']
                or hashlib.sha256(content).hexdigest() != segment['sha256']):
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Source segment checksum differs')
            try:
                text = content.decode('utf-8')
            except UnicodeDecodeError as error:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Source segment encoding differs') from error
            if len(text) != segment['char_end'] - segment['char_start']:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Source segment character interval differs')
            parts.append(text[max(0, proof['low'] - segment['char_start']):min(len(text), proof['high'] - segment['char_start'])])
        text = ''.join(parts)
        if len(text) != proof['high'] - proof['low']:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Source text interval is incomplete')
        if (proof['low'] == 0 and proof['high'] == proof['block_char_length']
            and hashlib.sha256(text.encode()).hexdigest() != proof['block_sha256']):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Source block checksum differs')
        checksum = request.definition.source.excerpt_sha256
        if checksum is not None and not (checksum == proof['block_sha256']
            and proof['start'] == 0 and proof['end'] == proof['block_char_length']):
            if proof['low'] != proof['start'] or proof['high'] != proof['end'] or hashlib.sha256(text.encode()).hexdigest() != checksum:
                raise ArtifactError('SOURCE_UNAVAILABLE', 'Excerpt checksum does not identify this exact interval')
        source = proof['source']
        source['locator'].update(char_space='canonical_block_text', char_start=proof['start'], char_end=proof['end'])
        # Source coordinates now describe the canonical block, preserving
        # physical page and original byte/line provenance separately.
        return SourceReadView(source=SourceReference.model_validate(source), text=text,
            offset=request.definition.offset,
            next_offset=proof['high'] - proof['start'] if proof['high'] < proof['end'] else None,
            truncated=proof['high'] < proof['end'], coverage=proof['coverage'])

    async def open_content(self, request, *, start=0, end=None):
        snapshot = await self.resolve(request)
        entry = snapshot.entry
        if entry is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'A representation entry is required')
        stop = entry.size_bytes if end is None else end
        if not 0 <= start <= stop <= entry.size_bytes:
            raise ArtifactError('ARTIFACT_INVALID_RANGE', 'Invalid representation byte interval')
        storage = self._storage(snapshot.storage_profile)
        metadata = await storage.stat(entry.object_key)
        if (metadata.sha256, metadata.size_bytes, metadata.version_id) != (entry.sha256, entry.size_bytes, entry.storage_version_id):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation download object receipt differs')
        return snapshot, storage.open(entry.object_key, start=start, end=stop)

    async def copy(self, request):
        from modules.artifacts.application.contracts.api import UploadCreate
        from modules.artifacts.application.contracts.uploads import BeginUpload, UploadPart, UploadRequest
        snapshot = await self.resolve(request)
        entry = snapshot.entry
        if entry is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Copy requires an exact representation entry')
        definition = UploadCreate(operation_id=request.operation_id, path=request.path,
            size_bytes=entry.size_bytes, sha256=entry.sha256, content_type=entry.content_type)
        view = await self._uploads.begin(BeginUpload(request.principal, request.scope, request.workspace_id,
            definition, origin='copy', source_representation_set_id=snapshot.generation.id,
            source_representation_entry_id=entry.id))
        upload = UploadRequest(request.principal, request.scope, request.workspace_id, view.id)
        if view.receipt is not None:
            return view
        _, stream = await self.open_content(request, start=view.offset)
        offset, buffer = view.offset, bytearray()
        try:
            async for chunk in stream:
                buffer.extend(chunk)
                while len(buffer) >= 1_048_576:
                    part = bytes(buffer[:1_048_576])
                    del buffer[:1_048_576]
                    await self.resolve(request)
                    await self._uploads.append(UploadPart(request.principal, request.scope, request.workspace_id,
                        view.id, offset, part))
                    offset += len(part)
            if buffer:
                await self.resolve(request)
                await self._uploads.append(UploadPart(request.principal, request.scope, request.workspace_id,
                    view.id, offset, bytes(buffer)))
        finally:
            await stream.aclose()
        await self.resolve(request)
        return await self._uploads.finalize(upload)
