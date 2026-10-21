"""Version 1 streaming object storage, shared without Knowledge identities.

Read ranges are half-open [start, end). Immutable writes are the default;
replacement is explicit and reserved for compatibility facades. ETag is never
a substitute for SHA-256. Adapters must close resources on early consumption.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
import re
from typing import Protocol


CHUNK_BYTES = 65_536


class ObjectStorageError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ObjectMetadata:
    key: str
    size_bytes: int
    sha256: str
    content_type: str
    version_id: str | None = None


def validate_object_key(key: str, *, legacy: bool = False) -> str:
    if (not isinstance(key, str) or len(key) > 1024
            or re.fullmatch(r'[A-Za-z0-9_.\-/]+', key) is None
            or any(part in {'', '.', '..'} for part in key.split('/'))):
        raise ObjectStorageError('invalid_key', 'Invalid object storage key')
    if key.split('/')[0] == '.woobe-object-metadata':
        raise ObjectStorageError('invalid_key', 'Reserved object storage key')
    for part in key.split('/'):
        if part.startswith('.woobe-staging-'):
            raise ObjectStorageError('invalid_key', 'Unpublished staging is not addressable')
        if not legacy and (part.endswith('.') or re.fullmatch(
            r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I
        )):
            raise ObjectStorageError('invalid_key', 'Nonportable object storage key')
    return key


class ObjectStorage(Protocol):
    contract_version: str

    async def put(self, key: str, chunks: AsyncIterator[bytes], *, size_bytes: int,
                  sha256: str, content_type: str, replace: bool = False) -> ObjectMetadata: ...

    def open(self, key: str, *, start: int = 0, end: int | None = None) -> AsyncGenerator[bytes, None]: ...

    async def head(self, key: str) -> ObjectMetadata:
        """Declared immutable-write metadata, without reading/verifying payload."""
        ...

    async def stat(self, key: str) -> ObjectMetadata: ...

    async def delete(self, key: str, *, version_id: str | None = None) -> None: ...


async def read_bounded(storage: ObjectStorage, key: str, *, max_bytes: int) -> bytes:
    if max_bytes < 1:
        raise ValueError('Invalid bounded object read')
    content = bytearray()
    stream = storage.open(key)
    try:
        async for chunk in stream:
            if len(content) + len(chunk) > max_bytes:
                raise ValueError('Document exceeds bounded read')
            content.extend(chunk)
    finally:
        await stream.aclose()
    return bytes(content)
