from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from copy import deepcopy
from typing import Any
from uuid import UUID

from modules.agent.application.tool_templates import (
    collect_project_environment_keys,
    resolve_tool_templates,
)

ProjectEnvironmentResolver = Callable[..., Awaitable[Mapping[str, str]]]


async def materialize_mcp_connection_config(
    config: Mapping[str, Any],
    *,
    project_id: UUID,
    resolver: ProjectEnvironmentResolver | None,
    environment: str = "draft",
) -> dict[str, Any]:
    """Materialize only MCP connection fields for control-plane discovery.

    MCP discovery has no Run External Context. Project Environment is therefore
    resolved from the control-plane environment (Draft by default), while the
    persisted Tool config remains templated for runtime materialization.
    """

    raw = dict(config or {})
    server = deepcopy(raw.get("server") or {})
    connection: dict[str, Any] = {
        "server": server,
        "server_headers": deepcopy(raw.get("server_headers") or []),
    }

    keys = collect_project_environment_keys(connection)
    if not keys:
        return connection
    if resolver is None:
        return connection

    values = await resolver(
        project_id=project_id,
        environment=environment,
        keys=keys,
    )
    return resolve_tool_templates(
        connection,
        external_context={},
        project_environment=values,
    )


__all__ = [
    "ProjectEnvironmentResolver",
    "materialize_mcp_connection_config",
]
