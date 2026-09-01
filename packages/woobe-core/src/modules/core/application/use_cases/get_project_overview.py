from __future__ import annotations

from datetime import UTC, datetime

from modules.core.application.dtos.project_overview import (
    ProjectOverviewOutput,
    ProjectOverviewQuery,
)
from modules.core.application.ports.project_overview_reader import ProjectOverviewReader


class GetProjectOverviewUseCase:
    def __init__(self, reader: ProjectOverviewReader) -> None:
        self._reader = reader

    async def execute(self, query: ProjectOverviewQuery) -> ProjectOverviewOutput:
        assert query.from_ is not None
        assert query.to is not None
        assert query.bucket is not None

        sections = await self._reader.fetch(
            project_id=query.project_id,
            start=query.from_,
            end=query.to,
            bucket=query.bucket,
            environment=query.environment,
            recent_limit=query.recent_limit,
        )
        return ProjectOverviewOutput.model_validate(
            {
                "project_id": query.project_id,
                "generated_at": datetime.now(UTC),
                "from": query.from_,
                "to": query.to,
                "bucket": query.bucket,
                "environment": query.environment,
                **sections,
            }
        )
