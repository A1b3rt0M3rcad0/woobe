import hashlib
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.file_storage import build_document_storage_key, compute_sha256
from modules.agent.infra.storage.local_file_storage import LocalFileStorage
from shared.contracts.object_storage import ObjectStorageError, read_bounded
from shared.infra.object_storage.local import LocalObjectStorage
from shared.infra.object_storage.s3 import S3ObjectStorage


async def chunks(content, length=8192):
    for offset in range(0, len(content), length):
        yield content[offset:offset + length]


@pytest.mark.parametrize('content', [b'', b'small document', b'x' * 262_144])
async def test_generic_stream_metadata_range_restart_and_delete(tmp_path, content):
    storage = LocalObjectStorage(tmp_path)
    digest = hashlib.sha256(content).hexdigest()
    saved = await storage.put('project/revision/original', chunks(content), size_bytes=len(content),
                               sha256=digest, content_type='application/custom')
    restarted = LocalObjectStorage(tmp_path)
    assert await restarted.stat(saved.key) == saved
    assert await read_bounded(restarted, saved.key, max_bytes=max(1, len(content))) == content
    assert b''.join([part async for part in restarted.open(saved.key, start=0, end=min(5, len(content)))]) == content[:5]
    await restarted.delete(saved.key)
    await restarted.delete(saved.key)
    with pytest.raises(ObjectStorageError) as error:
        await restarted.stat(saved.key)
    assert error.value.code == 'not_found'


async def test_declared_integrity_and_immutable_object_identity(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    content = b'original'
    key = 'revision/original'
    await storage.put(key, chunks(content), size_bytes=len(content), sha256=compute_sha256(content), content_type='text/plain')
    with pytest.raises(ObjectStorageError) as error:
        await storage.put(key, chunks(b'replaced'), size_bytes=8, sha256=compute_sha256(b'replaced'), content_type='text/plain')
    assert error.value.code == 'conflict'
    assert await read_bounded(storage, key, max_bytes=8) == content
    with pytest.raises(ObjectStorageError) as error:
        await storage.put('revision/bad', chunks(content), size_bytes=8, sha256='0' * 64, content_type='text/plain')
    assert error.value.code == 'integrity'
    with pytest.raises(ObjectStorageError):
        await storage.stat('revision/bad')


async def test_legacy_knowledge_facade_keeps_keys_and_original_bytes(tmp_path):
    project, collection, document = uuid4(), uuid4(), uuid4()
    legacy = LocalFileStorage(tmp_path)
    saved = await legacy.save_document(content=b'first', project_id=project, collection_id=collection,
        document_id=document, file_name='notes.md', content_type='text/markdown')
    assert saved.storage_key == build_document_storage_key(project_id=project, collection_id=collection,
                                                            document_id=document, file_name='notes.md')
    assert (tmp_path / saved.storage_key).read_bytes() == b'first'
    assert saved.sha256 == compute_sha256(b'first')
    replaced = await legacy.save_document(content=b'second', project_id=project, collection_id=collection,
        document_id=document, file_name='notes.md', content_type='text/markdown')
    assert replaced.storage_key == saved.storage_key
    assert await legacy.read_document(saved.storage_key) == b'second'
    assert await legacy.read_document_bounded(saved.storage_key, max_bytes=6) == b'second'


async def test_bounded_consumption_and_early_close_do_not_read_whole_stream(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    content = b'a' * 262_144
    await storage.put('large', chunks(content), size_bytes=len(content), sha256=compute_sha256(content), content_type='text/plain')
    stream = storage.open('large')
    assert len(await anext(stream)) == 65_536
    await stream.aclose()
    with pytest.raises(ValueError, match='bounded'):
        await read_bounded(storage, 'large', max_bytes=10)
    assert await storage.stat('large')


async def test_local_head_returns_only_declared_receipt_and_stat_still_verifies_payload(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    content = b'x' * 1_048_576
    receipt = await storage.put('revision/text', chunks(content), size_bytes=len(content),
        sha256=compute_sha256(content), content_type='text/plain')
    assert await storage.head(receipt.key) == receipt
    # The distinction is intentional: bounded readers authenticate independent
    # segment hashes, whereas publication/original verification uses strong stat.
    (tmp_path / receipt.key).write_bytes(b'y' * len(content))
    assert await storage.head(receipt.key) == receipt
    with pytest.raises(ObjectStorageError) as failure:
        await storage.stat(receipt.key)
    assert failure.value.code == 'integrity'
    (tmp_path / receipt.key).write_bytes(b'truncated')
    with pytest.raises(ObjectStorageError) as failure:
        await storage.head(receipt.key)
    assert failure.value.code == 'integrity'


async def test_s3_temporary_download_url_is_exact_key_and_capped_at_one_minute():
    class Client:
        def __init__(self):
            self.call = None

        def generate_presigned_url(self, operation, *, Params, ExpiresIn):
            self.call = (operation, Params, ExpiresIn)
            return 'https://objects.example/bucket/object?signature=private'

    client = Client()
    storage = S3ObjectStorage(client, bucket='bucket', prefix='tenant', part_size=5 * 1024 * 1024)
    url = await storage.presign_get('workspace/revision', expires_seconds=60)
    assert url.startswith('https://objects.example/')
    assert client.call == (
        'get_object',
        {'Bucket': 'bucket', 'Key': 'tenant/workspace/revision'},
        60,
    )
    with pytest.raises(ObjectStorageError, match='60 seconds'):
        await storage.presign_get('workspace/revision', expires_seconds=61)


async def test_s3_purge_removes_all_versions_of_only_the_exact_key():
    class Client:
        def __init__(self):
            self.versions = [
                {'Key': 'tenant/workspace/object', 'VersionId': 'v1'},
                {'Key': 'tenant/workspace/object', 'VersionId': 'delete-marker', 'marker': True},
                {'Key': 'tenant/workspace/object-copy', 'VersionId': 'keep'},
            ]

        def list_object_versions(self, **kwargs):
            matching = [item for item in self.versions if item['Key'].startswith(kwargs['Prefix'])]
            return {
                'Versions': [item for item in matching if not item.get('marker')],
                'DeleteMarkers': [item for item in matching if item.get('marker')],
                'IsTruncated': False,
            }

        def delete_objects(self, *, Bucket, Delete):
            removed = {(item['Key'], item['VersionId']) for item in Delete['Objects']}
            self.versions = [item for item in self.versions
                if (item['Key'], item['VersionId']) not in removed]
            return {'Deleted': Delete['Objects']}

    client = Client()
    storage = S3ObjectStorage(client, bucket='bucket', prefix='tenant')
    await storage.delete('workspace/object')
    assert client.versions == [{'Key': 'tenant/workspace/object-copy', 'VersionId': 'keep'}]


async def test_s3_purge_can_delete_a_known_version_without_listing():
    class Client:
        def __init__(self):
            self.calls = []

        def delete_object(self, **kwargs):
            self.calls.append(kwargs)

        def list_object_versions(self, **kwargs):
            raise AssertionError('known versions do not need a prefix listing')

    client = Client()
    storage = S3ObjectStorage(client, bucket='bucket', prefix='tenant')
    await storage.delete('workspace/object', version_id='immutable-v1')
    assert client.calls == [{
        'Bucket': 'bucket', 'Key': 'tenant/workspace/object', 'VersionId': 'immutable-v1',
    }]
