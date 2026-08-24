from __future__ import annotations

from uuid import UUID

from modules.agent.application.dtos.mcp_permission_dtos import (
    BulkUpdateMcpToolPermissionsInput,
    McpToolPermissionOutput,
    McpToolPermissionsOutput,
    UpdateMcpToolPermissionsInput,
)
from modules.agent.application.interfaces.mcp_readiness import build_mcp_readiness
from modules.agent.application.interfaces.repositories import ToolRepository
from modules.agent.domain.mcp_permissions import (
    MCP_PERMISSION_ALLOW,
    MCP_PERMISSION_DENY,
    MCP_PERMISSION_MODES,
    MCP_PERMISSION_REVIEW,
    allowed_mcp_discovered_tools,
    default_mcp_permission,
    mcp_tool_permission_mode,
    merge_discovered_tools_with_existing_permissions,
    normalize_discovered_tool,
    normalize_discovered_tools,
    normalize_permission,
)


def write_mcp_readiness(config: dict) -> None:
    config["mcp_readiness"] = build_mcp_readiness(config)


def _permissions_output(
    tool_id: UUID,
    discovered_tools: list[dict],
) -> McpToolPermissionsOutput:
    return McpToolPermissionsOutput(
        tool_id=tool_id,
        permissions=[
            McpToolPermissionOutput(
                name=str(item["name"]),
                mode=normalize_permission(item.get("permission"))["mode"],
                risk_level=normalize_permission(item.get("permission")).get("risk_level"),
            )
            for item in discovered_tools
        ],
    )


class UpdateMcpToolPermissionsUseCase:
    def __init__(self, tool_repo: ToolRepository) -> None:
        self._tool_repo = tool_repo

    async def execute(
        self,
        input_dto: UpdateMcpToolPermissionsInput,
    ) -> McpToolPermissionsOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)
        if tool is None:
            raise ValueError("MCP provider tool not found")
        config = dict(tool.config or {})
        discovered_tools = normalize_discovered_tools(config.get("discovered_tools"))
        by_name = {item["name"]: item for item in discovered_tools}
        for permission in input_dto.permissions:
            item = by_name.get(permission.remote_tool_name)
            if item is None:
                continue
            next_permission = {"mode": permission.mode}
            if permission.risk_level:
                next_permission["risk_level"] = permission.risk_level
            item["permission"] = normalize_permission(next_permission)
        config["discovered_tools"] = discovered_tools
        write_mcp_readiness(config)
        tool.config = config
        await self._tool_repo.update(tool)
        return _permissions_output(tool.id, discovered_tools)


class BulkUpdateMcpToolPermissionsUseCase:
    def __init__(self, tool_repo: ToolRepository) -> None:
        self._tool_repo = tool_repo

    async def execute(
        self,
        input_dto: BulkUpdateMcpToolPermissionsInput,
    ) -> McpToolPermissionsOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)
        if tool is None:
            raise ValueError("MCP provider tool not found")
        config = dict(tool.config or {})
        discovered_tools = normalize_discovered_tools(config.get("discovered_tools"))
        for item in discovered_tools:
            next_permission = {"mode": input_dto.mode}
            if input_dto.risk_level:
                next_permission["risk_level"] = input_dto.risk_level
            elif input_dto.mode == MCP_PERMISSION_REVIEW:
                next_permission["risk_level"] = "unknown"
            item["permission"] = normalize_permission(next_permission)
        config["discovered_tools"] = discovered_tools
        write_mcp_readiness(config)
        tool.config = config
        await self._tool_repo.update(tool)
        return _permissions_output(tool.id, discovered_tools)


__all__ = [
    "BulkUpdateMcpToolPermissionsUseCase",
    "MCP_PERMISSION_ALLOW",
    "MCP_PERMISSION_DENY",
    "MCP_PERMISSION_MODES",
    "MCP_PERMISSION_REVIEW",
    "UpdateMcpToolPermissionsUseCase",
    "allowed_mcp_discovered_tools",
    "default_mcp_permission",
    "mcp_tool_permission_mode",
    "merge_discovered_tools_with_existing_permissions",
    "normalize_discovered_tool",
    "normalize_discovered_tools",
    "normalize_permission",
    "write_mcp_readiness",
]
