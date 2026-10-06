from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class CategoryResolver(Protocol):
    async def resolve_category(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        revision: int | None,
        scope: str,
        transaction: object,
    ) -> dict[str, Any]: ...
