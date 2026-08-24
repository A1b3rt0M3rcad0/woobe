from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.contracts.execution_state import ExecutionStateStore
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.infra.redis_execution_state import RedisExecutionStateStore


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
