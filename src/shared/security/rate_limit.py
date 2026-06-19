from collections import defaultdict, deque
from time import monotonic

from shared.infra.errors import RateLimitError


class LoginRateLimiter:
    def __init__(self, *, max_attempts: int, window_seconds: int) -> None:
        if max_attempts <= 0 or window_seconds <= 0:
            raise ValueError("Rate-limit values must be positive")
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def consume(self, key: str) -> None:
        now = monotonic()
        cutoff = now - self._window_seconds
        bucket = self._attempts[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self._max_attempts:
            retry_after = max(1, int(bucket[0] + self._window_seconds - now))
            raise RateLimitError(
                "Too many authentication attempts",
                retry_after=retry_after,
            )
        bucket.append(now)
