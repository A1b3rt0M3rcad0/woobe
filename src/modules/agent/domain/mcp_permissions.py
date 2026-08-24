from __future__ import annotations

from typing import Any

MCP_PERMISSION_ALLOW = "allow"
MCP_PERMISSION_DENY = "deny"
MCP_PERMISSION_REVIEW = "review"
MCP_PERMISSION_MODES = {
    MCP_PERMISSION_ALLOW,
    MCP_PERMISSION_DENY,
    MCP_PERMISSION_REVIEW,
}


def normalize_permission(
    value: Any,
    *,
    default_mode: str = MCP_PERMISSION_REVIEW,
) -> dict[str, Any]:
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


def normalize_discovered_tool(
    raw: dict[str, Any],
    *,
    fallback_permission: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = dict(raw)
    permission = (
        fallback_permission
        if fallback_permission is not None
        else item.get("permission")
    )
    item["permission"] = normalize_permission(
        permission or default_mcp_permission()
    )
    return item


def normalize_discovered_tools(raw_tools: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_tools, list):
        return []
    result: list[dict[str, Any]] = []
    for raw in raw_tools:
        if (
            isinstance(raw, dict)
            and isinstance(raw.get("name"), str)
            and raw["name"].strip()
        ):
            result.append(normalize_discovered_tool(raw))
    return result


def merge_discovered_tools_with_existing_permissions(
    new_tools: list[dict[str, Any]],
    existing_tools: Any,
) -> list[dict[str, Any]]:
    existing_by_name: dict[str, dict[str, Any]] = {}
    for item in normalize_discovered_tools(existing_tools):
        name = item.get("name")
        if isinstance(name, str):
            existing_by_name[name] = (
                item.get("permission") or default_mcp_permission()
            )

    result: list[dict[str, Any]] = []
    for raw in new_tools:
        name = raw.get("name")
        fallback = existing_by_name.get(name) if isinstance(name, str) else None
        result.append(
            normalize_discovered_tool(raw, fallback_permission=fallback)
        )
    return result


def mcp_tool_permission_mode(
    config: dict[str, Any],
    remote_tool_name: str,
) -> str:
    discovered_tools = normalize_discovered_tools(config.get("discovered_tools"))
    if not discovered_tools:
        return MCP_PERMISSION_ALLOW
    for item in discovered_tools:
        if item.get("name") == remote_tool_name:
            return normalize_permission(item.get("permission"))["mode"]
    return MCP_PERMISSION_REVIEW


def allowed_mcp_discovered_tools(
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        item
        for item in normalize_discovered_tools(config.get("discovered_tools"))
        if normalize_permission(item.get("permission"))["mode"]
        == MCP_PERMISSION_ALLOW
    ]
