from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class ProjectAccessRepository(ABC):
    @abstractmethod
    async def require_user_access(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
    ) -> None: ...
