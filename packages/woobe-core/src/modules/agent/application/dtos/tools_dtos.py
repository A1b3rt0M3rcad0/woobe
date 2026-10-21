from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator, field_serializer

from modules.agent.domain.oauth_public_configuration import public_tool_configuration, reject_public_oauth_material

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


class HttpArtifactFileBinding(BaseModel):
    """A model argument that names one exact authorized Artifact revision."""

    input_name: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    mode: Literal["bytes", "multipart", "url"]
    part_name: str = Field(default="file", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    content_types: list[str] = Field(..., min_length=1, max_length=32)
    max_bytes: int = Field(default=25 * 1024 * 1024, ge=1, le=50 * 1024 * 1024)
    idempotency_header: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        pattern=r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$",
    )

    @model_validator(mode="after")
    def validate_file_contract(self):
        normalized = [value.strip().lower() for value in self.content_types]
        if any(
            re.fullmatch(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+", value) is None
            for value in normalized
        ):
            raise ValueError("Artifact transfer content_types must be valid media types")
        if self.idempotency_header and self.idempotency_header.lower() in {
            "authorization", "connection", "content-length", "content-type", "cookie",
            "host", "proxy-authorization", "transfer-encoding",
        }:
            raise ValueError("Idempotency header cannot override a reserved HTTP header")
        self.content_types = normalized
        return self


class ToolArtifactOutputBinding(BaseModel):
    """Explicit bounded projection of one external Tool result into Artifacts."""

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    mode: Literal["response_body", "json_base64", "mcp_resource"]
    path: str = Field(..., min_length=1, max_length=1024)
    content_types: list[str] = Field(..., min_length=1, max_length=16)
    max_bytes: int = Field(default=1024 * 1024, ge=1, le=8 * 1024 * 1024)
    data_pointer: str | None = Field(default=None, max_length=1024)
    content_type_pointer: str | None = Field(default=None, max_length=1024)
    sha256_pointer: str | None = Field(default=None, max_length=1024)
    operation_ref_pointer: str | None = Field(default=None, max_length=1024)
    status_pointer: str | None = Field(default=None, max_length=1024)
    pending_statuses: list[str] = Field(default_factory=list, max_length=8)
    success_pointer: str | None = Field(default=None, max_length=1024)
    resource_name: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_output_binding(self) -> "ToolArtifactOutputBinding":
        path_parts = self.path.split("/")
        if ("\\" in self.path or any(part in {"", ".", ".."} for part in path_parts)
                or any(ord(char) < 32 or ord(char) == 127 for char in self.path)):
            raise ValueError("External Artifact output path must be a logical Workspace path")
        media_types = [item.strip().lower() for item in self.content_types]
        if any(
            re.fullmatch(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+", item) is None
            for item in media_types
        ):
            raise ValueError("External Artifact output requires valid media types")
        self.content_types = media_types
        for pointer in (
            self.data_pointer,
            self.content_type_pointer,
            self.sha256_pointer,
            self.operation_ref_pointer,
            self.status_pointer,
            self.success_pointer,
        ):
            if pointer is not None and (not pointer.startswith("/") or "\x00" in pointer):
                raise ValueError("External Artifact output JSON pointers must be absolute")
        if self.mode == "json_base64" and self.data_pointer is None:
            raise ValueError("JSON output binding requires a base64 data pointer")
        if self.status_pointer is not None and (self.mode != "json_base64" or self.operation_ref_pointer is None):
            raise ValueError("External operation status requires a JSON output binding and operation reference")
        statuses = [status.strip().lower() for status in self.pending_statuses]
        if any(not status or len(status) > 64 for status in statuses) or len(set(statuses)) != len(statuses):
            raise ValueError("External operation pending statuses must be short, unique strings")
        if statuses and self.status_pointer is None:
            raise ValueError("Pending statuses require an external operation status pointer")
        self.pending_statuses = statuses
        if self.mode == "mcp_resource" and not self.resource_name:
            raise ValueError("MCP resource output binding requires a negotiated resource name")
        if self.mode != "mcp_resource" and self.resource_name is not None:
            raise ValueError("Only MCP resource output bindings accept a resource name")
        if self.mode != "json_base64" and any(
            pointer is not None for pointer in (
                self.data_pointer, self.content_type_pointer, self.sha256_pointer, self.status_pointer,
            )
        ):
            raise ValueError("Only JSON base64 output bindings accept content pointers")
        return self


class HttpRouteConfig(BaseModel):
    authentication: dict[str, Any] | None = None
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
    file_bindings: list["HttpArtifactFileBinding"] = Field(default_factory=list)
    output_bindings: list[ToolArtifactOutputBinding] = Field(default_factory=list, max_length=3)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    status: Literal["active", "inactive"] = "active"
    default_permission: Literal["allow", "deny", "review"] = "review"
    permission: dict[str, Any] | None = None
    timeout_ms: int | None = Field(default=None, ge=1)
    contract_version: int | None = None
    contract_hash: str | None = None

    @model_validator(mode="after")
    def validate_output_bindings(self) -> "HttpRouteConfig":
        if len({item.name for item in self.output_bindings}) != len(self.output_bindings):
            raise ValueError("HTTP route output binding names must be unique")
        if len({item.path for item in self.output_bindings}) != len(self.output_bindings):
            raise ValueError("HTTP route output binding paths must be unique")
        if any(item.mode == "mcp_resource" for item in self.output_bindings):
            raise ValueError("HTTP routes cannot bind MCP resource outputs")
        return self


class HttpToolConfig(BaseModel):
    authentication: dict[str, Any] | None = None
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
    file_bindings: list["HttpArtifactFileBinding"] = Field(default_factory=list)
    output_bindings: list[ToolArtifactOutputBinding] = Field(default_factory=list, max_length=3)
    auth: HttpAuthConfig | None = None
    timeout_ms: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_target(self) -> "HttpToolConfig":
        from modules.agent.domain.tool_configuration import validate_tool_authentication
        # Private compatibility references are verified against the exact Tool
        # owner by persistence; accepting their shape grants no use authority.
        validate_tool_authentication(self.model_dump(exclude_none=True), allow_legacy=True)
        if any(binding.mode == "mcp_resource" for binding in self.output_bindings):
            raise ValueError("HTTP Tools cannot bind MCP resource outputs")
        if len({item.name for item in self.output_bindings}) != len(self.output_bindings):
            raise ValueError("HTTP output binding names must be unique")
        if len({item.path for item in self.output_bindings}) != len(self.output_bindings):
            raise ValueError("HTTP output binding paths must be unique")
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


class McpArtifactFileBinding(BaseModel):
    """A schema-negotiated exact Artifact value for one MCP argument."""

    input_name: str = Field(..., min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    mode: Literal["base64", "url"]
    content_types: list[str] = Field(..., min_length=1, max_length=32)
    max_bytes: int = Field(default=4 * 1024 * 1024, ge=1, le=4 * 1024 * 1024)

    @model_validator(mode="after")
    def validate_media_types(self) -> "McpArtifactFileBinding":
        normalized = [value.strip().lower() for value in self.content_types]
        if any(
            re.fullmatch(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+", value) is None
            for value in normalized
        ):
            raise ValueError("MCP Artifact bindings require valid media types")
        self.content_types = normalized
        return self


class McpToolConfig(BaseModel):
    authentication: dict[str, Any] | None = None
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
    file_bindings: list[McpArtifactFileBinding] = Field(default_factory=list)
    output_bindings: list[ToolArtifactOutputBinding] = Field(default_factory=list, max_length=3)
    discovery_cache_ttl_seconds: int | None = Field(default=None, ge=0)
    timeout_ms: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_transport_target(self) -> "McpToolConfig":
        from modules.agent.domain.tool_configuration import validate_tool_authentication
        validate_tool_authentication(self.model_dump(exclude_none=True), allow_legacy=True)
        if any(binding.mode == "response_body" for binding in self.output_bindings):
            raise ValueError("MCP Tools cannot bind raw HTTP response bodies")
        if len({item.name for item in self.output_bindings}) != len(self.output_bindings):
            raise ValueError("MCP output binding names must be unique")
        if len({item.path for item in self.output_bindings}) != len(self.output_bindings):
            raise ValueError("MCP output binding paths must be unique")
        if self.output_bindings and (self.mode == "server" or self.exposure == "all_discovered"):
            raise ValueError("MCP output bindings require a single selected remote Tool")
        if not self.server.url:
            raise ValueError("MCP server.url is required for streamable_http transport")
        if self.mode != "server" and self.exposure != "all_discovered" and not self.tool_name:
            raise ValueError("MCP tool_name is required when exposing a single MCP tool")
        if self.file_bindings:
            if self.mode == "server" or self.exposure == "all_discovered":
                raise ValueError("MCP Artifact file bindings require a single selected remote Tool")
            schema = self.discovered_input_schema
            if not isinstance(schema, dict):
                raise ValueError("MCP Artifact file bindings require the discovered input schema")
            seen: set[str] = set()
            properties = schema.get("properties")
            if not isinstance(properties, dict):
                raise ValueError("MCP Artifact file bindings require object input properties")
            for binding in self.file_bindings:
                name = binding.input_name
                prop = properties.get(name)
                if name in seen or not isinstance(prop, dict) or prop.get("type") != "string":
                    raise ValueError("MCP Artifact binding must match a unique string property")
                expected = (
                    prop.get("format") == "byte" or prop.get("contentEncoding") == "base64"
                    if binding.mode == "base64"
                    else prop.get("format") == "uri"
                )
                if not expected:
                    raise ValueError("MCP Artifact binding mode does not match the negotiated input schema")
                seen.add(name)
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
        reject_public_oauth_material(self.config)
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

    @field_serializer('config')
    def public_config(self, config):
        return public_tool_configuration(config, tool_type=self.type)


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
