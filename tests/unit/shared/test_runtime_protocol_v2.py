import asyncio
import json
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from modules.agent.infra.execution.runtime_streaming import RuntimeStreamChannel
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.infra.redis_execution_state import RedisExecutionStateStore
from shared.runtime.contracts import RunKind, RunReference, SemanticRuntimeEvent, RuntimeControlFrame
from shared.runtime.observer import RuntimeObserver
from shared.runtime.publisher import RuntimeEventPublisher
from shared.runtime.sse import format_sse_frame


def wire(frame):
    return json.loads(next(line[6:] for line in format_sse_frame(frame).splitlines() if line.startswith('data: ')))


def test_semantic_serializer_has_one_complete_envelope():
    event = SemanticRuntimeEvent(event_type='token', data={'content': 'hello'},
        run_id=uuid4(), session_id=uuid4(), run_kind=RunKind.AGENT, sequence=1)
    data = wire(event)
    assert set(data) == {'protocol_version', 'event_id', 'run_id', 'session_id', 'run_kind', 'sequence', 'type', 'occurred_at', 'payload'}
    assert data['protocol_version'] == 2
    assert data['session_id'] == str(event.session_id)
    assert data['payload'] == {'content': 'hello'}
    assert format_sse_frame(event).startswith('id: 1\n')


def test_heartbeat_is_transport_without_order_or_domain_identity():
    assert set(wire(RuntimeControlFrame('heartbeat', {}))) == {'protocol_version', 'type', 'occurred_at'}
    with pytest.raises(ValueError):
        RuntimeControlFrame('heartbeat', {}, sequence=1)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', [RunKind.AGENT, RunKind.NETWORK])
async def test_initial_disconnect_reattach_keeps_identity_and_n_plus_one(kind):
    run_id, session_id = uuid4(), uuid4()
    store = InMemoryExecutionStateStore()
    await store.create(run_id, {'status': 'running', 'session_id': str(session_id)}, ttl_seconds=60)
    observer = RuntimeObserver(store, block_ms=50)
    channel = RuntimeStreamChannel(run_id=run_id, session_id=session_id)
    local = observer.subscribe_local(channel, run_kind=kind)
    stream = local.stream()
    await channel.emit('token', content='first')
    first = await anext(stream)
    await stream.aclose()  # Only detach observation, do not stop execution.
    publisher = RuntimeEventPublisher(store)
    queued = channel.queue.get_nowait()
    await publisher.publish(run_id, kind.value, queued.event_type, queued.payload,
        event_id=queued.event_id, sequence=queued.sequence, occurred_at=queued.occurred_at)
    stored = (await store.list_events_after(run_id, 0))[0]
    assert (first.event_id, first.sequence, first.occurred_at) == (stored.event_id, stored.sequence, stored.occurred_at)
    fallback = AsyncMock(return_value={'session_id': str(session_id), 'status': 'running'})
    reattach = observer.observe(RunReference(run_id, kind), durable_fallback=fallback)
    snapshot = await anext(reattach)
    assert snapshot.sequence == 1
    assert snapshot.session_id == session_id
    assert wire(snapshot)['run_kind'] == kind.value.upper()
    await channel.emit('done', answer='first')
    queued = channel.queue.get_nowait()
    await publisher.publish(run_id, kind.value, queued.event_type, queued.payload,
        event_id=queued.event_id, sequence=queued.sequence, occurred_at=queued.occurred_at)
    terminal = await anext(reattach)
    assert terminal.sequence == 2
    assert terminal.event_id == queued.event_id
    assert terminal.session_id == session_id
    with pytest.raises(StopAsyncIteration):
        await anext(reattach)


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', [0, 1, 3, True])
async def test_store_rejects_duplicate_regressive_or_gapped_sequence(bad):
    store = InMemoryExecutionStateStore()
    run_id = uuid4()
    await store.create(run_id, {}, ttl_seconds=60)
    await store.append_event(run_id, 'token', {}, sequence=1)
    with pytest.raises(ValueError):
        await store.append_event(run_id, 'token', {}, sequence=bad)
    assert len(await store.list_events_after(run_id, 0)) == 1


@pytest.mark.asyncio
async def test_local_first_token_does_not_wait_for_hot_store():
    store = InMemoryExecutionStateStore()
    store.append_event = AsyncMock(side_effect=ConnectionError('offline'))
    channel = RuntimeStreamChannel(run_id=uuid4(), session_id=uuid4())
    local = RuntimeObserver(store).subscribe_local(channel, run_kind=RunKind.AGENT)
    await channel.emit('token', content='available locally')
    stream = local.stream()
    event = await asyncio.wait_for(anext(stream), timeout=0.1)
    assert event.sequence == 1
    assert event.data['content'] == 'available locally'
    assert await RuntimeEventPublisher(store).publish(channel.run_id, 'agent', 'token', event.data,
        sequence=event.sequence, event_id=event.event_id, occurred_at=event.occurred_at) is None
    await channel.emit('done', answer='available locally')
    assert (await anext(stream)).event_type == 'done'
    await stream.aclose()


@pytest.mark.asyncio
async def test_preaccept_error_is_transport_and_not_semantic():
    channel = RuntimeStreamChannel()
    local = RuntimeObserver(InMemoryExecutionStateStore()).subscribe_local(channel, run_kind=RunKind.AGENT)
    await channel.emit('error', message='request rejected')
    stream = local.stream()
    frame = await anext(stream)
    assert isinstance(frame, RuntimeControlFrame)
    assert 'event_id' not in wire(frame)
    await stream.aclose()


def test_redis_event_decode_preserves_identity():
    event_id = str(uuid4())
    event = RedisExecutionStateStore._event('10-1', {'event_id': event_id, 'sequence': '5',
        'type': 'token', 'payload': '{"content":"hi"}', 'at': '2026-09-16T20:00:00Z'})
    assert event.event_id == event_id
    assert event.sequence == 5
    assert event.occurred_at == '2026-09-16T20:00:00Z'
