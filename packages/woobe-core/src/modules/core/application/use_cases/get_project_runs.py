from __future__ import annotations

from typing import Any

from modules.core.application.dtos.project_runs import ProjectRunsQuery
from modules.core.application.ports.project_runs_reader import ProjectRunsReader


class GetProjectRunsUseCase:
    def __init__(self, reader: ProjectRunsReader) -> None:
        self._reader = reader

    async def execute(self, query: ProjectRunsQuery) -> dict[str, Any]:
        return await self._reader.fetch(
            project_id=query.project_id,
            network_id=query.network_id,
            limit=query.limit,
        )
