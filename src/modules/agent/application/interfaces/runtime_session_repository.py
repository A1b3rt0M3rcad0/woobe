from typing import Protocol
from uuid import UUID

from modules.agent.domain.entities import Session
from shared.contracts.pagination import CursorPage


class RuntimeSessionRepository(Protocol):
    async def create(self, session: Session) -> Session: ...

    async def paginate_by_agent_environment(
        self,
        project_id: UUID,
        agent_id: UUID,
        environment: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> CursorPage[tuple[Session, int]]: ...
