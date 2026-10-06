from __future__ import annotations

from typing import Protocol
from uuid import UUID


class ProjectEnvironmentKeyReader(Protocol):
    async def inspect_keys(self, *, project_id: UUID, keys: set[str]) -> dict: ...

    async def require_keys(
        self,
        *,
        project_id: UUID,
        keys: set[str],
    ) -> None: ...


__all__ = ["ProjectEnvironmentKeyReader"]
