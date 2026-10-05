from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


class ApiKeyDelegationPolicy(Protocol):
    async def validate(
        self,
        *,
        actor_key_id: UUID,
        project_id: UUID,
        scopes: list[str],
        conditions: dict[str, Any],
        expires_at: datetime | None,
    ) -> None: ...
