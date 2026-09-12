from __future__ import annotations

from typing import Any, Protocol

from modules.agent.application.dtos.runtime_dtos import AskOutput


class AgentRunPersistencePort(Protocol):
    """Terminal persistence strategy selected by Agent composition."""

    storage_version: str

    async def complete(self, owner: Any, **kwargs: Any) -> AskOutput: ...

    async def fail(self, owner: Any, **kwargs: Any) -> None: ...

    async def prepare_failure(
        self,
        owner: Any,
        *,
        input_dto: Any,
        error: Exception,
    ) -> bool: ...
