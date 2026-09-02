from typing import Protocol
from uuid import UUID

from modules.core.domain.enums import RuntimeTargetType


class RuntimeKeyTargetReader(Protocol):
    async def get_target_project_id(
        self,
        target_type: RuntimeTargetType,
        target_id: UUID,
    ) -> UUID | None: ...
