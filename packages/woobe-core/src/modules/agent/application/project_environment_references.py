from __future__ import annotations

from uuid import UUID

from modules.agent.application.interfaces.repositories import ToolRepository
from modules.agent.domain.tool_project_environment import (
    collect_tool_project_environment_keys,
)


async def project_environment_tool_usage(
    repo: ToolRepository,
    *,
    project_id: UUID,
) -> dict[str, list[dict[str, str]]]:
    usage: dict[str, list[dict[str, str]]] = {}
    for tool in await repo.list_by_project(project_id):
        reference = {
            "id": str(tool.id),
            "name": tool.name,
        }
        for key in collect_tool_project_environment_keys(tool.config):
            usage.setdefault(key, []).append(reference)
    return usage


__all__ = [
    "collect_tool_project_environment_keys",
    "project_environment_tool_usage",
]
