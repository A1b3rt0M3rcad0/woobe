from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from modules.agent.application.mcp_discovery import DiscoverMcpToolsUseCase, McpDiscoverInput
from modules.agent.application.ports import ToolExecutionPort
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


def _headers_from_config(config: dict[str, Any]) -> dict[str, str]:
    server = config.get("server") or {}
    raw_headers = config.get("server_headers") or server.get("headers") or []
    if isinstance(raw_headers, dict):
        return {str(k): str(v) for k, v in raw_headers.items() if k}
    if not isinstance(raw_headers, list):
        return {}
    headers: dict[str, str] = {}
    for header in raw_headers:
        if not isinstance(header, dict):
            continue
        key = header.get("key")
        if key:
            headers[str(key)] = str(header.get("value", ""))
    return headers


async def refresh_stale_mcp_server_tools(
    *,
    tools: list[Tool],
    tool_repo: ToolRepository,
    executor: ToolExecutionPort,
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
                    headers=_headers_from_config(config),
                    timeout_ms=tool.timeout_ms or int(config.get("timeout_ms") or 30000),
                )
            )
        except Exception as exc:
            logger.warning("MCP discovery refresh failed for tool %s: %s", tool.id, exc)
            refreshed_tools.append(tool)
            continue

        if output.error or not output.tools:
            logger.warning(
                "MCP discovery refresh returned no tools for tool %s: %s",
                tool.id,
                output.error,
            )
            refreshed_tools.append(tool)
            continue

        config["discovered_tools"] = [item.model_dump() for item in output.tools]
        config["discovered_at"] = now.isoformat()
        tool.config = config
        tool.updated_at = now
        try:
            refreshed_tools.append(await tool_repo.update(tool))
        except Exception as exc:
            logger.warning("Failed to persist MCP discovery refresh for tool %s: %s", tool.id, exc)
            refreshed_tools.append(tool)

    return refreshed_tools
