from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class AgentRunListingUseCase(Protocol):
    async def execute(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID | None = None,
        environment: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...
