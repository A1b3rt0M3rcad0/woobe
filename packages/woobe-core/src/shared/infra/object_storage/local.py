from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import stat
import time
from uuid import uuid4

from shared.infra.object_storage.io import run_blocking

from shared.contracts.object_storage import (
    CHUNK_BYTES, ObjectMetadata, ObjectStorageError, validate_object_key,
)


class LocalObjectStorage:
    contract_version = '1'

    def __init__(self, base_dir: str | Path, *, legacy_keys: bool = False):
        self._base_dir = Path(base_dir).expanduser().absolute()
        self._legacy_keys = legacy_keys

    def _key(self, key):
        return validate_object_key(key, legacy=self._legacy_keys)

    _io = staticmethod(run_blocking)

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
                fcntl.flock(parent, fcntl.LOCK_SH)
                try:
                    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                    stream = os.fdopen(fd, 'rb')
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        stream.close()
                        raise ObjectStorageError('invalid_object', 'Object is not an isolated regular file')
                finally:
                    fcntl.flock(parent, fcntl.LOCK_UN)
            return stream, info.st_size
        except FileNotFoundError as error:
            raise ObjectStorageError('not_found', 'Object is unavailable') from error
        except OSError as error:
            raise ObjectStorageError('unavailable', 'Object storage is unavailable') from error

    async def open(self, key: str, *, start: int = 0, end: int | None = None):
        self._key(key)
        stream, size = await self._io(self._open_read, key, on_cancel=lambda pair: pair[0].close())
        try:
            stop = size if end is None else end
            if not 0 <= start <= stop <= size:
                raise ObjectStorageError('range', 'Invalid object byte range')
            await self._io(stream.seek, start)
            remaining = stop - start
            while remaining:
                chunk = await self._io(stream.read, min(CHUNK_BYTES, remaining))
                if not chunk:
                    raise ObjectStorageError('integrity', 'Object ended before its expected size')
                remaining -= len(chunk)
                yield chunk
        except OSError as error:
            raise ObjectStorageError('unavailable', 'Object storage is unavailable') from error
        finally:
            await self._io(stream.close)

    @staticmethod
    def _metadata_key(key: str):
        return '.woobe-object-metadata/' + hashlib.sha256(key.encode()).hexdigest() + '.json'

    def _prepare(self, key: str):
        with self._parent(key, create=True) as (parent, name):
            temporary = '.woobe-staging-' + uuid4().hex + '.tmp'
            fd = os.open(temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=parent)
            stream = None
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                stream = os.fdopen(fd, 'wb')
                owned_parent = os.dup(parent)
            except BaseException:
                if stream is not None:
                    stream.close()
                else:
                    os.close(fd)
                os.unlink(temporary, dir_fd=parent)
                raise
            return stream, owned_parent, temporary, name

    @staticmethod
    def _discard(resource):
        stream, parent, temporary, name = resource
        try:
            stream.close()
            try:
                os.unlink(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass
        finally:
            os.close(parent)

    @staticmethod
    def _finish(stream):
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()

    @staticmethod
    def _write_bytes(stream, chunk):
        stream.write(chunk)

    @staticmethod
    def _promote(resource, *, replace: bool):
        stream, parent, temporary, name = resource
        if not stream.closed:
            raise RuntimeError('Only closed, verified objects can be published')
        fcntl.flock(parent, fcntl.LOCK_EX)
        try:
            if replace:
                try:
                    info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise ObjectStorageError('invalid_object', 'Replacement target is not an isolated regular file')
                os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
            else:
                os.link(temporary, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                os.unlink(temporary, dir_fd=parent)
            os.fsync(parent)
        finally:
            fcntl.flock(parent, fcntl.LOCK_UN)

    def _read_metadata(self, key):
        try:
            stream, size = self._open_read(self._metadata_key(key))
        except ObjectStorageError as error:
            if error.code == 'not_found':
                return None
            raise
        with stream:
            if size > 8192:
                raise ObjectStorageError('integrity', 'Object metadata is invalid')
            try:
                metadata = json.load(stream)
            except ValueError as error:
                raise ObjectStorageError('integrity', 'Object metadata is invalid') from error
        if (not isinstance(metadata, dict) or metadata.get('key') != key
                or type(metadata.get('size_bytes')) is not int
                or not isinstance(metadata.get('sha256'), str)
                or not isinstance(metadata.get('content_type'), str)
                or '\r' in metadata['content_type'] or '\n' in metadata['content_type']):
            raise ObjectStorageError('integrity', 'Object metadata is invalid')
        return metadata

    def _write_metadata(self, metadata: ObjectMetadata, *, replace: bool):
        resource = self._prepare(self._metadata_key(metadata.key))
        try:
            resource[0].write(json.dumps(asdict(metadata), sort_keys=True).encode())
            self._finish(resource[0])
            try:
                self._promote(resource, replace=replace)
            except FileExistsError:
                if self._read_metadata(metadata.key) != asdict(metadata):
                    raise ObjectStorageError('conflict', 'Object metadata already differs') from None
        finally:
            self._discard(resource)

    async def put(self, key: str, chunks, *, size_bytes: int, sha256: str,
                  content_type: str, replace: bool = False) -> ObjectMetadata:
        self._key(key)
        if (type(size_bytes) is not int or size_bytes < 0
                or re.fullmatch(r'[0-9a-f]{64}', sha256) is None
                or '/' not in content_type or len(content_type) > 255
                or '\r' in content_type or '\n' in content_type):
            raise ObjectStorageError('integrity', 'Invalid expected object metadata')
        resource = None
        try:
            resource = await self._io(self._prepare, key, on_cancel=self._discard)
            stream = resource[0]
            digest, size = hashlib.sha256(), 0
            async for chunk in chunks:
                if not isinstance(chunk, bytes):
                    raise ObjectStorageError('integrity', 'Object stream must contain bytes')
                size += len(chunk)
                if size > size_bytes:
                    raise ObjectStorageError('integrity', 'Object exceeds its expected size')
                digest.update(chunk)
                await self._io(self._write_bytes, stream, chunk)
            if size != size_bytes or digest.hexdigest() != sha256:
                raise ObjectStorageError('integrity', 'Object size or SHA-256 does not match')
            await self._io(self._finish, stream)
            metadata = ObjectMetadata(key, size, sha256, content_type)
            try:
                await self._io(self._promote, resource, replace=replace)
            except FileExistsError:
                current = await self.stat(key)
                if current.size_bytes != size or current.sha256 != sha256:
                    raise ObjectStorageError('conflict', 'Object already has different bytes') from None
            # Repair a metadata ACK loss only after verifying the existing bytes.
            await self._io(self._write_metadata, metadata, replace=replace)
            return metadata
        except OSError as error:
            raise ObjectStorageError('unavailable', 'Object storage is unavailable') from error
        finally:
            if resource is not None:
                await self._io(self._discard, resource)

    def _head(self, key: str):
        stream, size = self._open_read(key)
        stream.close()
        metadata = self._read_metadata(key)
        if (metadata is None or metadata['size_bytes'] != size
            or re.fullmatch(r'[0-9a-f]{64}', metadata['sha256']) is None
            or metadata.get('version_id') is not None or '/' not in metadata['content_type']):
            raise ObjectStorageError('integrity', 'Immutable object receipt metadata is unavailable or invalid')
        return ObjectMetadata(key, size, metadata['sha256'], metadata['content_type'])

    async def head(self, key: str):
        self._key(key)
        try:
            return await self._io(self._head, key)
        except (ValueError, KeyError, TypeError) as error:
            raise ObjectStorageError('integrity', 'Object receipt metadata is invalid') from error
        except OSError as error:
            raise ObjectStorageError('unavailable', 'Object storage is unavailable') from error

    def _stat(self, key: str):
        stream, size = self._open_read(key)
        digest = hashlib.sha256()
        with stream:
            while chunk := stream.read(CHUNK_BYTES):
                digest.update(chunk)
        content_type = mimetypes.guess_type(key)[0] or 'application/octet-stream'
        metadata = self._read_metadata(key)
        if metadata is not None:
            if metadata['sha256'] != digest.hexdigest() or metadata['size_bytes'] != size:
                raise ObjectStorageError('integrity', 'Object metadata does not match its bytes')
            content_type = metadata['content_type']
        return ObjectMetadata(key, size, digest.hexdigest(), content_type)

    async def stat(self, key: str):
        self._key(key)
        try:
            return await self._io(self._stat, key)
        except (ValueError, KeyError) as error:
            raise ObjectStorageError('integrity', 'Object metadata is invalid') from error
        except OSError as error:
            raise ObjectStorageError('unavailable', 'Object storage is unavailable') from error

    def _delete_key(self, key: str):
        try:
            with self._parent(key) as (parent, name):
                os.unlink(name, dir_fd=parent)
                os.fsync(parent)
        except FileNotFoundError:
            pass

    async def delete(self, key: str, *, version_id: str | None = None):
        self._key(key)
        try:
            await self._io(self._delete_key, key)
            await self._io(self._delete_key, self._metadata_key(key))
        except OSError as error:
            raise ObjectStorageError('unavailable', 'Object storage is unavailable') from error

    def _cleanup_staging(self, older_than_seconds):
        if older_than_seconds < 60:
            raise ValueError('Staging cleanup requires at least a 60 second grace period')
        removed = 0
        try:
            root = os.open(self._base_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return 0
        try:
            def fail_on_unreadable(error):
                raise error

            for directory, subdirectories, filenames, parent in os.fwalk(
                '.', dir_fd=root, follow_symlinks=False, onerror=fail_on_unreadable
            ):
                for name in filenames:
                    if re.fullmatch(r'\.woobe-staging-[0-9a-f]{32}\.tmp', name) is None:
                        continue
                    try:
                        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                    except FileNotFoundError:
                        continue
                    try:
                        info = os.fstat(fd)
                        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mtime > time.time() - older_than_seconds:
                            continue
                        try:
                            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError:
                            continue
                        os.unlink(name, dir_fd=parent)
                        removed += 1
                    finally:
                        os.close(fd)
        finally:
            os.close(root)
        return removed

    async def cleanup_staging(self, *, older_than_seconds: int = 3600):
        try:
            return await self._io(self._cleanup_staging, older_than_seconds)
        except OSError as error:
            raise ObjectStorageError('unavailable', 'Staging cleanup is unavailable') from error
