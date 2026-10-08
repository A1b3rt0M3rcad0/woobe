from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from modules.agent.application.http_tool_contract import (
    compile_http_tool_group_contract,
    compile_http_tool_contract,
    is_http_tool_group,
)
from modules.agent.application.tool_context_bindings import validate_context_bindings
from modules.agent.application.tool_types import is_mcp_tool_type
from modules.agent.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType


class ToolBindingSource(BaseModel):
    kind: Literal["context", "project_environment"] = "context"
    field: str = Field(..., min_length=1)


class ToolInputBinding(BaseModel):
    source: ToolBindingSource


class HttpHeaderConfig(BaseModel):
    key: str = Field(..., min_length=1)
    value: str = ""
    sensitive: bool | None = None
    mode: Literal["set", "remove"] = "set"


class HttpAuthConfig(BaseModel):
    type: Literal["none", "api_key", "bearer", "basic"] = "none"
    credentials: list[str] | None = None


class ToolPermissionConfig(BaseModel):
    mode: Literal["allow", "deny", "review"]
    risk_level: RiskLevel | None = None


class HttpRouteConfig(BaseModel):
    id: str = Field(..., min_length=1)
    operation_id: str | None = None
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"] = "GET"
    path: str = Field(..., min_length=1)
    headers: list[HttpHeaderConfig] = Field(default_factory=list)
    body: str | dict[str, Any] | list[Any] | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    bindings: dict[str, ToolInputBinding] = Field(default_factory=dict)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    status: Literal["active", "inactive"] = "active"
    default_permission: Literal["allow", "deny", "review"] = "review"
    permission: dict[str, Any] | None = None
    timeout_ms: int | None = Field(default=None, ge=1)
    contract_version: int | None = None
    contract_hash: str | None = None


class HttpToolConfig(BaseModel):
    permission: ToolPermissionConfig | None = None
    protocol: Literal["http"] | None = None
    mode: Literal["single", "group"] = "single"
    schema_version: int | None = None
    url: str = ""
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"] = "GET"
    base_url: str | None = None
    routes: list[HttpRouteConfig] = Field(default_factory=list)
    headers: list[HttpHeaderConfig] = Field(default_factory=list)
    body: str | dict[str, Any] | list[Any] | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    bindings: dict[str, ToolInputBinding] = Field(default_factory=dict)
    auth: HttpAuthConfig | None = None
    timeout_ms: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self) -> "HttpToolConfig":
        if self.mode == "group":
            if not self.base_url:
                raise ValueError("HTTP API base_url is required for group mode")
            if not self.routes:
                raise ValueError("HTTP API group requires at least one route")
        elif not self.url:
            raise ValueError("HTTP Tool url is required")
        return self


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
    bindings: dict[str, ToolInputBinding] = Field(default_factory=dict)
    permission: dict[str, Any] | None = None


class McpToolConfig(BaseModel):
    permission: ToolPermissionConfig | None = None
    protocol: Literal["mcp"] | None = None
    mode: Literal["tool", "server"] = "tool"
    exposure: Literal["single", "all_discovered"] = "single"
    server: McpServerConfig
    tool_name: str | None = None
    server_headers: list[HttpHeaderConfig] = Field(default_factory=list)
    input_schema_source: Literal["discovered", "manual"] = "manual"
    discovered_input_schema: dict[str, Any] | None = None
    discovered_tools: list[McpDiscoveredToolConfig] = Field(default_factory=list)
    bindings: dict[str, ToolInputBinding] = Field(default_factory=dict)
    discovery_cache_ttl_seconds: int | None = Field(default=None, ge=0)
    timeout_ms: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_transport_target(self) -> "McpToolConfig":
        if not self.server.url:
            raise ValueError("MCP server.url is required for streamable_http transport")
        if self.mode != "server" and self.exposure != "all_discovered" and not self.tool_name:
            raise ValueError("MCP tool_name is required when exposing a single MCP tool")
        return self


def _restore_binding_omissions(
    raw_config: dict[str, Any],
    normalized: dict[str, Any],
) -> dict[str, Any]:
    """Keep omitted bindings distinguishable from an explicit empty binding map.

    Pydantic defaults missing binding maps to ``{}``. Updates need to retain the
    distinction so the application layer can preserve old bindings on omission while
    still allowing callers to clear them explicitly with ``bindings: {}``.
    """

    if "bindings" not in raw_config:
        normalized.pop("bindings", None)

    raw_routes = raw_config.get("routes")
    normalized_routes = normalized.get("routes")
    if isinstance(raw_routes, list) and isinstance(normalized_routes, list):
        for raw_route, normalized_route in zip(raw_routes, normalized_routes, strict=False):
            if (
                isinstance(raw_route, dict)
                and isinstance(normalized_route, dict)
                and "bindings" not in raw_route
            ):
                normalized_route.pop("bindings", None)
    return normalized


def _compile_http_config(
    raw_config: dict[str, Any],
    declared_schema: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    parsed = HttpToolConfig.model_validate(raw_config)
    normalized = _restore_binding_omissions(
        raw_config,
        parsed.model_dump(exclude_none=True),
    )
    validate_context_bindings(normalized)
    if is_http_tool_group(normalized):
        compiled_group = compile_http_tool_group_contract(normalized)
        return compiled_group.config, {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }
    compiled = compile_http_tool_contract(normalized, declared_schema)
    return compiled.config, compiled.input_schema


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
            validate_context_bindings(self.config)
        else:
            self.config, self.input_schema = _compile_http_config(self.config, self.input_schema)
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
        if self.config is None:
            return self
        protocol = self.type or self.config.get("protocol")
        if is_mcp_tool_type(protocol):
            McpToolConfig.model_validate(self.config)
            validate_context_bindings(self.config)
        else:
            self.config, self.input_schema = _compile_http_config(self.config, self.input_schema)
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
    project_id: UUID | None = None
    environment: Literal["draft", "staging", "production"] = "draft"
    config: dict[str, Any]
    input_data: dict[str, Any] | None = None
    external_context: dict[str, Any] | None = None
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
