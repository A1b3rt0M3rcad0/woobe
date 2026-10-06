from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator

from modules.agent.domain.mcp_permissions import (
    MCP_PERMISSION_ALLOW,
    MCP_PERMISSION_DENY,
    MCP_PERMISSION_MODES,
    MCP_PERMISSION_REVIEW,
)

McpPermissionMode = Literal["allow", "deny", "review"]


class McpToolPermissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    remote_tool_name: str = Field(..., min_length=1, max_length=256)
    mode: McpPermissionMode
    risk_level: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("remote_tool_name", "risk_level")
    @classmethod
    def reject_blank(cls, value):
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("MCP permission strings must be nonblank without surrounding whitespace")
        return value


class UpdateMcpToolPermissionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_id: UUID
    permissions: list[McpToolPermissionInput] = Field(min_length=1, max_length=1000)

    @field_validator("permissions")
    @classmethod
    def unique_names(cls, values):
        if len({item.remote_tool_name for item in values}) != len(values):
            raise ValueError("MCP remote tool names must be unique")
        return values


class BulkUpdateMcpToolPermissionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_id: UUID
    mode: McpPermissionMode
    risk_level: str | None = Field(default=None, min_length=1, max_length=256)

    @field_validator("risk_level")
    @classmethod
    def reject_blank(cls, value):
        return McpToolPermissionInput.reject_blank(value)


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
