from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class ProjectRunsReader(Protocol):
    async def fetch(
        self,
        *,
        project_id: UUID,
        network_id: UUID | None,
        limit: int,
    ) -> dict[str, Any]: ...
