from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.errors import RateLimitError
from shared.security.rate_limit import ApiKeyConcurrencyLimiter


@pytest.mark.asyncio
async def test_lease_is_shared_and_cross_instance_release_works() -> None:
    engine = create_engine(Settings.model_validate({}))
    factory = create_session_factory(engine)
    subject = f"lease-{uuid4()}"
    first = ApiKeyConcurrencyLimiter(
        session_factory=factory,
        max_concurrency=1,
        lease_ttl_seconds=60,
    )
    second = ApiKeyConcurrencyLimiter(
        session_factory=factory,
        max_concurrency=1,
        lease_ttl_seconds=60,
    )
    active: list[UUID] = []

    try:
        results = await asyncio.gather(
            first.acquire(subject),
            second.acquire(subject),
            return_exceptions=True,
        )
        active = [result for result in results if isinstance(result, UUID)]
        failures = [result for result in results if isinstance(result, Exception)]
        assert len(active) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], RateLimitError)

        await second.release(active.pop())
        active.append(await second.acquire(subject))
    finally:
        for lease_id in active:
            await first.release(lease_id)
        await engine.dispose()
