from __future__ import annotations

import os
from uuid import uuid4

import pytest
from pymongo import AsyncMongoClient
from redis.asyncio import Redis

from shared.infra.mongodb_run_event_journal import MongoDBRunEventJournal
from shared.infra.redis_run_event_buffer import RedisRunEventBuffer
from woobe_workers.runtime.run_event_persistence_worker import RunEventPersistenceWorker


@pytest.mark.anyio
async def test_redis_buffer_is_persisted_to_mongodb_with_contiguous_watermark() -> None:
    redis_url = os.environ.get("WOOBE_REDIS_URL")
    mongodb_url = os.environ.get("WOOBE_MONGODB_URL")
    if not redis_url or not mongodb_url:
        pytest.skip("Redis and MongoDB are required for the Run journal integration test")

    run_id = uuid4()
    namespace = uuid4().hex
    stream_key = f"woobe:test:journal:{namespace}"
    dead_letter_key = f"woobe:test:journal:dead:{namespace}"
    state_prefix = f"woobe:test:journal:run:{namespace}"
    consumer_group = f"woobe-test-journal-{namespace}"
    database_name = f"woobe_test_journal_{namespace}"

    redis = Redis.from_url(redis_url, decode_responses=True)
    mongo = AsyncMongoClient(mongodb_url, serverSelectionTimeoutMS=3000)
    buffer = RedisRunEventBuffer(
        redis,
        stream_key=stream_key,
        dead_letter_key=dead_letter_key,
        state_prefix=state_prefix,
    )
    journal = MongoDBRunEventJournal(mongo, database_name)
    worker = RunEventPersistenceWorker(
        buffer=buffer,
        journal=journal,
        consumer_group=consumer_group,
        consumer_name=f"worker-{namespace}",
    )

    try:
        await redis.ping()
        await mongo.admin.command("ping")
        await journal.ensure_indexes()
        await buffer.ensure_consumer_group(consumer_group)

        first = await buffer.append(
            run_id=run_id,
            run_kind="agent",
            event_type="execution.started",
            metadata={"project_id": str(uuid4()), "attempt": 1},
            payload={"phase": "execution"},
        )
        second = await buffer.append(
            run_id=run_id,
            run_kind="agent",
            event_type="run.completed",
            metadata={"project_id": str(uuid4()), "attempt": 1},
            payload={"status": "completed"},
        )

        buffered = await buffer.read_group(
            group=consumer_group,
            consumer=f"worker-{namespace}",
            count=10,
            block_ms=100,
        )
        assert [event.sequence for event in buffered] == [first.sequence, second.sequence]

        await worker._persist_batch(buffered)

        persisted = await journal.list_events(run_id)
        state = await journal.get_state(run_id)

        assert [event.sequence for event in persisted] == [1, 2]
        assert [event.event_type for event in persisted] == [
            "execution.started",
            "run.completed",
        ]
        assert state is not None
        assert state.durable_sequence == 2
        assert state.terminal_sequence == 2
        assert state.terminal_status == "completed"

        pending = await redis.xpending(stream_key, consumer_group)
        assert int(pending["pending"]) == 0
    finally:
        await mongo.drop_database(database_name)
        await redis.delete(
            stream_key,
            dead_letter_key,
            f"{state_prefix}:{run_id}",
        )
        await redis.aclose()
        await mongo.close()
