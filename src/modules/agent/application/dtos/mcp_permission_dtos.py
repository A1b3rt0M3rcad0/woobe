from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from modules.agent.domain.mcp_permissions import (
    MCP_PERMISSION_ALLOW,
    MCP_PERMISSION_DENY,
    MCP_PERMISSION_MODES,
    MCP_PERMISSION_REVIEW,
)

McpPermissionMode = Literal["allow", "deny", "review"]


class McpToolPermissionInput(BaseModel):
    remote_tool_name: str = Field(..., min_length=1)
    mode: McpPermissionMode
    risk_level: str | None = None


class UpdateMcpToolPermissionsInput(BaseModel):
    tool_id: UUID
    permissions: list[McpToolPermissionInput]


class BulkUpdateMcpToolPermissionsInput(BaseModel):
    tool_id: UUID
    mode: McpPermissionMode
    risk_level: str | None = None


class McpToolPermissionOutput(BaseModel):
    name: str
    mode: str
    risk_level: str | None = None


class McpToolPermissionsOutput(BaseModel):
    tool_id: UUID
    permissions: list[McpToolPermissionOutput]


__all__ = [
    "BulkUpdateMcpToolPermissionsInput",
    "MCP_PERMISSION_ALLOW",
    "MCP_PERMISSION_DENY",
    "MCP_PERMISSION_MODES",
    "MCP_PERMISSION_REVIEW",
    "McpPermissionMode",
    "McpToolPermissionInput",
    "McpToolPermissionOutput",
    "McpToolPermissionsOutput",
    "UpdateMcpToolPermissionsInput",
]
