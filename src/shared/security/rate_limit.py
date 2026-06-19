from asyncio import Lock
from collections import defaultdict, deque
from time import monotonic

from shared.infra.errors import RateLimitError


class SlidingWindowRateLimiter:
    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        message: str,
    ) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("Rate-limit values must be positive")
        self._limit = limit
        self._window_seconds = window_seconds
        self._message = message
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def consume(self, key: str) -> None:
        now = monotonic()
        cutoff = now - self._window_seconds
        bucket = self._attempts[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self._limit:
            retry_after = max(1, int(bucket[0] + self._window_seconds - now))
            raise RateLimitError(self._message, retry_after=retry_after)
        bucket.append(now)


class LoginRateLimiter(SlidingWindowRateLimiter):
    def __init__(self, *, max_attempts: int, window_seconds: int) -> None:
        super().__init__(
            limit=max_attempts,
            window_seconds=window_seconds,
            message="Too many authentication attempts",
        )


class ApiKeyRequestLimiter(SlidingWindowRateLimiter):
    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        super().__init__(
            limit=max_requests,
            window_seconds=window_seconds,
            message="API key rate limit exceeded",
        )


class ApiKeyConcurrencyLimiter:
    def __init__(self, *, max_concurrency: int) -> None:
        if max_concurrency <= 0:
            raise ValueError("Concurrency limit must be positive")
        self._max_concurrency = max_concurrency
        self._active: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    async def acquire(self, key: str) -> None:
        async with self._lock:
            if self._active[key] >= self._max_concurrency:
                raise RateLimitError(
                    "API key concurrency limit exceeded",
                    retry_after=1,
                )
            self._active[key] += 1

    async def release(self, key: str) -> None:
        async with self._lock:
            active = self._active.get(key, 0)
            if active <= 1:
                self._active.pop(key, None)
            else:
                self._active[key] = active - 1
