from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from modules.core.application.dtos.project_overview import (
    OverviewBucket,
    OverviewEnvironment,
)


class ProjectOverviewReader(Protocol):
    async def fetch(
        self,
        *,
        project_id: UUID,
        start: datetime,
        end: datetime,
        bucket: OverviewBucket,
        environment: OverviewEnvironment,
        recent_limit: int,
    ) -> dict[str, Any]: ...
