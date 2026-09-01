from collections.abc import Awaitable, Callable
from uuid import UUID

RuntimeEnvironmentGuard = Callable[[UUID, UUID, str], Awaitable[None]]
