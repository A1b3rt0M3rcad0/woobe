from __future__ import annotations

from modules.agent.application.dtos.mcp_tool_refresh_dtos import RefreshMcpProviderToolsInput, RefreshMcpProviderToolsOutput

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID


from modules.agent.application.mcp_discovery import DiscoverMcpToolsUseCase, McpDiscoverInput, McpDiscoverOutput
from modules.agent.application.mcp_oauth_metadata_validation import (
    McpOAuthMetadataValidation,
    oauth_validation_diagnostic_fields,
    validate_mcp_oauth_metadata,
    validated_mcp_status,
    write_mcp_oauth_validation,
)
from modules.agent.application.mcp_permissions import merge_discovered_tools_with_existing_permissions, write_mcp_readiness
from modules.agent.application.interfaces.mcp_readiness import classify_mcp_discovery_status
from modules.agent.application.interfaces.ports import ToolExecutionPort, ToolSecretResolverPort
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import ToolType
from modules.agent.application.interfaces.repositories import ToolRepository
from shared.contracts.time import utc_now

logger = logging.getLogger(__name__)






def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _is_mcp_server_provider(tool: Tool) -> bool:
    config = tool.config or {}
    tool_type = _enum_value(tool.type).lower()
    return (
        (tool_type == ToolType.MCP.value or tool_type == "mcp" or config.get("protocol") == "mcp")
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


async def _auth_headers_for(tool: Tool, auth_header_provider: Any | None) -> dict[str, str]:
    if auth_header_provider is None:
        return {}
    try:
        method = getattr(auth_header_provider, "authorization_" + "headers_for")
        return await method(tool)
    except Exception as exc:
        logger.warning("MCP discovery OAuth header resolution failed for tool %s: %s", tool.id, exc)
        return {}


def _preliminary_discovery_status(output: McpDiscoverOutput, *, config: dict[str, Any]) -> str:
    oauth = config.get("oauth") if isinstance(config.get("oauth"), dict) else {}
    protected_metadata = config.get("mcp_resource_metadata")
    return classify_mcp_discovery_status(
        has_tools=bool(output.tools),
        error=output.error,
        http_status=output.http_status,
        www_authenticate=output.www_authenticate,
        oauth_connected=oauth.get("status") == "connected",
        protected_resource_metadata=protected_metadata if isinstance(protected_metadata, dict) else None,
    )


async def _validated_discovery_status(
    executor: ToolExecutionPort,
    *,
    output: McpDiscoverOutput,
    config: dict[str, Any],
    server_url: str,
    timeout_ms: int,
) -> tuple[str, McpOAuthMetadataValidation | None]:
    status = _preliminary_discovery_status(output, config=config)
    if status != "oauth_required":
        return status, None
    validation = await validate_mcp_oauth_metadata(
        executor,
        server_url=server_url,
        www_authenticate=output.www_authenticate,
        timeout_ms=timeout_ms,
    )
    return validated_mcp_status(validation), validation


def _safe_www_authenticate(value: str | None) -> str | None:
    if not value:
        return None
    return value[:1000]


def _write_discovery_diagnostic(
    config: dict[str, Any],
    output: McpDiscoverOutput,
    *,
    status: str,
    oauth_validation: McpOAuthMetadataValidation | None,
    now: datetime,
    server_url: str,
) -> None:
    config["mcp_status"] = status
    diagnostic = {
        "status": status,
        "phase": output.phase,
        "http_status": output.http_status,
        "initialized": output.initialized,
        "error": output.error,
        "server_url": server_url,
        "checked_at": now.isoformat(),
        "www_authenticate": _safe_www_authenticate(output.www_authenticate),
    }
    diagnostic.update(oauth_validation_diagnostic_fields(oauth_validation))
    config["mcp_discovery"] = diagnostic
    if oauth_validation is not None:
        write_mcp_oauth_validation(config, oauth_validation, checked_at=now.isoformat())
    elif output.error:
        config["oauth_discovery_error"] = output.error
    else:
        config.pop("oauth_discovery_error", None)


async def _discover_and_persist_tool(
    *,
    tool: Tool,
    tool_repo: ToolRepository,
    executor: ToolExecutionPort,
    secret_resolver: ToolSecretResolverPort | None,
    auth_header_provider: Any | None,
    timeout_ms: int,
    now: datetime,
) -> RefreshMcpProviderToolsOutput:
    config = dict(tool.config or {})
    if not _is_mcp_server_provider(tool):
        raise ValueError("Tool is not an MCP server provider")
    server = config.get("server") or {}
    server_url = server.get("url") or config.get("url")
    if not server_url:
        raise ValueError("MCP server.url is required before discovery")

    configured_headers = await _resolve_headers(raw_headers=_raw_headers_from_config(config), tool=tool, secret_resolver=secret_resolver)
    oauth_headers = await _auth_headers_for(tool, auth_header_provider)
    output = await DiscoverMcpToolsUseCase(executor).execute(
        McpDiscoverInput(
            server_url=str(server_url),
            headers={**configured_headers, **oauth_headers},
            timeout_ms=timeout_ms,
        )
    )

    status, oauth_validation = await _validated_discovery_status(
        executor,
        output=output,
        config=config,
        server_url=str(server_url),
        timeout_ms=timeout_ms,
    )
    _write_discovery_diagnostic(
        config,
        output,
        status=status,
        oauth_validation=oauth_validation,
        now=now,
        server_url=str(server_url),
    )
    if output.error or not output.tools:
        write_mcp_readiness(config)
        tool.config = config
        tool.updated_at = now
        await tool_repo.update(tool)
        result_error = None if status == "oauth_required" else (
            oauth_validation.error if oauth_validation and oauth_validation.error else output.error
        )
        return RefreshMcpProviderToolsOutput(
            tool_id=tool.id,
            discovered_count=0,
            initialized=output.initialized,
            status=status,
            error=result_error,
            http_status=output.http_status,
            phase=output.phase,
        )

    next_tools = [item.model_dump() for item in output.tools]
    config["discovered_tools"] = merge_discovered_tools_with_existing_permissions(next_tools, config.get("discovered_tools"))
    config["discovered_at"] = now.isoformat()
    write_mcp_readiness(config)
    tool.config = config
    tool.updated_at = now
    await tool_repo.update(tool)
    return RefreshMcpProviderToolsOutput(
        tool_id=tool.id,
        discovered_count=len(next_tools),
        initialized=output.initialized,
        status="ready",
        error=None,
        http_status=output.http_status,
        phase=output.phase,
    )


class RefreshMcpProviderToolsUseCase:
    def __init__(
        self,
        *,
        tool_repo: ToolRepository,
        executor: ToolExecutionPort,
        secret_resolver: ToolSecretResolverPort | None = None,
        auth_header_provider: Any | None = None,
    ) -> None:
        self._tool_repo = tool_repo
        self._executor = executor
        self._secret_resolver = secret_resolver
        self._auth_header_provider = auth_header_provider

    async def execute(self, input_dto: RefreshMcpProviderToolsInput) -> RefreshMcpProviderToolsOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)
        if tool is None:
            raise ValueError("MCP tool provider not found")
        return await _discover_and_persist_tool(
            tool=tool,
            tool_repo=self._tool_repo,
            executor=self._executor,
            secret_resolver=self._secret_resolver,
            auth_header_provider=self._auth_header_provider,
            timeout_ms=input_dto.timeout_ms,
            now=utc_now(),
        )

    async def refresh_if_needed(self, tool: Tool) -> Tool:
        now = utc_now()
        if not _needs_refresh(tool, now):
            return tool
        await _discover_and_persist_tool(
            tool=tool,
            tool_repo=self._tool_repo,
            executor=self._executor,
            secret_resolver=self._secret_resolver,
            auth_header_provider=self._auth_header_provider,
            timeout_ms=tool.timeout_ms or 30000,
            now=now,
        )
        return await self._tool_repo.get_by_id(tool.id) or tool


async def refresh_stale_mcp_server_tools(
    *,
    tools: list[Tool],
    tool_repo: ToolRepository,
    executor: ToolExecutionPort,
    secret_resolver: ToolSecretResolverPort | None = None,
    auth_header_provider: Any | None = None,
) -> list[Tool]:
    refresher = RefreshMcpProviderToolsUseCase(
        tool_repo=tool_repo,
        executor=executor,
        secret_resolver=secret_resolver,
        auth_header_provider=auth_header_provider,
    )
    refreshed: list[Tool] = []
    for tool in tools:
        if not _is_mcp_server_provider(tool):
            refreshed.append(tool)
            continue
        try:
            refreshed.append(await refresher.refresh_if_needed(tool))
        except Exception as exc:
            logger.warning("Stale MCP tool refresh failed for tool %s: %s", tool.id, exc)
            refreshed.append(tool)
    return refreshed
