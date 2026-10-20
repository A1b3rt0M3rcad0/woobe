import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
from uuid import uuid4
from unittest.mock import patch

from botocore.exceptions import ReadTimeoutError
import pytest

from modules.agent.application.interfaces.file_storage import build_document_storage_key
from modules.agent.infra.storage.s3_file_storage import S3FileStorage
from shared.contracts.object_storage import ObjectMetadata, ObjectStorageError, read_bounded
from shared.infra.object_storage.s3 import S3ObjectStorage
from shared.infra.object_storage.s3_factory import create_s3_object_storage


async def chunks(content, length=65_536):
    for offset in range(0, len(content), length):
        yield content[offset:offset + length]


def storage(backend, *, clock=None):
    client, bucket = backend
    return S3ObjectStorage(client, bucket=bucket, prefix=uuid4().hex,
                           part_size=5 * 1024 * 1024, clock=clock)


async def put(store, key, content):
    return await store.put(key, chunks(content), size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(), content_type='application/octet-stream')


@pytest.mark.parametrize('content', [b'', b'small object', b'm' * (11 * 1024 * 1024)])
async def test_real_s3_streams_checksum_range_and_immutable_replay(s3_backend, content):
    store = storage(s3_backend)
    receipt = await put(store, 'revision/original', content)
    assert receipt == await store.stat('revision/original')
    assert receipt == await put(store, 'revision/original', content)
    assert await read_bounded(store, 'revision/original', max_bytes=max(1, len(content))) == content
    assert b''.join([chunk async for chunk in store.open('revision/original', start=0, end=min(5, len(content)))]) == content[:5]
    client, bucket = s3_backend
    metadata = client.head_object(Bucket=bucket, Key=store._physical_key('revision/original'))
    assert metadata['Metadata']['sha256'] == hashlib.sha256(content).hexdigest()
    assert receipt.sha256 != metadata['ETag'].strip('"')
    assert not client.list_multipart_uploads(Bucket=bucket, Prefix=store._prefix).get('Uploads')
    await store.delete('revision/original')
    await store.delete('revision/original')


async def test_real_conditional_completion_has_one_winner(s3_backend):
    store = storage(s3_backend)
    results = await asyncio.gather(put(store, 'race', b'left'), put(store, 'race', b'right'),
                                    return_exceptions=True)
    assert sum(isinstance(value, ObjectMetadata) for value in results) == 1
    assert sum(isinstance(value, ObjectStorageError) and value.code == 'conflict' for value in results) == 1
    client, bucket = s3_backend
    assert not client.list_multipart_uploads(Bucket=bucket, Prefix=store._prefix).get('Uploads')


async def test_failed_checksum_and_interrupted_input_abort_real_multiparts(s3_backend):
    store = storage(s3_backend)
    with pytest.raises(ObjectStorageError) as failure:
        await store.put('bad', chunks(b'bytes'), size_bytes=5, sha256='0' * 64,
                         content_type='text/plain')
    assert failure.value.code == 'integrity'

    async def interrupted():
        yield b'a' * (5 * 1024 * 1024)
        raise ConnectionError('injected disconnected source')

    with pytest.raises(ObjectStorageError):
        await store.put('interrupted', interrupted(), size_bytes=6 * 1024 * 1024,
                         sha256='0' * 64, content_type='application/octet-stream')
    client, bucket = s3_backend
    assert not client.list_multipart_uploads(Bucket=bucket, Prefix=store._prefix).get('Uploads')
    assert not client.list_objects_v2(Bucket=bucket, Prefix=store._prefix).get('Contents')


async def test_real_complete_ack_loss_is_recovered_by_hash_without_republication(s3_backend, monkeypatch):
    store = storage(s3_backend)
    client, bucket = s3_backend
    original = client.complete_multipart_upload
    calls = []

    def lose_response(**kwargs):
        calls.append(kwargs['Key'])
        original(**kwargs)
        raise ReadTimeoutError(endpoint_url='local-test-s3')

    with monkeypatch.context() as local:
        local.setattr(client, 'complete_multipart_upload', lose_response)
        first = await put(store, 'lost-response', b'complete bytes')
    replay = await put(store, 'lost-response', b'complete bytes')
    assert replay == first and len(calls) == 1
    assert not client.list_multipart_uploads(Bucket=bucket, Prefix=store._prefix).get('Uploads')


async def test_expired_multipart_cleanup_checks_active_owner_and_prefix(s3_backend):
    now = datetime.now(UTC)
    store = storage(s3_backend, clock=lambda: now + timedelta(hours=2))
    client, bucket = s3_backend
    physical = store._physical_key('expired/original')
    upload = client.create_multipart_upload(Bucket=bucket, Key=physical)['UploadId']

    async def active(key, upload_id):
        assert key == 'expired/original' and upload_id == upload
        return True

    assert await store.abort_expired_multipart(prefix='expired', older_than_seconds=3600, is_active=active) == 0

    async def inactive(key, upload_id):
        return False

    assert await store.abort_expired_multipart(prefix='expired', older_than_seconds=3600, is_active=inactive) == 1
    assert not client.list_multipart_uploads(Bucket=bucket, Prefix=store._prefix).get('Uploads')


async def test_legacy_keys_attributes_and_bounded_reads_survive_factory_refactor(s3_backend):
    client, bucket = s3_backend
    project, collection, document = uuid4(), uuid4(), uuid4()
    with patch('boto3.client', return_value=client) as factory:
        legacy = S3FileStorage(bucket=bucket, prefix='legacy', force_path_style=True)
    assert factory.call_args.kwargs['config'].signature_version == 's3v4'
    assert 'verify' not in factory.call_args.kwargs
    stored = await legacy.save_document(content=b'knowledge', project_id=project,
        collection_id=collection, document_id=document, file_name='notes.md', content_type='text/markdown')
    assert stored.storage_key == build_document_storage_key(project_id=project,
        collection_id=collection, document_id=document, file_name='notes.md', prefix='legacy')
    head = client.head_object(Bucket=bucket, Key=stored.storage_key)
    assert head['Metadata']['project_id'] == str(project)
    assert head['Metadata']['collection_id'] == str(collection)
    assert head['Metadata']['document_id'] == str(document)
    assert head['Metadata']['original_file_name'] == 'notes.md'
    assert await legacy.read_document_bounded(stored.storage_key, max_bytes=9) == b'knowledge'
    with pytest.raises(ValueError):
        await legacy.read_document_bounded(stored.storage_key, max_bytes=8)
    await legacy.save_document(content=b'replaced', project_id=project, collection_id=collection,
        document_id=document, file_name='notes.md', content_type='text/markdown')
    assert await legacy.read_document(stored.storage_key) == b'replaced'
    await legacy.delete(stored.storage_key)


async def test_factory_uses_existing_credential_chain_and_preserves_tls_verification(s3_backend):
    client, bucket = s3_backend
    with patch('boto3.client', return_value=client) as factory:
        store = create_s3_object_storage(bucket=bucket, prefix='configured', force_path_style=True)
    assert factory.call_args.args == ('s3',)
    assert not {'aws_access_key_id', 'aws_secret_access_key', 'verify'} & factory.call_args.kwargs.keys()
    receipt = await put(store, 'factory', b'real bytes')
    assert receipt.sha256 == hashlib.sha256(b'real bytes').hexdigest()


async def test_real_read_can_be_retried_and_failed_part_never_publishes(s3_backend, monkeypatch):
    store = storage(s3_backend)
    client, bucket = s3_backend
    await put(store, 'read-retry', b'readable')
    with monkeypatch.context() as local:
        def timeout(**kwargs):
            raise ReadTimeoutError(endpoint_url='local-test-s3')
        local.setattr(client, 'get_object', timeout)
        with pytest.raises(ObjectStorageError) as failure:
            await read_bounded(store, 'read-retry', max_bytes=8)
        assert failure.value.code == 'unavailable'
    assert await read_bounded(store, 'read-retry', max_bytes=8) == b'readable'
    with monkeypatch.context() as local:
        local.setattr(client, 'upload_part', timeout)
        with pytest.raises(ObjectStorageError):
            await put(store, 'part-timeout', b'never published')
    with pytest.raises(ObjectStorageError) as failure:
        await store.stat('part-timeout')
    assert failure.value.code == 'not_found'
    assert not client.list_multipart_uploads(Bucket=bucket, Prefix=store._prefix).get('Uploads')


async def test_upload_concurrency_is_bounded_before_consuming_sources(s3_backend):
    client, bucket = s3_backend
    store = S3ObjectStorage(client, bucket=bucket, prefix=uuid4().hex, max_uploads=1)
    entered, release = asyncio.Event(), asyncio.Event()
    second_entered = asyncio.Event()

    async def first_source():
        entered.set()
        await release.wait()
        yield b'one'

    async def second_source():
        second_entered.set()
        yield b'two'

    first = asyncio.create_task(store.put('one', first_source(), size_bytes=3,
        sha256=hashlib.sha256(b'one').hexdigest(), content_type='text/plain'))
    await entered.wait()
    second = asyncio.create_task(store.put('two', second_source(), size_bytes=3,
        sha256=hashlib.sha256(b'two').hexdigest(), content_type='text/plain'))
    await asyncio.sleep(0.02)
    assert not second_entered.is_set()
    release.set()
    assert all(isinstance(result, ObjectMetadata) for result in await asyncio.gather(first, second))
