from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
import hashlib
import re

from botocore.exceptions import BotoCoreError, ClientError

from shared.contracts.object_storage import (
    CHUNK_BYTES, ObjectMetadata, ObjectStorageError, validate_object_key,
)
from shared.infra.object_storage.io import run_blocking


def _storage_error(error):
    if isinstance(error, ClientError):
        status = error.response.get('ResponseMetadata', {}).get('HTTPStatusCode')
        code = error.response.get('Error', {}).get('Code')
        if status == 404 and code != 'NoSuchBucket':
            return ObjectStorageError('not_found', 'Object is unavailable')
        if status == 412:
            return ObjectStorageError('conflict', 'Object already exists')
        if status == 416:
            return ObjectStorageError('range', 'Invalid object byte range')
    return ObjectStorageError('unavailable', 'S3 object storage is unavailable')


class S3ObjectStorage:
    """Private multipart staging + conditional, immutable completion.

    Parts/UploadIds are backend-only: no client URL can mutate a completed key.
    A conditional-write-unsupported endpoint fails closed; it is not retried as
    an unconditional write. Actual SHA-256 is verified after completion.
    """

    contract_version = '1'

    def __init__(self, client, *, bucket: str, prefix: str = '',
                 part_size: int = 8 * 1024 * 1024, legacy_keys: bool = False,
                 server_side_encryption: str | None = None, clock=None,
                 max_uploads: int = 4):
        if not bucket or not 5 * 1024 * 1024 <= part_size <= 64 * 1024 * 1024:
            raise ValueError('S3 bucket and bounded multipart part size are required')
        self._client = client
        self._bucket = bucket
        self._prefix = prefix.strip().strip('/')
        self._part_size = part_size
        self._legacy_keys = legacy_keys
        self._encryption = server_side_encryption
        self._clock = clock or (lambda: datetime.now(UTC))
        if type(max_uploads) is not int or not 1 <= max_uploads <= 32:
            raise ValueError('S3 upload concurrency must be between 1 and 32')
        self._uploads = asyncio.Semaphore(max_uploads)

    def _physical_key(self, key):
        if self._legacy_keys:
            if not isinstance(key, str) or not key or '\x00' in key or len(key.encode()) > 1024:
                raise ObjectStorageError('invalid_key', 'Invalid legacy object key')
        else:
            validate_object_key(key)
        physical = f'{self._prefix}/{key}' if self._prefix else key
        if len(physical.encode()) > 1024:
            raise ObjectStorageError('invalid_key', 'Object storage key is too long')
        return physical

    async def open(self, key: str, *, start: int = 0, end: int | None = None):
        physical = self._physical_key(key)
        if start < 0 or (end is not None and end < start):
            raise ObjectStorageError('range', 'Invalid object byte range')
        body = None
        try:
            if end is not None and end == start:
                head = await run_blocking(self._client.head_object, Bucket=self._bucket, Key=physical)
                if start > head['ContentLength']:
                    raise ObjectStorageError('range', 'Invalid object byte range')
                return
            kwargs = {'Bucket': self._bucket, 'Key': physical}
            if start or end is not None:
                kwargs['Range'] = f'bytes={start}-' + (str(end - 1) if end is not None else '')
            response = await run_blocking(self._client.get_object, **kwargs,
                                          on_cancel=lambda value: value['Body'].close())
            body = response['Body']
            if 'Range' in kwargs:
                match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.get('ContentRange', ''))
                if (match is None or int(match[1]) != start
                        or (end is not None and int(match[2]) + 1 != end)):
                    raise ObjectStorageError('range', 'S3 endpoint did not honor the requested range')
            expected, consumed = response.get('ContentLength'), 0
            while expected is None or consumed < expected:
                maximum = CHUNK_BYTES if expected is None else min(CHUNK_BYTES, expected - consumed)
                chunk = await run_blocking(body.read, maximum)
                if not chunk:
                    break
                consumed += len(chunk)
                yield chunk
            if expected is not None and consumed != expected:
                raise ObjectStorageError('integrity', 'S3 object ended before its expected size')
        except (BotoCoreError, ClientError, OSError) as error:
            if isinstance(error, ClientError) and error.response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 416 and end is None:
                head = await run_blocking(self._client.head_object, Bucket=self._bucket, Key=physical)
                if start == head['ContentLength']:
                    return
            raise _storage_error(error) from error
        finally:
            if body is not None:
                await run_blocking(body.close)

    async def stat(self, key: str):
        physical = self._physical_key(key)
        try:
            head = await run_blocking(self._client.head_object, Bucket=self._bucket, Key=physical)
            digest, size = hashlib.sha256(), 0
            stream = self.open(key)
            try:
                async for chunk in stream:
                    digest.update(chunk)
                    size += len(chunk)
            finally:
                await stream.aclose()
            expected = head.get('Metadata', {}).get('sha256')
            if head['ContentLength'] != size or (expected is not None and expected != digest.hexdigest()):
                raise ObjectStorageError('integrity', 'S3 bytes do not match their recorded SHA-256/size')
            return ObjectMetadata(key, size, digest.hexdigest(),
                head.get('ContentType') or 'application/octet-stream', head.get('VersionId'))
        except (BotoCoreError, ClientError, OSError) as error:
            raise _storage_error(error) from error

    async def _abort(self, physical, upload_id):
        try:
            await run_blocking(self._client.abort_multipart_upload, Bucket=self._bucket,
                               Key=physical, UploadId=upload_id)
        except ClientError as error:
            if error.response.get('Error', {}).get('Code') != 'NoSuchUpload':
                raise

    async def _reconcile(self, key, *, size, digest, content_type):
        try:
            current = await self.stat(key)
        except ObjectStorageError as error:
            if error.code == 'not_found':
                raise ObjectStorageError('unavailable', 'S3 publication could not be reconciled') from error
            raise
        if (current.size_bytes, current.sha256, current.content_type) != (size, digest, content_type):
            raise ObjectStorageError('conflict', 'S3 object already has different bytes or metadata')
        return current

    async def put(self, key, chunks, *, size_bytes, sha256, content_type,
                  replace=False, attributes=None):
        async with self._uploads:
            return await self._put(key, chunks, size_bytes=size_bytes, sha256=sha256,
                                   content_type=content_type, replace=replace,
                                   attributes=attributes)

    async def _put(self, key, chunks, *, size_bytes, sha256, content_type,
                   replace=False, attributes=None):
        physical = self._physical_key(key)
        if (type(size_bytes) is not int or not 0 <= size_bytes <= 5 * 1024**4
                or re.fullmatch(r'[0-9a-f]{64}', sha256) is None
                or not isinstance(content_type, str) or '/' not in content_type
                or len(content_type) > 255 or '\r' in content_type or '\n' in content_type):
            raise ObjectStorageError('integrity', 'Invalid expected object metadata')
        metadata = dict(attributes or {})
        if any(not isinstance(value, str) for value in metadata.values()):
            raise ObjectStorageError('integrity', 'Invalid S3 object attributes')
        metadata['sha256'] = sha256
        options = {'Bucket': self._bucket, 'Key': physical, 'ContentType': content_type,
                   'Metadata': metadata}
        if self._encryption:
            options['ServerSideEncryption'] = self._encryption
        upload_id = None
        completed = False
        digest, size = hashlib.sha256(), 0
        parts, buffer = [], bytearray()
        try:
            if size_bytes:
                created = await run_blocking(self._client.create_multipart_upload, **options,
                    ChecksumAlgorithm='SHA256',
                    on_cancel=lambda result: self._client.abort_multipart_upload(
                        Bucket=self._bucket, Key=physical, UploadId=result['UploadId']))
                upload_id = created['UploadId']

            async def send_part(content):
                number = len(parts) + 1
                if number > 10_000:
                    raise ObjectStorageError('integrity', 'Multipart part count limit exceeded')
                checksum = base64.b64encode(hashlib.sha256(content).digest()).decode()
                response = await run_blocking(self._client.upload_part, Bucket=self._bucket,
                    Key=physical, UploadId=upload_id, PartNumber=number, Body=content,
                    ChecksumSHA256=checksum)
                parts.append({'PartNumber': number, 'ETag': response['ETag'], 'ChecksumSHA256': checksum})

            async for chunk in chunks:
                if not isinstance(chunk, bytes):
                    raise ObjectStorageError('integrity', 'Object stream must contain bytes')
                size += len(chunk)
                if size > size_bytes:
                    raise ObjectStorageError('integrity', 'Object exceeds its expected size')
                digest.update(chunk)
                view = memoryview(chunk)
                offset = 0
                while offset < len(view):
                    amount = min(self._part_size - len(buffer), len(view) - offset)
                    buffer.extend(view[offset:offset + amount])
                    offset += amount
                    if len(buffer) == self._part_size:
                        await send_part(bytes(buffer))
                        buffer.clear()
            if size != size_bytes or digest.hexdigest() != sha256:
                raise ObjectStorageError('integrity', 'Object size or SHA-256 does not match')
            if upload_id is not None:
                if buffer:
                    await send_part(bytes(buffer))
                kwargs = {'Bucket': self._bucket, 'Key': physical, 'UploadId': upload_id,
                          'MultipartUpload': {'Parts': parts}}
                if not replace:
                    kwargs['IfNoneMatch'] = '*'
                try:
                    await run_blocking(self._client.complete_multipart_upload, **kwargs)
                    completed = True
                except (BotoCoreError, ClientError, OSError):
                    # A lost ACK may be followed by NoSuchUpload. Read identity,
                    # never remove a condition or silently replace an object.
                    current = await self._reconcile(key, size=size, digest=sha256, content_type=content_type)
                    return current
            else:
                kwargs = options | {'Body': b'', 'ChecksumSHA256': base64.b64encode(digest.digest()).decode()}
                if not replace:
                    kwargs['IfNoneMatch'] = '*'
                try:
                    await run_blocking(self._client.put_object, **kwargs)
                except (BotoCoreError, ClientError, OSError):
                    return await self._reconcile(key, size=size, digest=sha256, content_type=content_type)
            return await self._reconcile(key, size=size, digest=sha256, content_type=content_type)
        except (BotoCoreError, ClientError, OSError) as error:
            raise _storage_error(error) from error
        finally:
            if upload_id is not None and not completed:
                try:
                    await self._abort(physical, upload_id)
                except (BotoCoreError, ClientError, OSError):
                    # Expiry reconciliation can find abandoned private multipart
                    # state by key, without deleting any published original.
                    pass

    async def delete(self, key):
        try:
            await run_blocking(self._client.delete_object, Bucket=self._bucket,
                              Key=self._physical_key(key))
        except (BotoCoreError, ClientError, OSError) as error:
            raise _storage_error(error) from error

    async def abort_expired_multipart(self, *, prefix, older_than_seconds, is_active):
        if older_than_seconds < 60:
            raise ValueError('Multipart cleanup requires at least a 60 second grace period')
        physical_prefix = self._physical_key(prefix.rstrip('/')) + '/'
        cutoff = self._clock() - timedelta(seconds=older_than_seconds)
        kwargs = {'Bucket': self._bucket, 'Prefix': physical_prefix}
        count = 0
        try:
            while True:
                response = await run_blocking(self._client.list_multipart_uploads, **kwargs)
                for upload in response.get('Uploads', []):
                    key = upload['Key']
                    if not key.startswith(physical_prefix) or upload['Initiated'] >= cutoff:
                        continue
                    logical = key[len(self._prefix) + 1:] if self._prefix else key
                    if await is_active(logical, upload['UploadId']):
                        continue
                    await self._abort(key, upload['UploadId'])
                    count += 1
                if not response.get('IsTruncated'):
                    break
                kwargs.update(KeyMarker=response['NextKeyMarker'],
                              UploadIdMarker=response['NextUploadIdMarker'])
            return count
        except (BotoCoreError, ClientError, OSError) as error:
            raise _storage_error(error) from error

    async def close(self):
        await run_blocking(self._client.close)
