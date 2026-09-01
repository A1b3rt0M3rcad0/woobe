from __future__ import annotations

from typing import Any


class AgentRuntimeEnvironmentGuard:
    """Compatibility delegate.

    Environment validation is part of the Agent Run Acceptance transaction so a
    standalone execution does not pay an additional database boundary.
    """

    def __init__(
        self,
        delegate: Any,
        transactions: Any = None,
        *,
        default_environment: str = "production",
    ) -> None:
        del transactions, default_environment
        self._delegate = delegate

    async def execute(self, input_dto: Any) -> Any:
        return await self._delegate.execute(input_dto)
