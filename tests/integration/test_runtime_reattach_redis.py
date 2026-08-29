from __future__ import annotations

import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from shared.infra.redis_execution_state import RedisExecutionStateStore
from shared.runtime_reattach import RuntimeStreamReader


@pytest.mark.asyncio
async def test_real_redis_reattach_folds_projection_to_high_watermark_then_tails_live() -> None:
    redis_url = os.environ.get("WOOBE_REDIS_URL")
    assert redis_url, "integration runtime must provide WOOBE_REDIS_URL"

    client = Redis.from_url(redis_url, decode_responses=True)
    prefix = f"woobe:test:reattach:{uuid4()}"
    store = RedisExecutionStateStore(client, key_prefix=prefix)
    run_id = uuid4()
    state_key = f"{prefix}:run:{run_id}"
    events_key = f"{state_key}:events"
    lease_key = f"{state_key}:lease"

    async def durable_fallback():
        return {"status": "completed", "output": "durable fallback", "result": {"answer": "durable fallback"}}

    try:
        assert await client.ping() is True
        await store.create(run_id, {"status": "running"}, ttl_seconds=60)
        for sequence in range(1, 132):
            await store.append_event(
                run_id,
                "token",
                {"content": f"{sequence},", "visibility": "assistant", "channel": "final"},
            )

        await store.update(
            run_id,
            {
                "runtime_projection": {
                    "run_id": str(run_id),
                    "kind": "AGENT",
                    "status": "running",
                    "sequence": 125,
                    "output": "".join(f"{value}," for value in range(1, 126)),
                    "activity": None,
                    "active_tools": [],
                    "active_agents": [],
                    "completed_agents": [],
                    "current_route": None,
                    "usage": {},
                    "result": None,
                }
            },
        )

        reader = RuntimeStreamReader(store, block_ms=100)
        stream = reader.stream(run_id, "agent", durable_fallback=durable_fallback)

        state = await anext(stream)
        assert state.event_type == "run.state"
        assert state.sequence == 131
        assert state.data["output"].endswith("126,127,128,129,130,131,")

        await store.append_event(
            run_id,
            "token",
            {"content": "132,", "visibility": "assistant", "channel": "final"},
        )
        live = await anext(stream)
        assert live.event_type == "token"
        assert live.sequence == 132
        assert live.data["content"] == "132,"
        await stream.aclose()
    finally:
        await client.delete(state_key, events_key, lease_key)
        await client.aclose()


@pytest.mark.asyncio
async def test_real_redis_supports_two_independent_run_observers() -> None:
    redis_url = os.environ.get("WOOBE_REDIS_URL")
    assert redis_url, "integration runtime must provide WOOBE_REDIS_URL"

    client = Redis.from_url(redis_url, decode_responses=True)
    prefix = f"woobe:test:observers:{uuid4()}"
    store = RedisExecutionStateStore(client, key_prefix=prefix)
    run_id = uuid4()
    state_key = f"{prefix}:run:{run_id}"
    events_key = f"{state_key}:events"
    lease_key = f"{state_key}:lease"

    async def fallback():
        return {"status": "running", "output": ""}

    try:
        await store.create(run_id, {"status": "running"}, ttl_seconds=60)
        await store.append_event(run_id, "token", {"content": "one"})

        stream_a = RuntimeStreamReader(store, block_ms=100).stream(run_id, "agent", durable_fallback=fallback)
        stream_b = RuntimeStreamReader(store, block_ms=100).stream(run_id, "agent", durable_fallback=fallback)
        assert (await anext(stream_a)).sequence == 1
        assert (await anext(stream_b)).sequence == 1

        await store.append_event(run_id, "token", {"content": "two"})
        event_a = await anext(stream_a)
        event_b = await anext(stream_b)
        assert event_a.sequence == 2
        assert event_b.sequence == 2
        assert event_a.data["content"] == "two"
        assert event_b.data["content"] == "two"

        await stream_a.aclose()
        await stream_b.aclose()
    finally:
        await client.delete(state_key, events_key, lease_key)
        await client.aclose()


@pytest.mark.asyncio
async def test_real_redis_preserves_cancel_request_while_runtime_events_continue() -> None:
    redis_url = os.environ.get("WOOBE_REDIS_URL")
    assert redis_url, "integration runtime must provide WOOBE_REDIS_URL"

    client = Redis.from_url(redis_url, decode_responses=True)
    prefix = f"woobe:test:cancel:{uuid4()}"
    store = RedisExecutionStateStore(client, key_prefix=prefix)
    run_id = uuid4()

    try:
        await store.create(run_id, {"status": "running", "phase": "llm"}, ttl_seconds=60)
        assert await store.is_cancel_requested(run_id) is False

        await store.request_cancel(run_id)
        await store.append_event(
            run_id,
            "token",
            {"content": "partial", "visibility": "assistant", "channel": "final"},
        )
        await store.update(run_id, {"phase": "provider_wait"})

        hot = await store.get(run_id)
        assert hot is not None
        assert hot["cancel_requested"] is True
        assert hot["event_sequence"] == 1
        assert await store.is_cancel_requested(run_id) is True
    finally:
        await store.delete(run_id)
        await client.aclose()


@pytest.mark.asyncio
async def test_real_redis_loss_after_durable_cancelled_terminal_falls_back_without_losing_partial() -> None:
    redis_url = os.environ.get("WOOBE_REDIS_URL")
    assert redis_url, "integration runtime must provide WOOBE_REDIS_URL"

    client = Redis.from_url(redis_url, decode_responses=True)
    prefix = f"woobe:test:durable-cancel:{uuid4()}"
    store = RedisExecutionStateStore(client, key_prefix=prefix)
    run_id = uuid4()

    durable = {
        "status": "cancelled",
        "output": "durable partial",
        "result": {"answer": "durable partial", "partial": True, "cancelled": True},
    }

    async def durable_fallback():
        return durable

    try:
        await store.create(run_id, {"status": "running"}, ttl_seconds=60)
        await store.request_cancel(run_id)
        await store.delete(run_id)

        stream = RuntimeStreamReader(store, block_ms=100).stream(
            run_id,
            "agent",
            durable_fallback=durable_fallback,
        )
        state = await anext(stream)

        assert state.event_type == "run.state"
        assert state.sequence is None
        assert state.data["status"] == "cancelled"
        assert state.data["output"] == "durable partial"
        assert state.data["realtime_available"] is False

        with pytest.raises(StopAsyncIteration):
            await anext(stream)
    finally:
        await store.delete(run_id)
        await client.aclose()
