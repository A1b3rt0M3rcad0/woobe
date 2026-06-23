from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from modules.agent.application.mcp_discovery import DiscoverMcpToolsUseCase, McpDiscoverInput
from modules.agent.application.mcp_permissions import merge_discovered_tools_with_existing_permissions
from modules.agent.application.ports import ToolExecutionPort, ToolSecretResolverPort
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import ToolType
from modules.agent.domain.repositories import ToolRepository
from shared.infra.time import utc_now

logger = logging.getLogger(__name__)


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _is_mcp_server_provider(tool: Tool) -> bool:
    config = tool.config or {}
    tool_type = _enum_value(tool.type)
    return (
        tool_type in {ToolType.MCP.value, "mcp", "http_mcp"}
        and (config.get("mode") == "server" or config.get("exposure") == "all_discovered")
        and (config.get("server") or {}).get("transport", "streamable_http") == "streamable_http"
    )


def _parse_discovered_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _needs_refresh(tool: Tool, now: datetime) -> bool:
    config = tool.config or {}
    if not _is_mcp_server_provider(tool):
        return False
    ttl_seconds = config.get("discovery_cache_ttl_seconds", 3600)
    try:
        ttl_seconds = int(ttl_seconds)
    except (TypeError, ValueError):
        ttl_seconds = 3600
    if ttl_seconds < 0:
        return False
    discovered_tools = config.get("discovered_tools") or []
    if not discovered_tools:
        return True
    if ttl_seconds == 0:
        return True
    discovered_at = _parse_discovered_at(config.get("discovered_at"))
    if discovered_at is None:
        return True
    return discovered_at + timedelta(seconds=ttl_seconds) <= now


def _raw_headers_from_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    server = config.get("server") or {}
    raw_headers = config.get("server_headers") or server.get("headers") or []
    if isinstance(raw_headers, dict):
        return [{"key": str(k), "value": str(v)} for k, v in raw_headers.items() if k]
    if not isinstance(raw_headers, list):
        return []
    return [header for header in raw_headers if isinstance(header, dict)]


def _headers_from_raw(raw_headers: list[dict[str, Any]]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for header in raw_headers:
        key = header.get("key")
        if key:
            headers[str(key)] = str(header.get("value", ""))
    return headers


async def _resolve_headers(
    *,
    raw_headers: list[dict[str, Any]],
    tool: Tool,
    secret_resolver: ToolSecretResolverPort | None,
) -> dict[str, str]:
    if secret_resolver is not None and tool.project_id is not None:
        return await secret_resolver.resolve_headers(raw_headers, tool.project_id)
    return _headers_from_raw(raw_headers)


async def refresh_stale_mcp_server_tools(
    *,
    tools: list[Tool],
    tool_repo: ToolRepository,
    executor: ToolExecutionPort,
    secret_resolver: ToolSecretResolverPort | None = None,
) -> list[Tool]:
    now = utc_now()
    discovery = DiscoverMcpToolsUseCase(executor)
    refreshed_tools: list[Tool] = []

    for tool in tools:
        if not _needs_refresh(tool, now):
            refreshed_tools.append(tool)
            continue

        config = dict(tool.config or {})
        server = config.get("server") or {}
        server_url = server.get("url") or config.get("url")
        if not server_url:
            refreshed_tools.append(tool)
            continue

        try:
            output = await discovery.execute(
                McpDiscoverInput(
                    server_url=str(server_url),
                    headers=await _resolve_headers(
                        raw_headers=_raw_headers_from_config(config),
                        tool=tool,
                        secret_resolver=secret_resolver,
                    ),
                    timeout_ms=tool.timeout_ms or int(config.get("timeout_ms") or 30000),
                )
            )
        except Exception as exc:
            logger.warning("MCP discovery refresh failed for tool %s: %s", tool.id, exc)
            refreshed_tools.append(tool)
            continue

        if output.error or not output.tools:
            logger.warning("MCP discovery refresh returned no tools for tool %s: %s", tool.id, output.error)
            refreshed_tools.append(tool)
            continue

        next_tools = [item.model_dump() for item in output.tools]
        config["discovered_tools"] = merge_discovered_tools_with_existing_permissions(next_tools, config.get("discovered_tools"))
        config["discovered_at"] = now.isoformat()
        tool.config = config
        tool.updated_at = now
        try:
            refreshed_tools.append(await tool_repo.update(tool))
        except Exception as exc:
            logger.warning("Failed to persist MCP discovery refresh for tool %s: %s", tool.id, exc)
            refreshed_tools.append(tool)

    return refreshed_tools
