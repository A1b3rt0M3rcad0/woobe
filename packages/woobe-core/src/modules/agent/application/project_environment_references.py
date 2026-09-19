from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from modules.agent.application.interfaces.repositories import ToolRepository
from modules.agent.application.tool_context_bindings import (
    collect_project_environment_binding_keys,
)
from modules.agent.application.tool_templates import collect_project_environment_keys


def collect_tool_project_environment_keys(
    config: Mapping[str, Any] | None,
) -> set[str]:
    raw = dict(config or {})
    keys = collect_project_environment_keys(raw)
    keys.update(collect_project_environment_binding_keys(raw))
    return keys


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
