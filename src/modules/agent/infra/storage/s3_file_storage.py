from __future__ import annotations

import asyncio
from uuid import UUID

from modules.agent.application.interfaces.file_storage import (
    StoredFile,
    build_document_storage_key,
    compute_sha256,
    sanitize_file_name,
)


class S3FileStorage:
    def __init__(
        self,
        *,
        bucket: str,
        region: str | None = None,
        prefix: str | None = None,
        endpoint_url: str | None = None,
        force_path_style: bool = False,
        server_side_encryption: str | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("WOOBE_S3_BUCKET is required when WOOBE_STORAGE_DRIVER=s3")

        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("boto3 is required when WOOBE_STORAGE_DRIVER=s3") from exc

        config = Config(
            s3={"addressing_style": "path" if force_path_style else "auto"}
        )
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url or None,
            config=config,
        )
        self._bucket = bucket
        self._prefix = prefix
        self._server_side_encryption = server_side_encryption or None

    async def save_document(
        self,
        *,
        content: bytes,
        project_id: UUID,
        collection_id: UUID,
        document_id: UUID,
        file_name: str,
        content_type: str,
    ) -> StoredFile:
        safe_file_name = sanitize_file_name(file_name)
        storage_key = build_document_storage_key(
            project_id=project_id,
            collection_id=collection_id,
            document_id=document_id,
            file_name=safe_file_name,
            prefix=self._prefix,
        )
        sha256 = compute_sha256(content)

        put_kwargs = {
            "Bucket": self._bucket,
            "Key": storage_key,
            "Body": content,
            "ContentType": content_type,
            "Metadata": {
                "project_id": str(project_id),
                "collection_id": str(collection_id),
                "document_id": str(document_id),
                "sha256": sha256,
                "original_file_name": safe_file_name,
            },
        }
        if self._server_side_encryption:
            put_kwargs["ServerSideEncryption"] = self._server_side_encryption

        await asyncio.to_thread(self._client.put_object, **put_kwargs)
        return StoredFile(
            storage_key=storage_key,
            file_name=safe_file_name,
            content_type=content_type,
            size_bytes=len(content),
            sha256=sha256,
        )

    async def read_document(self, storage_key: str) -> bytes:
        response = await asyncio.to_thread(
            self._client.get_object,
            Bucket=self._bucket,
            Key=storage_key,
        )
        body = response["Body"]
        return await asyncio.to_thread(body.read)

    async def delete(self, storage_key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self._bucket,
            Key=storage_key,
        )
