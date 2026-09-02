from typing import Protocol
from uuid import UUID


class AgentAvailability(Protocol):
    async def unavailable_active_agent_ids(
        self,
        *,
        project_id: UUID,
        agent_ids: set[UUID],
    ) -> set[UUID]: ...
