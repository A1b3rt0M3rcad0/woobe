from __future__ import annotations

from modules.metering.application.dtos.project_usage import (
    ProjectUsageOutput,
    ProjectUsageQuery,
)
from modules.metering.application.ports.project_usage_reader import ProjectUsageReader


class GetProjectUsageUseCase:
    def __init__(self, reader: ProjectUsageReader) -> None:
        self._reader = reader

    async def execute(self, query: ProjectUsageQuery) -> ProjectUsageOutput:
        result = await self._reader.fetch(query)
        return ProjectUsageOutput.model_validate(result)
