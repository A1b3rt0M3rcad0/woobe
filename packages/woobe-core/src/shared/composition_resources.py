from __future__ import annotations

from pymongo import AsyncMongoClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.contracts.execution_state import ExecutionStateStore
from shared.contracts.run_event_buffer import RunEventBufferPort
from shared.contracts.run_event_journal import RunEventJournalPort
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.infra.mongodb_run_event_journal import MongoDBRunEventJournal
from shared.infra.redis_execution_state import RedisExecutionStateStore
from shared.infra.redis_run_event_buffer import RedisRunEventBuffer
from shared.runtime.durability import RunDurabilityBarrier


SETTINGS: Settings = Settings(service_role="api")
DATABASE_ENGINE: AsyncEngine = create_engine(SETTINGS)
SESSION_FACTORY: async_sessionmaker[AsyncSession] = create_session_factory(DATABASE_ENGINE)

REDIS_CLIENT: Redis | None = None
if SETTINGS.redis_url:
    REDIS_CLIENT = Redis.from_url(
        SETTINGS.redis_url,
        decode_responses=True,
        socket_connect_timeout=SETTINGS.redis_connect_timeout_seconds,
        socket_timeout=SETTINGS.redis_connect_timeout_seconds,
        health_check_interval=30,
    )

if REDIS_CLIENT is not None:
    EXECUTION_STATE_STORE: ExecutionStateStore = RedisExecutionStateStore(REDIS_CLIENT)
else:
    # Tests and explicit no-Redis development remain importable. Runtime deployments
    # should provide WOOBE_REDIS_URL; the Community compose does so by default.
    EXECUTION_STATE_STORE = InMemoryExecutionStateStore()

MONGO_CLIENT: AsyncMongoClient | None = None
RUN_EVENT_JOURNAL: RunEventJournalPort | None = None
if SETTINGS.mongodb_url:
    MONGO_CLIENT = AsyncMongoClient(
        SETTINGS.mongodb_url,
        serverSelectionTimeoutMS=max(
            100,
            int(SETTINGS.redis_connect_timeout_seconds * 1000),
        ),
    )
    RUN_EVENT_JOURNAL = MongoDBRunEventJournal(
        MONGO_CLIENT,
        SETTINGS.mongodb_database,
    )

RUN_EVENT_BUFFER: RunEventBufferPort | None = None
if REDIS_CLIENT is not None:
    RUN_EVENT_BUFFER = RedisRunEventBuffer(
        REDIS_CLIENT,
        stream_key=SETTINGS.run_event_redis_stream,
        dead_letter_key=SETTINGS.run_event_dead_letter_stream,
    )

RUN_DURABILITY_BARRIER: RunDurabilityBarrier | None = None
if RUN_EVENT_JOURNAL is not None:
    RUN_DURABILITY_BARRIER = RunDurabilityBarrier(
        RUN_EVENT_JOURNAL,
        timeout_seconds=SETTINGS.run_event_durability_timeout_seconds,
    )


def durable_run_journal_ready() -> bool:
    """Return whether event-journal mode has all mandatory runtime adapters."""

    return RUN_EVENT_BUFFER is not None and RUN_EVENT_JOURNAL is not None
