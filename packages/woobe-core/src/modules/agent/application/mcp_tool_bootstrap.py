from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from modules.agent.application.mcp_connection_templates import (
    ProjectEnvironmentResolver,
    materialize_mcp_connection_config,
)
from modules.agent.application.mcp_discovery import (
    DiscoverMcpToolsUseCase,
    McpDiscoverInput,
    McpDiscoverOutput,
)
from modules.agent.application.mcp_oauth_metadata_validation import (
    McpOAuthMetadataValidation,
    oauth_validation_diagnostic_fields,
    validate_mcp_oauth_metadata,
    validated_mcp_status,
    write_mcp_oauth_validation,
)
from modules.agent.application.mcp_permissions import (
    MCP_PERMISSION_ALLOW,
    merge_discovered_tools_with_existing_permissions,
    normalize_discovered_tools,
    normalize_permission,
)
from modules.agent.application.interfaces.mcp_readiness import classify_mcp_discovery_status
from modules.agent.application.interfaces.ports import ToolExecutionPort
from modules.agent.application.tool_types import is_mcp_tool_type
from modules.agent.domain.entities import Tool
from shared.contracts.time import utc_now

DEFAULT_CREATE_DISCOVERY_TIMEOUT_MS = 10000


class McpToolBootstrapResult(BaseModel):
    tool_id: UUID
    discovered_count: int = 0
    initialized: bool = False
    status: str
    error: str | None = None
    http_status: int | None = None
    phase: str | None = None


def _raw_headers_from_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    server = config.get("server") or {}
    raw_headers = config.get("server_headers") or server.get("headers") or []
    if isinstance(raw_headers, dict):
        return [{"key": str(key), "value": str(value)} for key, value in raw_headers.items() if key]
    if not isinstance(raw_headers, list):
        return []
    return [item for item in raw_headers if isinstance(item, dict)]


def _headers_from_raw(raw_headers: list[dict[str, Any]]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for item in raw_headers:
        key = item.get("key")
        if key:
            headers[str(key)] = str(item.get("value", ""))
    return headers


def _server_url_from_config(config: dict[str, Any]) -> str:
    server = config.get("server") or {}
    return str(server.get("url") or config.get("url") or "").strip()


def _permission_counts(discovered_tools: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"allow": 0, "deny": 0, "review": 0}
    for item in discovered_tools:
        mode = normalize_permission(item.get("permission"))["mode"]
        if mode in counts:
            counts[mode] += 1
    return counts


def _readiness(
    *,
    state: str,
    label: str,
    message: str,
    action: str,
    discovered_tools: list[dict[str, Any]],
    oauth_connected: bool = False,
    mcp_ready: bool = False,
    supports_device_code: bool = False,
    needs_provider_client: bool = False,
) -> dict[str, Any]:
    counts = _permission_counts(discovered_tools)
    return {
        "state": state,
        "label": label,
        "message": message,
        "action": action,
        "can_use_tools": state == "ready" and counts[MCP_PERMISSION_ALLOW] > 0,
        "oauth_connected": oauth_connected,
        "mcp_ready": mcp_ready,
        "discovered_count": len(discovered_tools),
        "exposed_count": counts[MCP_PERMISSION_ALLOW],
        "supports_device_code": supports_device_code,
        "needs_provider_client": needs_provider_client,
    }


def _diagnostic(
    output: McpDiscoverOutput,
    *,
    server_url: str,
    status: str,
    checked_at: str,
    oauth_validation: McpOAuthMetadataValidation | None = None,
) -> dict[str, Any]:
    diagnostic = {
        "status": status,
        "phase": output.phase,
        "http_status": output.http_status,
        "initialized": output.initialized,
        "error": output.error,
        "server_url": server_url,
        "checked_at": checked_at,
        "www_authenticate": output.www_authenticate[:1000] if output.www_authenticate else None,
    }
    diagnostic.update(oauth_validation_diagnostic_fields(oauth_validation))
    return diagnostic


def _preliminary_status(output: McpDiscoverOutput) -> str:
    return classify_mcp_discovery_status(
        has_tools=bool(output.tools),
        error=output.error,
        http_status=output.http_status,
        www_authenticate=output.www_authenticate,
    )


async def _validated_status(
    executor: ToolExecutionPort,
    *,
    output: McpDiscoverOutput,
    server_url: str,
    timeout_ms: int,
) -> tuple[str, McpOAuthMetadataValidation | None]:
    status = _preliminary_status(output)
    if status != "oauth_required":
        return status, None
    validation = await validate_mcp_oauth_metadata(
        executor,
        server_url=server_url,
        www_authenticate=output.www_authenticate,
        timeout_ms=timeout_ms,
    )
    return validated_mcp_status(validation), validation


class McpToolBootstrapper:
    def __init__(
        self,
        executor: ToolExecutionPort,
        *,
        default_timeout_ms: int = DEFAULT_CREATE_DISCOVERY_TIMEOUT_MS,
        project_environment_resolver: ProjectEnvironmentResolver | None = None,
    ) -> None:
        self._executor = executor
        self._default_timeout_ms = default_timeout_ms
        self._project_environment_resolver = project_environment_resolver

    async def bootstrap(self, tool: Tool, *, timeout_ms: int | None = None) -> McpToolBootstrapResult | None:
        if not is_mcp_tool_type(tool.type):
            return None

        config = dict(tool.config or {})
        existing_tools = normalize_discovered_tools(config.get("discovered_tools"))

        try:
            connection_config = await materialize_mcp_connection_config(
                config,
                project_id=tool.project_id,
                resolver=self._project_environment_resolver,
                environment="draft",
            )
        except Exception as exc:
            status = "discovery_failed"
            config["mcp_status"] = status
            config["mcp_discovery"] = {
                "status": status,
                "phase": "project_environment",
                "http_status": None,
                "initialized": False,
                "error": str(exc),
                "server_url": _server_url_from_config(config),
                "checked_at": utc_now().isoformat(),
            }
            config["mcp_readiness"] = _readiness(
                state="discovery_failed",
                label="Discovery failed",
                message="Project Environment could not be resolved for MCP discovery.",
                action="configure_credentials",
                discovered_tools=existing_tools,
            )
            tool.config = config
            return McpToolBootstrapResult(
                tool_id=tool.id,
                status=status,
                error=str(exc),
                phase="project_environment",
            )

        server_url = _server_url_from_config(connection_config)

        if not server_url:
            status = "invalid_config"
            config["mcp_status"] = status
            config["mcp_readiness"] = _readiness(
                state="not_ready",
                label="Invalid MCP config",
                message="MCP server.url is required before tools can be loaded.",
                action="refresh",
                discovered_tools=existing_tools,
            )
            tool.config = config
            return McpToolBootstrapResult(tool_id=tool.id, status=status)

        effective_timeout = timeout_ms or tool.timeout_ms or int(config.get("timeout_ms") or self._default_timeout_ms)
        effective_timeout = min(effective_timeout, self._default_timeout_ms)

        try:
            output = await DiscoverMcpToolsUseCase(self._executor).execute(
                McpDiscoverInput(
                    server_url=server_url,
                    headers=_headers_from_raw(_raw_headers_from_config(connection_config)),
                    timeout_ms=effective_timeout,
                )
            )
        except Exception as exc:
            status = "discovery_failed"
            config["mcp_status"] = status
            config["mcp_discovery"] = {
                "status": status,
                "phase": "bootstrap",
                "http_status": None,
                "initialized": False,
                "error": str(exc),
                "server_url": server_url,
                "checked_at": utc_now().isoformat(),
            }
            config["oauth_discovery_error"] = str(exc)
            config["mcp_readiness"] = _readiness(
                state="discovery_failed",
                label="Discovery failed",
                message="ProjectRAI could not load this MCP provider. Retry loading tools or edit the provider configuration.",
                action="refresh",
                discovered_tools=existing_tools,
            )
            tool.config = config
            return McpToolBootstrapResult(tool_id=tool.id, status=status, error=str(exc))

        status, oauth_validation = await _validated_status(
            self._executor,
            output=output,
            server_url=server_url,
            timeout_ms=effective_timeout,
        )
        checked_at = utc_now().isoformat()
        config["mcp_status"] = status
        config["mcp_discovery"] = _diagnostic(
            output,
            server_url=server_url,
            status=status,
            checked_at=checked_at,
            oauth_validation=oauth_validation,
        )
        if oauth_validation is not None:
            write_mcp_oauth_validation(config, oauth_validation, checked_at=checked_at)

        if output.tools:
            next_tools = [item.model_dump() for item in output.tools]
            discovered_tools = merge_discovered_tools_with_existing_permissions(next_tools, existing_tools)
            config["discovered_tools"] = discovered_tools
            config["discovered_at"] = checked_at
            config.pop("oauth_discovery_error", None)
            counts = _permission_counts(discovered_tools)
            if counts[MCP_PERMISSION_ALLOW] > 0:
                config["mcp_readiness"] = _readiness(
                    state="ready",
                    label="Ready",
                    message=f"{counts[MCP_PERMISSION_ALLOW]} MCP tools are available to agents.",
                    action="manage_tools",
                    discovered_tools=discovered_tools,
                    mcp_ready=True,
                )
            else:
                config["mcp_readiness"] = _readiness(
                    state="needs_permission",
                    label="Needs permission",
                    message="MCP tools were loaded. Choose which tools agents can use.",
                    action="configure_permissions",
                    discovered_tools=discovered_tools,
                    mcp_ready=True,
                )
            tool.config = config
            return McpToolBootstrapResult(
                tool_id=tool.id,
                discovered_count=len(discovered_tools),
                initialized=output.initialized,
                status="ready",
                http_status=output.http_status,
                phase=output.phase,
            )

        readiness_by_status: dict[str, tuple[str, str, str, str]] = {
            "oauth_required": (
                "needs_connection",
                "Connect",
                "This MCP provider exposed a complete OAuth configuration. Connect before loading its tools.",
                "connect",
            ),
            "provider_managed": (
                "provider_managed",
                "Managed connection required",
                "This MCP endpoint uses a provider-managed connection. Use the provider-issued connection details instead of direct OAuth discovery.",
                "provider_credentials",
            ),
            "oauth_metadata_invalid": (
                "oauth_metadata_invalid",
                "OAuth metadata invalid",
                "The server advertised OAuth, but Woobe could not validate authorization_endpoint and token_endpoint. Verify the MCP URL or use the provider-managed connection flow.",
                "review_provider",
            ),
            "needs_credentials": (
                "needs_credentials",
                "Credentials required",
                "The server rejected the request without advertising MCP OAuth. Configure the required API key or headers, or use the provider-managed connection URL.",
                "configure_credentials",
            ),
            "scope_denied": (
                "scope_denied",
                "Permission denied",
                "The server accepted the credential but denied access. Review scopes, permissions, or API key policy.",
                "configure_credentials",
            ),
            "invalid_endpoint": (
                "invalid_endpoint",
                "Invalid endpoint",
                "The host responded, but this URL is not accepting MCP requests. Verify the MCP path, commonly /mcp.",
                "edit_endpoint",
            ),
            "unavailable": (
                "unavailable",
                "Unavailable",
                "The MCP server is temporarily unavailable. Retry discovery after the provider recovers.",
                "refresh",
            ),
            "empty": (
                "no_tools",
                "No tools",
                "The MCP provider responded but did not return any tools.",
                "refresh",
            ),
        }
        readiness_state, label, message, action = readiness_by_status.get(
            status,
            (
                "discovery_failed",
                "Discovery failed",
                "ProjectRAI could not load this MCP provider. Retry loading tools or edit the provider configuration.",
                "refresh",
            ),
        )
        if oauth_validation is None and output.error:
            config["oauth_discovery_error"] = output.error
        config["mcp_readiness"] = _readiness(
            state=readiness_state,
            label=label,
            message=message,
            action=action,
            discovered_tools=existing_tools,
            needs_provider_client=status == "provider_managed",
        )

        tool.config = config
        result_error = None if status == "oauth_required" else (
            oauth_validation.error if oauth_validation and oauth_validation.error else output.error
        )
        return McpToolBootstrapResult(
            tool_id=tool.id,
            discovered_count=len(existing_tools),
            initialized=output.initialized,
            status=status,
            error=result_error,
            http_status=output.http_status,
            phase=output.phase,
        )
