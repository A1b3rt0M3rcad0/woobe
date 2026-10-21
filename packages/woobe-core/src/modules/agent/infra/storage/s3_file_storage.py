from __future__ import annotations

from uuid import UUID

from modules.agent.application.interfaces.file_storage import (
    StoredFile, build_document_storage_key, compute_sha256, sanitize_file_name,
)
from modules.agent.infra.storage.errors import legacy_document_error
from shared.contracts.object_storage import ObjectStorageError, read_bounded
from shared.infra.object_storage.s3 import S3ObjectStorage
from shared.infra.object_storage.s3_factory import create_s3_object_storage


class S3FileStorage:
    """Knowledge facade preserving keys and metadata over shared S3 streaming."""

    def __init__(self, *, bucket: str, region: str | None = None,
                 prefix: str | None = None, endpoint_url: str | None = None,
                 force_path_style: bool = False, server_side_encryption: str | None = None):
        if not bucket:
            raise ValueError('WOOBE_S3_BUCKET is required when WOOBE_STORAGE_DRIVER=s3')
        self._objects = create_s3_object_storage(bucket=bucket, region=region,
            endpoint_url=endpoint_url, force_path_style=force_path_style,
            server_side_encryption=server_side_encryption, legacy_keys=True)
        self._client = self._objects._client
        self._bucket, self._prefix = bucket, prefix
        self._server_side_encryption = server_side_encryption

    def _store(self):
        if getattr(self, '_objects', None) is None:
            self._objects = S3ObjectStorage(self._client, bucket=self._bucket,
                legacy_keys=True, server_side_encryption=getattr(self, '_server_side_encryption', None))
        return self._objects

    async def save_document(self, *, content: bytes, project_id: UUID,
                            collection_id: UUID, document_id: UUID,
                            file_name: str, content_type: str):
        safe_name = sanitize_file_name(file_name)
        key = build_document_storage_key(project_id=project_id, collection_id=collection_id,
            document_id=document_id, file_name=safe_name, prefix=self._prefix)
        digest = compute_sha256(content)

        async def chunks():
            for offset in range(0, len(content), 65_536):
                yield content[offset:offset + 65_536]

        try:
            await self._store().put(key, chunks(), size_bytes=len(content), sha256=digest,
                content_type=content_type, replace=True, attributes={
                    'project_id': str(project_id), 'collection_id': str(collection_id),
                    'document_id': str(document_id), 'original_file_name': safe_name})
        except ObjectStorageError as error:
            raise legacy_document_error(error) from error
        return StoredFile(key, safe_name, content_type, len(content), digest)

    async def read_document(self, storage_key):
        try:
            return b''.join([chunk async for chunk in self._store().open(storage_key)])
        except ObjectStorageError as error:
            raise legacy_document_error(error) from error

    async def read_document_bounded(self, storage_key, *, max_bytes):
        try:
            return await read_bounded(self._store(), storage_key, max_bytes=max_bytes)
        except ObjectStorageError as error:
            raise legacy_document_error(error) from error

    async def delete(self, storage_key):
        try:
            await self._store().delete(storage_key)
        except ObjectStorageError as error:
            raise legacy_document_error(error) from error

    async def close(self):
        await self._store().close()
