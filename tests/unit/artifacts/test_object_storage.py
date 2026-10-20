import hashlib
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.file_storage import build_document_storage_key, compute_sha256
from modules.agent.infra.storage.local_file_storage import LocalFileStorage
from shared.contracts.object_storage import ObjectStorageError, read_bounded
from shared.infra.object_storage.local import LocalObjectStorage


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
