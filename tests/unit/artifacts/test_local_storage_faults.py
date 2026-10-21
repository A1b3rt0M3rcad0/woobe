import asyncio
import errno
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import tracemalloc

import pytest

from modules.artifacts.domain.models import ArtifactRef, Scope, artifact_object_key
from modules.artifacts.infra.storage.scratch import artifact_scratch
from shared.contracts.object_storage import ObjectMetadata, ObjectStorageError, read_bounded
from shared.infra.object_storage.local import LocalObjectStorage


async def chunks(content):
    yield content


async def put(storage, key, content, **kwargs):
    return await storage.put(key, chunks(content), size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(), content_type='text/plain', **kwargs)


async def test_staging_is_unaddressable_until_verified_atomic_publication(tmp_path):
    store = LocalObjectStorage(tmp_path)
    started, release = asyncio.Event(), asyncio.Event()

    async def slow():
        yield b'first'
        started.set()
        await release.wait()
        yield b'last'

    task = asyncio.create_task(store.put('revision/original', slow(), size_bytes=9,
        sha256=hashlib.sha256(b'firstlast').hexdigest(), content_type='text/plain'))
    await started.wait()
    assert not (tmp_path / 'revision/original').exists()
    staging = list(tmp_path.rglob('.woobe-staging-*'))
    assert len(staging) == 1
    with pytest.raises(ObjectStorageError):
        await store.stat(str(staging[0].relative_to(tmp_path)))
    os.utime(staging[0], (time.time() - 120, time.time() - 120))
    assert await store.cleanup_staging(older_than_seconds=60) == 0
    release.set()
    await task
    assert await read_bounded(store, 'revision/original', max_bytes=9) == b'firstlast'
    assert not list(tmp_path.rglob('.woobe-staging-*'))


async def test_interruption_cancellation_disk_full_and_hash_failure_preserve_old_content(tmp_path, monkeypatch):
    store = LocalObjectStorage(tmp_path)
    await put(store, 'original', b'old')

    async def interrupted():
        yield b'new'
        raise ConnectionError('input disconnected')

    with pytest.raises(ObjectStorageError) as interruption:
        await store.put('original', interrupted(), size_bytes=3,
            sha256=hashlib.sha256(b'new').hexdigest(), content_type='text/plain', replace=True)
    assert interruption.value.code == 'unavailable'
    assert await read_bounded(store, 'original', max_bytes=3) == b'old'

    async def waiting():
        yield b'new'
        await asyncio.Event().wait()

    task = asyncio.create_task(store.put('original', waiting(), size_bytes=3,
        sha256=hashlib.sha256(b'new').hexdigest(), content_type='text/plain', replace=True))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await read_bounded(store, 'original', max_bytes=3) == b'old'

    def disk_full(stream, chunk):
        raise OSError(errno.ENOSPC, 'injected disk full')

    with monkeypatch.context() as patch:
        patch.setattr(store, '_write_bytes', disk_full)
        with pytest.raises(ObjectStorageError) as failure:
            await put(store, 'original', b'new', replace=True)
        assert failure.value.code == 'unavailable'
    with pytest.raises(ObjectStorageError):
        await store.put('original', chunks(b'new'), size_bytes=3, sha256='0' * 64,
                         content_type='text/plain', replace=True)
    assert await read_bounded(store, 'original', max_bytes=3) == b'old'
    assert not list(tmp_path.rglob('.woobe-staging-*'))


async def test_verified_ack_loss_and_simultaneous_immutable_writes_are_reconciled(tmp_path, monkeypatch):
    store = LocalObjectStorage(tmp_path)
    with monkeypatch.context() as patch:
        def lose_metadata(*args, **kwargs):
            raise OSError('injected metadata acknowledgement loss')
        patch.setattr(store, '_write_metadata', lose_metadata)
        with pytest.raises(ObjectStorageError):
            await put(store, 'lost-ack', b'complete')
    receipt = await put(store, 'lost-ack', b'complete')
    assert await store.stat('lost-ack') == receipt
    assert await put(store, 'lost-ack', b'complete') == receipt
    results = await asyncio.gather(put(store, 'race', b'left'), put(store, 'race', b'right'),
                                    return_exceptions=True)
    assert sum(isinstance(value, ObjectMetadata) for value in results) == 1
    assert sum(isinstance(value, ObjectStorageError) and value.code == 'conflict' for value in results) == 1
    assert not list(tmp_path.rglob('.woobe-staging-*'))


async def test_cancellation_during_threaded_acquisition_closes_owned_resources(tmp_path, monkeypatch):
    store = LocalObjectStorage(tmp_path)
    entered, release = threading.Event(), threading.Event()
    resources = []
    original = store._prepare

    def delayed(key):
        resource = original(key)
        resources.append(resource)
        entered.set()
        release.wait(2)
        return resource

    monkeypatch.setattr(store, '_prepare', delayed)
    task = asyncio.create_task(put(store, 'cancelled', b'data'))
    assert await asyncio.to_thread(entered.wait, 2)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert resources[0][0].closed
    assert not (tmp_path / 'cancelled').exists()
    assert not list(tmp_path.rglob('.woobe-staging-*'))


async def test_corrupted_metadata_is_a_safe_integrity_failure(tmp_path):
    store = LocalObjectStorage(tmp_path)
    await put(store, 'safe', b'original')
    (tmp_path / store._metadata_key('safe')).write_text('{broken')
    with pytest.raises(ObjectStorageError) as failure:
        await store.stat('safe')
    assert failure.value.code == 'integrity'
    assert (tmp_path / 'safe').read_bytes() == b'original'


async def test_readers_cannot_observe_the_exclusive_link_promotion_window(tmp_path, monkeypatch):
    store = LocalObjectStorage(tmp_path)
    linked, release, reading = threading.Event(), threading.Event(), threading.Event()
    link = os.link
    open_read = store._open_read

    def slow_link(source, target, **kwargs):
        result = link(source, target, **kwargs)
        if target == 'race':
            linked.set()
            release.wait(2)
        return result

    def observe_read(key):
        if key == 'race':
            reading.set()
        return open_read(key)

    monkeypatch.setattr(os, 'link', slow_link)
    monkeypatch.setattr(store, '_open_read', observe_read)
    writer = asyncio.create_task(put(store, 'race', b'data'))
    assert await asyncio.to_thread(linked.wait, 2)
    reader = asyncio.create_task(read_bounded(store, 'race', max_bytes=4))
    assert await asyncio.to_thread(reading.wait, 2)
    await asyncio.sleep(0.02)
    finished_before_promotion = reader.done()
    release.set()
    await writer
    assert await reader == b'data'
    assert not finished_before_promotion


@pytest.mark.parametrize('key', ['../outside', '/absolute', 'a//b', 'a/./b', 'a\\b',
                                 'ação', 'CON', 'a/NUL.txt', 'a/trailing.',
                                 '.woobe-object-metadata/private.json'])
async def test_nonportable_ambiguous_or_private_physical_keys_are_denied(tmp_path, key):
    with pytest.raises(ObjectStorageError) as failure:
        await put(LocalObjectStorage(tmp_path), key, b'bytes')
    assert failure.value.code == 'invalid_key'


async def test_symlinks_hardlinks_and_invalid_ranges_never_expose_other_files(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    root = tmp_path / 'objects'
    root.mkdir()
    (root / 'linked').symlink_to(outside, target_is_directory=True)
    store = LocalObjectStorage(root)
    with pytest.raises(ObjectStorageError):
        await put(store, 'linked/original', b'not allowed')
    assert not list(outside.iterdir())
    await put(store, 'safe', b'original')
    os.link(root / 'safe', root / 'hardlink')
    with pytest.raises(ObjectStorageError):
        await read_bounded(store, 'hardlink', max_bytes=8)
    os.unlink(root / 'hardlink')
    for start, end in ((-1, 2), (4, 3), (0, 100), (100, None)):
        with pytest.raises(ObjectStorageError) as failure:
            await anext(store.open('safe', start=start, end=end))
        assert failure.value.code == 'range'


async def test_real_process_crash_leaves_only_unpublished_collectable_staging(tmp_path):
    source = Path(__file__).resolve().parents[3] / 'packages/woobe-core/src'
    script = '''import asyncio,hashlib,os,sys
from shared.infra.object_storage.local import LocalObjectStorage
async def chunks():
    yield b'data'
    os._exit(19)
asyncio.run(LocalObjectStorage(sys.argv[1]).put('revision/original',chunks(),size_bytes=4,sha256=hashlib.sha256(b'data').hexdigest(),content_type='text/plain'))
'''
    result = await asyncio.to_thread(subprocess.run, [sys.executable, '-c', script, str(tmp_path)],
                                      env={'PATH': os.environ['PATH'], 'PYTHONPATH': str(source)})
    assert result.returncode == 19
    assert not (tmp_path / 'revision/original').exists()
    staging = list(tmp_path.rglob('.woobe-staging-*'))
    assert len(staging) == 1
    os.utime(staging[0], (time.time() - 120, time.time() - 120))
    assert await LocalObjectStorage(tmp_path).cleanup_staging(older_than_seconds=60) == 1
    assert not list(tmp_path.rglob('.woobe-staging-*'))


async def test_large_upload_python_heap_is_bounded(tmp_path):
    store = LocalObjectStorage(tmp_path)
    chunk = b'x' * 65_536
    count = 1024
    digest = hashlib.sha256()
    for _ in range(count):
        digest.update(chunk)

    async def generated():
        for _ in range(count):
            yield chunk

    tracemalloc.start()
    try:
        await store.put('large', generated(), size_bytes=count * len(chunk),
                         sha256=digest.hexdigest(), content_type='application/octet-stream')
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    print(f'stream_size_bytes={count * len(chunk)} python_heap_peak_bytes={peak}')
    assert peak < 8 * 1024 * 1024
    assert (await store.stat('large')).sha256 == digest.hexdigest()


def test_scratch_is_private_per_operation_and_object_keys_ignore_logical_names():
    with artifact_scratch('job') as first, artifact_scratch('job') as second:
        assert first != second and first.stat().st_mode & 0o077 == 0
        (first / 'scratch').write_text('temporary')
    assert not first.exists() and not second.exists()
    with pytest.raises(ValueError):
        with artifact_scratch('../escape'):
            pytest.fail('Unsafe scratch was created')
    key = artifact_object_key(Scope('project', 'staging'), 'workspace', ArtifactRef('artifact', 'revision'))
    assert key == 'projects/project/environments/staging/artifact-workspaces/workspace/artifacts/artifact/revisions/revision/original'
