from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import ceil
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.infra.errors import RateLimitError

_default_session_factory: async_sessionmaker[AsyncSession] | None = None


def configure_rate_limit_session_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    global _default_session_factory
    _default_session_factory = session_factory


def _session_factory(
    explicit: async_sessionmaker[AsyncSession] | None,
) -> async_sessionmaker[AsyncSession]:
    factory = explicit or _default_session_factory
    if factory is None:
        raise RuntimeError("Shared rate-limit session factory is not configured")
    return factory


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def _lock_subject(
    session: AsyncSession,
    *,
    namespace: str,
    subject_key: str,
) -> None:
    await session.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "hashtextextended(:lock_subject, 0)"
            ")"
        ),
        {"lock_subject": f"{namespace}:{subject_key}"},
    )


class SlidingWindowRateLimiter:
    def __init__(
        self,
        *,
        namespace: str,
        limit: int,
        window_seconds: int,
        message: str,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("Rate-limit values must be positive")
        if not namespace.strip():
            raise ValueError("Rate-limit namespace is required")
        self._explicit_session_factory = session_factory
        self._namespace = namespace
        self._limit = limit
        self._window_seconds = window_seconds
        self._message = message

    async def consume(self, key: str) -> None:
        now = datetime.now(UTC)
        cutoff = now - timedelta(seconds=self._window_seconds)
        session_factory = _session_factory(self._explicit_session_factory)

        async with session_factory() as session:
            async with session.begin():
                await _lock_subject(
                    session,
                    namespace=f"rate:{self._namespace}",
                    subject_key=key,
                )
                await session.execute(
                    text(
                        """
                        DELETE FROM core.security_rate_limit_events
                        WHERE namespace = :namespace
                          AND subject_key = :subject_key
                          AND occurred_at <= :cutoff
                        """
                    ),
                    {
                        "namespace": self._namespace,
                        "subject_key": key,
                        "cutoff": cutoff,
                    },
                )
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*) AS event_count,
                               MIN(occurred_at) AS oldest_event
                        FROM core.security_rate_limit_events
                        WHERE namespace = :namespace
                          AND subject_key = :subject_key
                          AND occurred_at > :cutoff
                        """
                    ),
                    {
                        "namespace": self._namespace,
                        "subject_key": key,
                        "cutoff": cutoff,
                    },
                )
                row = result.one()
                event_count = int(row.event_count)
                if event_count >= self._limit:
                    oldest_event = row.oldest_event
                    retry_after = 1
                    if oldest_event is not None:
                        retry_after = max(
                            1,
                            ceil(
                                (
                                    _as_utc(oldest_event)
                                    + timedelta(seconds=self._window_seconds)
                                    - now
                                ).total_seconds()
                            ),
                        )
                    raise RateLimitError(
                        self._message,
                        retry_after=retry_after,
                    )

                await session.execute(
                    text(
                        """
                        INSERT INTO core.security_rate_limit_events (
                            namespace,
                            subject_key,
                            occurred_at
                        ) VALUES (
                            :namespace,
                            :subject_key,
                            :occurred_at
                        )
                        """
                    ),
                    {
                        "namespace": self._namespace,
                        "subject_key": key,
                        "occurred_at": now,
                    },
                )


class LoginRateLimiter(SlidingWindowRateLimiter):
    def __init__(
        self,
        *,
        max_attempts: int,
        window_seconds: int,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        super().__init__(
            session_factory=session_factory,
            namespace="login",
            limit=max_attempts,
            window_seconds=window_seconds,
            message="Too many authentication attempts",
        )


class ApiKeyRequestLimiter(SlidingWindowRateLimiter):
    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: int,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        super().__init__(
            session_factory=session_factory,
            namespace="api_key_request",
            limit=max_requests,
            window_seconds=window_seconds,
            message="API key rate limit exceeded",
        )


class ApiKeyConcurrencyLimiter:
    def __init__(
        self,
        *,
        max_concurrency: int,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        lease_ttl_seconds: int = 180,
    ) -> None:
        if max_concurrency <= 0:
            raise ValueError("Concurrency limit must be positive")
        if lease_ttl_seconds <= 0:
            raise ValueError("Concurrency lease TTL must be positive")
        self._explicit_session_factory = session_factory
        self._max_concurrency = max_concurrency
        self._lease_ttl_seconds = lease_ttl_seconds
        self._namespace = "api_key_runtime"

    async def acquire(self, key: str) -> UUID:
        now = datetime.now(UTC)
        lease_id = uuid4()
        expires_at = now + timedelta(seconds=self._lease_ttl_seconds)
        session_factory = _session_factory(self._explicit_session_factory)

        async with session_factory() as session:
            async with session.begin():
                await _lock_subject(
                    session,
                    namespace=f"concurrency:{self._namespace}",
                    subject_key=key,
                )
                await session.execute(
                    text(
                        """
                        DELETE FROM core.security_concurrency_leases
                        WHERE namespace = :namespace
                          AND subject_key = :subject_key
                          AND expires_at <= :now
                        """
                    ),
                    {
                        "namespace": self._namespace,
                        "subject_key": key,
                        "now": now,
                    },
                )
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM core.security_concurrency_leases
                        WHERE namespace = :namespace
                          AND subject_key = :subject_key
                          AND expires_at > :now
                        """
                    ),
                    {
                        "namespace": self._namespace,
                        "subject_key": key,
                        "now": now,
                    },
                )
                if int(result.scalar_one()) >= self._max_concurrency:
                    raise RateLimitError(
                        "API key concurrency limit exceeded",
                        retry_after=1,
                    )

                await session.execute(
                    text(
                        """
                        INSERT INTO core.security_concurrency_leases (
                            id,
                            namespace,
                            subject_key,
                            acquired_at,
                            expires_at
                        ) VALUES (
                            :id,
                            :namespace,
                            :subject_key,
                            :acquired_at,
                            :expires_at
                        )
                        """
                    ),
                    {
                        "id": lease_id,
                        "namespace": self._namespace,
                        "subject_key": key,
                        "acquired_at": now,
                        "expires_at": expires_at,
                    },
                )
        return lease_id

    async def release(self, lease_id: UUID) -> None:
        session_factory = _session_factory(self._explicit_session_factory)
        async with session_factory() as session:
            async with session.begin():
                await session.execute(
                    text(
                        """
                        DELETE FROM core.security_concurrency_leases
                        WHERE id = :lease_id
                        """
                    ),
                    {"lease_id": lease_id},
                )
