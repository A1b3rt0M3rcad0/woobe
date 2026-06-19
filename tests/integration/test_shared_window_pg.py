from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.infra.errors import RateLimitError
from shared.security.rate_limit import LoginRateLimiter


@pytest.mark.asyncio
async def test_window_is_shared_between_instances() -> None:
    engine = create_engine(Settings.model_validate({}))
    factory = create_session_factory(engine)
    subject = f"window-{uuid4()}"
    first = LoginRateLimiter(
        session_factory=factory,
        max_attempts=1,
        window_seconds=60,
    )
    second = LoginRateLimiter(
        session_factory=factory,
        max_attempts=1,
        window_seconds=60,
    )

    try:
        results = await asyncio.gather(
            first.consume(subject),
            second.consume(subject),
            return_exceptions=True,
        )
        assert sum(result is None for result in results) == 1
        failures = [result for result in results if isinstance(result, Exception)]
        assert len(failures) == 1
        assert isinstance(failures[0], RateLimitError)
    finally:
        await engine.dispose()
