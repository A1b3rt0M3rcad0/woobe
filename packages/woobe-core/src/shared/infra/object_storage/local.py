from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import stat

from shared.contracts.object_storage import (
    CHUNK_BYTES, ObjectMetadata, ObjectStorageError, validate_object_key,
)


class LocalObjectStorage:
    contract_version = '1'

    def __init__(self, base_dir: str | Path):
        self._base_dir = Path(base_dir).expanduser().absolute()

    @contextmanager
    def _parent(self, key: str, *, create: bool = False):
        descriptors = []
        try:
            if create:
                self._base_dir.mkdir(parents=True, exist_ok=True)
            parent = os.open(self._base_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptors.append(parent)
            parts = key.split('/')
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=parent)
                    except FileExistsError:
                        pass
                parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                descriptors.append(parent)
            yield parent, parts[-1]
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    def _open_read(self, key: str):
        try:
            with self._parent(key) as (parent, name):
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            stream = os.fdopen(fd, 'rb')
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                stream.close()
                raise ObjectStorageError('invalid_object', 'Object is not an isolated regular file')
            return stream, info.st_size
        except FileNotFoundError as error:
            raise ObjectStorageError('not_found', 'Object is unavailable') from error
        except OSError as error:
            raise ObjectStorageError('unavailable', 'Object storage is unavailable') from error

    async def open(self, key: str, *, start: int = 0, end: int | None = None):
        validate_object_key(key)
        stream, size = await asyncio.to_thread(self._open_read, key)
        try:
            stop = size if end is None else end
            if not 0 <= start <= stop <= size:
                raise ObjectStorageError('range', 'Invalid object byte range')
            await asyncio.to_thread(stream.seek, start)
            remaining = stop - start
            while remaining:
                chunk = await asyncio.to_thread(stream.read, min(CHUNK_BYTES, remaining))
                if not chunk:
                    raise ObjectStorageError('integrity', 'Object ended before its expected size')
                remaining -= len(chunk)
                yield chunk
        except OSError as error:
            raise ObjectStorageError('unavailable', 'Object storage is unavailable') from error
        finally:
            await asyncio.to_thread(stream.close)

    @staticmethod
    def _metadata_key(key: str):
        return '.woobe-object-metadata/' + hashlib.sha256(key.encode()).hexdigest() + '.json'

    def _write_metadata(self, metadata: ObjectMetadata):
        payload = json.dumps(asdict(metadata), sort_keys=True).encode()
        with self._parent(self._metadata_key(metadata.key), create=True) as (parent, name):
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(fd, 'wb') as output:
                output.write(payload)

    def _write_open(self, key: str, *, replace: bool):
        try:
            with self._parent(key, create=True) as (parent, name):
                flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
                if not replace:
                    flags |= os.O_EXCL
                fd = os.open(name, flags, 0o600, dir_fd=parent)
            stream = os.fdopen(fd, 'wb')
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                stream.close()
                raise ObjectStorageError('invalid_object', 'Object is not an isolated regular file')
            stream.truncate(0)
            return stream
        except FileExistsError as error:
            raise ObjectStorageError('conflict', 'Object already exists') from error
        except OSError as error:
            raise ObjectStorageError('unavailable', 'Object storage is unavailable') from error

    async def put(self, key: str, chunks, *, size_bytes: int, sha256: str,
                  content_type: str, replace: bool = False) -> ObjectMetadata:
        validate_object_key(key)
        if (size_bytes < 0 or re.fullmatch(r'[0-9a-f]{64}', sha256) is None
                or not content_type or len(content_type) > 255
                or '\r' in content_type or '\n' in content_type):
            raise ObjectStorageError('integrity', 'Invalid expected object metadata')
        stream = await asyncio.to_thread(self._write_open, key, replace=replace)
        digest, size = hashlib.sha256(), 0
        try:
            async for chunk in chunks:
                if not isinstance(chunk, bytes):
                    raise ObjectStorageError('integrity', 'Object stream must contain bytes')
                size += len(chunk)
                if size > size_bytes:
                    raise ObjectStorageError('integrity', 'Object exceeds its expected size')
                digest.update(chunk)
                await asyncio.to_thread(stream.write, chunk)
            if size != size_bytes or digest.hexdigest() != sha256:
                raise ObjectStorageError('integrity', 'Object size or SHA-256 does not match')
            await asyncio.to_thread(stream.close)
            metadata = ObjectMetadata(key, size, sha256, content_type)
            if replace:
                await asyncio.to_thread(self._delete_key, self._metadata_key(key))
            await asyncio.to_thread(self._write_metadata, metadata)
            return metadata
        except BaseException as error:
            await asyncio.to_thread(stream.close)
            await self.delete(key)
            if isinstance(error, OSError):
                raise ObjectStorageError('unavailable', 'Object storage is unavailable') from error
            raise

    def _stat(self, key: str):
        stream, size = self._open_read(key)
        digest = hashlib.sha256()
        with stream:
            while chunk := stream.read(CHUNK_BYTES):
                digest.update(chunk)
        content_type = mimetypes.guess_type(key)[0] or 'application/octet-stream'
        try:
            metadata_stream, metadata_size = self._open_read(self._metadata_key(key))
        except ObjectStorageError as error:
            if error.code != 'not_found':
                raise
        else:
            with metadata_stream:
                if metadata_size > 8192:
                    raise ObjectStorageError('integrity', 'Object metadata is invalid')
                metadata = json.load(metadata_stream)
                if (metadata.get('key') != key or metadata.get('sha256') != digest.hexdigest()
                        or metadata.get('size_bytes') != size):
                    raise ObjectStorageError('integrity', 'Object metadata does not match its bytes')
                content_type = metadata['content_type']
        return ObjectMetadata(key, size, digest.hexdigest(), content_type)

    async def stat(self, key: str):
        validate_object_key(key)
        try:
            return await asyncio.to_thread(self._stat, key)
        except (ValueError, KeyError) as error:
            raise ObjectStorageError('integrity', 'Object metadata is invalid') from error
        except OSError as error:
            raise ObjectStorageError('unavailable', 'Object storage is unavailable') from error

    def _delete_key(self, key: str):
        try:
            with self._parent(key) as (parent, name):
                os.unlink(name, dir_fd=parent)
        except FileNotFoundError:
            pass

    async def delete(self, key: str):
        validate_object_key(key)
        try:
            await asyncio.to_thread(self._delete_key, key)
            await asyncio.to_thread(self._delete_key, self._metadata_key(key))
        except OSError as error:
            raise ObjectStorageError('unavailable', 'Object storage is unavailable') from error
