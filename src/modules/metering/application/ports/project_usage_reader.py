from __future__ import annotations

from typing import Protocol

from modules.metering.application.dtos.project_usage import ProjectUsageQuery


class ProjectUsageReader(Protocol):
    async def fetch(self, query: ProjectUsageQuery) -> dict: ...
