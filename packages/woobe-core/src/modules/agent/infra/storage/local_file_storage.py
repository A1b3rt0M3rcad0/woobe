from __future__ import annotations

from pathlib import Path
from uuid import UUID

from modules.agent.application.interfaces.file_storage import (
    StoredFile, build_document_storage_key, compute_sha256, sanitize_file_name,
)
from shared.contracts.object_storage import ObjectStorageError, read_bounded
from shared.infra.object_storage.local import LocalObjectStorage


def _legacy_error(error: ObjectStorageError):
    if error.code in {'invalid_key', 'invalid_object', 'range', 'integrity'}:
        return ValueError(str(error))
    if isinstance(error.__cause__, OSError):
        return error.__cause__
    if error.code == 'not_found':
        return FileNotFoundError('Document is unavailable')
    return OSError(str(error))


class LocalFileStorage:
    """Knowledge compatibility facade; original physical keys stay unchanged."""

    def __init__(self, base_dir: str | Path):
        self._base_dir = Path(base_dir).expanduser()
        self._objects = LocalObjectStorage(self._base_dir, legacy_keys=True)

    async def save_document(self, *, content: bytes, project_id: UUID,
                            collection_id: UUID, document_id: UUID,
                            file_name: str, content_type: str) -> StoredFile:
        safe_name = sanitize_file_name(file_name)
        key = build_document_storage_key(project_id=project_id, collection_id=collection_id,
                                          document_id=document_id, file_name=safe_name)
        digest = compute_sha256(content)

        async def chunks():
            for offset in range(0, len(content), 65_536):
                yield content[offset:offset + 65_536]

        try:
            await self._objects.put(key, chunks(), size_bytes=len(content), sha256=digest,
                                    content_type=content_type, replace=True)
        except ObjectStorageError as error:
            raise _legacy_error(error) from error
        return StoredFile(key, safe_name, content_type, len(content), digest)

    async def read_document(self, storage_key: str) -> bytes:
        try:
            return b''.join([chunk async for chunk in self._objects.open(storage_key)])
        except ObjectStorageError as error:
            raise _legacy_error(error) from error

    async def read_document_bounded(self, storage_key: str, *, max_bytes: int) -> bytes:
        try:
            return await read_bounded(self._objects, storage_key, max_bytes=max_bytes)
        except ObjectStorageError as error:
            raise _legacy_error(error) from error

    async def delete(self, storage_key: str):
        try:
            await self._objects.delete(storage_key)
        except ObjectStorageError as error:
            if error.code == 'invalid_key' or isinstance(error.__cause__, IsADirectoryError):
                return
            raise _legacy_error(error) from error
