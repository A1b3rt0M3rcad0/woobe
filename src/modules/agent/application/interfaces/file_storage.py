from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol
from uuid import UUID

_SAFE_FILE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class StoredFile:
    storage_key: str
    file_name: str
    content_type: str
    size_bytes: int
    sha256: str


class FileStorage(Protocol):
    async def save_document(
        self,
        *,
        content: bytes,
        project_id: UUID,
        collection_id: UUID,
        document_id: UUID,
        file_name: str,
        content_type: str,
    ) -> StoredFile: ...

    async def read_document(self, storage_key: str) -> bytes: ...

    async def delete(self, storage_key: str) -> None: ...


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sanitize_file_name(file_name: str) -> str:
    candidate = PurePosixPath(file_name.replace("\\", "/")).name.strip()
    candidate = _SAFE_FILE_NAME_RE.sub("-", candidate)
    candidate = candidate.strip(".-_")
    return candidate or "document"


def build_document_storage_key(
    *,
    project_id: UUID,
    collection_id: UUID,
    document_id: UUID,
    file_name: str,
    prefix: str | None = None,
) -> str:
    safe_file_name = sanitize_file_name(file_name)
    key = (
        f"projects/{project_id}/collections/{collection_id}/"
        f"documents/{document_id}/{safe_file_name}"
    )
    normalized_prefix = (prefix or "").strip().strip("/")
    if normalized_prefix:
        return f"{normalized_prefix}/{key}"
    return key
