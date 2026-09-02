from typing import Protocol
from uuid import UUID


class ProjectLookup(Protocol):
    async def exists(self, project_id: UUID) -> bool: ...
