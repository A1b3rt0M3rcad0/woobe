from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

from modules.agent.application.interfaces.file_storage import (
    StoredFile,
    build_document_storage_key,
    compute_sha256,
    sanitize_file_name,
)


class LocalFileStorage:
    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir).expanduser()

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
        )
        sha256 = compute_sha256(content)

        base_dir = self._base_dir.resolve()
        target_path = (base_dir / storage_key).resolve()
        if not target_path.is_relative_to(base_dir):
            raise ValueError("Resolved upload path escapes configured local storage root")

        def write_file() -> None:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(content)

        await asyncio.to_thread(write_file)
        return StoredFile(
            storage_key=storage_key,
            file_name=safe_file_name,
            content_type=content_type,
            size_bytes=len(content),
            sha256=sha256,
        )

    async def read_document(self, storage_key: str) -> bytes:
        base_dir = self._base_dir.resolve()
        target_path = (base_dir / storage_key).resolve()
        if not target_path.is_relative_to(base_dir):
            raise ValueError("Resolved read path escapes configured local storage root")
        return await asyncio.to_thread(target_path.read_bytes)

    async def delete(self, storage_key: str) -> None:
        base_dir = self._base_dir.resolve()
        target_path = (base_dir / storage_key).resolve()
        if not target_path.is_relative_to(base_dir):
            return

        def delete_file() -> None:
            try:
                target_path.unlink(missing_ok=True)
            except IsADirectoryError:
                return

        await asyncio.to_thread(delete_file)
