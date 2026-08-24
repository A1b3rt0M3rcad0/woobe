from __future__ import annotations

import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from shared.infra.redis_execution_state import RedisExecutionStateStore


@pytest.mark.asyncio
async def test_redis_execution_state_supports_cancel_leases_generation_events_and_ttl() -> None:
    redis_url = os.environ.get("WOOBE_REDIS_URL")
    assert redis_url, "integration runtime must provide WOOBE_REDIS_URL"

    client = Redis.from_url(redis_url, decode_responses=True)
    prefix = f"woobe:test:execution:{uuid4()}"
    store = RedisExecutionStateStore(client, key_prefix=prefix)
    run_id = uuid4()
    state_key = f"{prefix}:run:{run_id}"
    events_key = f"{state_key}:events"
    lease_key = f"{state_key}:lease"

    try:
        assert await client.ping() is True

        await store.create(
            run_id,
            {"status": "running", "phase": "llm", "counter": 0},
            ttl_seconds=60,
        )
        state = await store.get(run_id)
        assert state is not None
        assert state["status"] == "running"
        assert state["cancel_requested"] is False
        assert state["lease_generation"] == 0

        await store.request_cancel(run_id)
        assert await store.is_cancel_requested(run_id) is True

        first = await store.acquire_lease(
            run_id,
            worker_id="worker-a",
            ttl_seconds=30,
        )
        assert first is not None
        assert first.owner == "worker-a"
        assert first.generation == 1

        blocked = await store.acquire_lease(
            run_id,
            worker_id="worker-b",
            ttl_seconds=30,
        )
        assert blocked is None
        assert await store.renew_lease(
            run_id,
            worker_id="worker-b",
            ttl_seconds=30,
        ) is False
        assert await store.renew_lease(
            run_id,
            worker_id="worker-a",
            ttl_seconds=30,
        ) is True

        # Simulate lease expiry without sleeping. The next owner must advance the
        # generation so a stale worker cannot finalize as the current owner.
        await client.delete(lease_key)
        second = await store.acquire_lease(
            run_id,
            worker_id="worker-b",
            ttl_seconds=30,
        )
        assert second is not None
        assert second.owner == "worker-b"
        assert second.generation == 2

        assert await store.increment(run_id, "counter") == 1
        assert await store.increment(run_id, "counter", amount=2) == 3

        event_id = await store.append_event(
            run_id,
            "agent.run.progress",
            {"step": 1},
        )
        assert event_id is not None
        assert await client.xlen(events_key) == 1

        await store.expire(run_id, ttl_seconds=2)
        state_ttl = await client.ttl(state_key)
        events_ttl = await client.ttl(events_key)
        lease_ttl = await client.ttl(lease_key)
        assert 0 < state_ttl <= 2
        assert 0 < events_ttl <= 2
        assert 0 < lease_ttl <= 2

        await store.delete(run_id)
        assert await store.get(run_id) is None
        assert await client.exists(events_key) == 0
        assert await client.exists(lease_key) == 0
    finally:
        await client.delete(state_key, events_key, lease_key)
        await client.aclose()
