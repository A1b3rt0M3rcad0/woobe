from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from modules.agent.application.tool_types import is_mcp_tool_type
from modules.agent.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType


class HttpHeaderConfig(BaseModel):
    key: str = Field(..., min_length=1)
    value: str = ""
    sensitive: bool | None = None


class HttpAuthConfig(BaseModel):
    type: Literal["none", "api_key", "bearer", "basic"] = "none"
    credentials: list[str] | None = None


class HttpToolConfig(BaseModel):
    protocol: Literal["http"] | None = None
    url: str = ""
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"] = "GET"
    headers: list[HttpHeaderConfig] = Field(default_factory=list)
    body: str | dict[str, Any] | list[Any] | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    auth: HttpAuthConfig | None = None
    timeout_ms: int | None = Field(default=None, ge=1)


class McpServerConfig(BaseModel):
    transport: Literal["streamable_http"] = "streamable_http"
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    headers: list[HttpHeaderConfig] = Field(default_factory=list)
    env_secret_refs: dict[str, str] | None = None
    name: str | None = None


class McpDiscoveredToolConfig(BaseModel):
    name: str = Field(..., min_length=1)
    title: str | None = None
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    permission: dict[str, Any] | None = None


class McpToolConfig(BaseModel):
    protocol: Literal["mcp"] | None = None
    mode: Literal["tool", "server"] = "tool"
    exposure: Literal["single", "all_discovered"] = "single"
    server: McpServerConfig
    tool_name: str | None = None
    server_headers: list[HttpHeaderConfig] = Field(default_factory=list)
    input_schema_source: Literal["discovered", "manual"] = "manual"
    discovered_input_schema: dict[str, Any] | None = None
    discovered_tools: list[McpDiscoveredToolConfig] = Field(default_factory=list)
    discovery_cache_ttl_seconds: int | None = Field(default=None, ge=0)
    timeout_ms: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_transport_target(self) -> "McpToolConfig":
        if not self.server.url:
            raise ValueError("MCP server.url is required for streamable_http transport")
        if self.mode != "server" and self.exposure != "all_discovered" and not self.tool_name:
            raise ValueError("MCP tool_name is required when exposing a single MCP tool")
        return self


class CreateToolInput(BaseModel):
    project_id: UUID
    agent_id: UUID | None = None
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    type: ToolType = ToolType.HTTP
    config: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    timeout_ms: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_protocol_config(self) -> "CreateToolInput":
        if self.config is None:
            return self
        if is_mcp_tool_type(self.type):
            McpToolConfig.model_validate(self.config)
        else:
            HttpToolConfig.model_validate(self.config)
        return self


class CreateToolOutput(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID | None = None
    name: str
    description: str | None
    type: ToolType
    config: dict | None
    input_schema: dict | None
    output_schema: dict | None
    risk_level: RiskLevel
    timeout_ms: int | None
    status: ToolStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreateSecretInput(BaseModel):
    project_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    type: SecretType = SecretType.CUSTOM
    value: str = Field(..., min_length=1)
    data: dict | None = None


class CreateSecretOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    type: SecretType
    data: dict | None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UpdateToolInput(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    agent_id: UUID | None = None
    type: ToolType | None = None
    config: dict[str, Any] | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    risk_level: RiskLevel | None = None
    timeout_ms: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_protocol_config(self) -> "UpdateToolInput":
        if self.config is None or self.type is None:
            return self
        if is_mcp_tool_type(self.type):
            McpToolConfig.model_validate(self.config)
        else:
            HttpToolConfig.model_validate(self.config)
        return self


class UpdateToolStatusInput(BaseModel):
    status: ToolStatus


class DeleteToolInput(BaseModel):
    tool_id: UUID


class ToolUsageImpactOutput(BaseModel):
    tool_id: UUID
    status: ToolStatus
    in_use: bool
    can_delete: bool
    can_retire: bool
    draft_agents: int = 0
    staging_agents: int = 0
    production_agents: int = 0
    historical_releases: int = 0
    total_references: int = 0


class TestToolInput(BaseModel):
    type: ToolType | None = None
    config: dict[str, Any]
    input_data: dict[str, Any] | None = None
    timeout_ms: int = Field(default=30000, ge=1)


class TestToolOutput(BaseModel):
    success: bool
    status_code: int | None = None
    headers: dict | None = None
    body: str | None = None
    output: dict | None = None
    duration_ms: float | None = None
    error: str | None = None


class ExecuteToolInput(BaseModel):
    tool_id: UUID
    input_data: dict[str, Any] | None = None
    agent_id: UUID | None = None


class ExecuteToolOutput(BaseModel):
    success: bool
    output: dict | None = None
    duration_ms: float | None = None
    error: str | None = None


class ListToolsInput(BaseModel):
    project_id: UUID | None = None


class ListToolsByAgentInput(BaseModel):
    agent_id: UUID


class ListSecretsInput(BaseModel):
    project_id: UUID | None = None
