from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from modules.agent.domain.repositories import ToolRepository

McpPermissionMode = Literal["allow", "deny", "review"]
MCP_PERMISSION_ALLOW = "allow"
MCP_PERMISSION_DENY = "deny"
MCP_PERMISSION_REVIEW = "review"
MCP_PERMISSION_MODES = {MCP_PERMISSION_ALLOW, MCP_PERMISSION_DENY, MCP_PERMISSION_REVIEW}
MCP_CONNECTION_STATES = {"needs_connection", "oauth_required", "metadata_required", "token_invalid", "disconnected"}


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


def normalize_permission(value: Any, *, default_mode: str = MCP_PERMISSION_REVIEW) -> dict[str, Any]:
    if isinstance(value, dict):
        mode = str(value.get("mode") or default_mode).lower()
        risk_level = value.get("risk_level")
    else:
        mode = str(value or default_mode).lower()
        risk_level = None
    if mode not in MCP_PERMISSION_MODES:
        mode = default_mode
    result: dict[str, Any] = {"mode": mode}
    if isinstance(risk_level, str) and risk_level.strip():
        result["risk_level"] = risk_level.strip()
    elif mode == MCP_PERMISSION_REVIEW:
        result["risk_level"] = "unknown"
    return result


def default_mcp_permission() -> dict[str, Any]:
    return {"mode": MCP_PERMISSION_REVIEW, "risk_level": "unknown"}


def normalize_discovered_tool(raw: dict[str, Any], *, fallback_permission: dict[str, Any] | None = None) -> dict[str, Any]:
    item = dict(raw)
    item["permission"] = normalize_permission(item.get("permission") or fallback_permission or default_mcp_permission())
    return item


def normalize_discovered_tools(raw_tools: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_tools, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in raw_tools:
        if isinstance(raw, dict) and isinstance(raw.get("name"), str) and raw["name"].strip():
            result.append(normalize_discovered_tool(raw))
    return result


def merge_discovered_tools_with_existing_permissions(new_tools: list[dict[str, Any]], existing_tools: Any) -> list[dict[str, Any]]:
    existing_by_name: dict[str, dict[str, Any]] = {}
    for item in normalize_discovered_tools(existing_tools):
        name = item.get("name")
        if isinstance(name, str):
            existing_by_name[name] = item.get("permission") or default_mcp_permission()

    result: list[dict[str, Any]] = []
    for raw in new_tools:
        name = raw.get("name")
        fallback = existing_by_name.get(name) if isinstance(name, str) else None
        result.append(normalize_discovered_tool(raw, fallback_permission=fallback))
    return result


def mcp_tool_permission_mode(config: dict[str, Any], remote_tool_name: str) -> str:
    discovered_tools = normalize_discovered_tools(config.get("discovered_tools"))
    if not discovered_tools:
        return MCP_PERMISSION_ALLOW
    for item in discovered_tools:
        if item.get("name") == remote_tool_name:
            return normalize_permission(item.get("permission"))["mode"]
    return MCP_PERMISSION_REVIEW


def allowed_mcp_discovered_tools(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in normalize_discovered_tools(config.get("discovered_tools"))
        if normalize_permission(item.get("permission"))["mode"] == MCP_PERMISSION_ALLOW
    ]


def _permission_counts(discovered_tools: list[dict[str, Any]]) -> dict[str, int]:
    counts = {MCP_PERMISSION_ALLOW: 0, MCP_PERMISSION_DENY: 0, MCP_PERMISSION_REVIEW: 0}
    for item in discovered_tools:
        mode = normalize_permission(item.get("permission"))["mode"]
        counts[mode] += 1
    return counts


def write_mcp_readiness(config: dict[str, Any]) -> None:
    discovered_tools = normalize_discovered_tools(config.get("discovered_tools"))
    oauth = config.get("oauth") if isinstance(config.get("oauth"), dict) else {}
    oauth_connected = oauth.get("status") == "connected" if isinstance(oauth, dict) else False
    status = str(config.get("mcp_status") or "")
    mcp_ready = status == "ready"
    counts = _permission_counts(discovered_tools)

    if discovered_tools and counts[MCP_PERMISSION_ALLOW] > 0:
        state = "ready"
        label = "Ready"
        message = f"{counts[MCP_PERMISSION_ALLOW]} MCP tools are available to agents."
        action = "manage_tools"
        can_use_tools = True
    elif discovered_tools:
        state = "needs_permission"
        label = "Needs permission"
        message = "MCP tools were loaded. Choose which tools agents can use."
        action = "configure_permissions"
        can_use_tools = False
    elif status in MCP_CONNECTION_STATES:
        state = "needs_connection"
        label = "Connect"
        message = "This MCP provider requires OAuth before its tools can be loaded."
        action = "connect"
        can_use_tools = False
    elif status == "provider_client_rejected":
        state = "provider_not_supported"
        label = "Provider setup needed"
        message = "This provider needs a provider-issued client or alternate OAuth flow."
        action = "provider_credentials"
        can_use_tools = False
    elif status in {"empty", "no_tools"}:
        state = "no_tools"
        label = "No tools"
        message = "The MCP provider responded but did not return any tools."
        action = "refresh"
        can_use_tools = False
    elif status == "discovery_failed":
        state = "discovery_failed"
        label = "Discovery failed"
        message = "ProjectRAI could not load this MCP provider. Retry loading tools or edit the provider configuration."
        action = "refresh"
        can_use_tools = False
    else:
        existing = config.get("mcp_readiness") if isinstance(config.get("mcp_readiness"), dict) else {}
        state = str(existing.get("state") or "not_ready")
        label = str(existing.get("label") or "Not ready")
        message = str(existing.get("message") or "MCP tools are not available yet.")
        action = str(existing.get("action") or "refresh")
        can_use_tools = False

    config["mcp_readiness"] = {
        "state": state,
        "label": label,
        "message": message,
        "action": action,
        "can_use_tools": can_use_tools,
        "oauth_connected": oauth_connected,
        "mcp_ready": mcp_ready,
        "discovered_count": len(discovered_tools),
        "exposed_count": counts[MCP_PERMISSION_ALLOW],
        "supports_device_code": False,
        "needs_provider_client": False,
    }


def _permissions_output(tool_id: UUID, discovered_tools: list[dict[str, Any]]) -> McpToolPermissionsOutput:
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

    async def execute(self, input_dto: UpdateMcpToolPermissionsInput) -> McpToolPermissionsOutput:
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

    async def execute(self, input_dto: BulkUpdateMcpToolPermissionsInput) -> McpToolPermissionsOutput:
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
