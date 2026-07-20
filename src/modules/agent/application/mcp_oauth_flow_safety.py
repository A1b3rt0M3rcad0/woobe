from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from modules.agent.application import mcp_oauth_flows as _flows
from modules.agent.application.mcp_oauth import McpOAuthMetadataResolver
from modules.agent.application.mcp_readiness import has_mcp_oauth_challenge
from modules.agent.application.ports import ToolExecutionPort
from modules.agent.domain.repositories import ToolRepository
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter

PROJECTRAI_CLIENT_NAMES = {"projectrai", "project-rai", "project_rai"}


def _is_absolute_http_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _valid_authorization_servers(metadata: dict[str, Any], flow: str) -> list[str]:
    values: list[str] = []
    option = _flows._flow_option(metadata, flow)
    if isinstance(option, dict):
        raw = option.get("authorization_server")
        if _is_absolute_http_url(raw):
            values.append(str(raw).strip())
    issuer = metadata.get("authorization_server_issuer")
    if _is_absolute_http_url(issuer):
        values.append(str(issuer).strip())
    for source in (metadata, metadata.get("protected_resource_metadata")):
        if not isinstance(source, dict):
            continue
        raw_servers = source.get("authorization_servers")
        if not isinstance(raw_servers, list):
            continue
        for raw in raw_servers:
            if _is_absolute_http_url(raw):
                values.append(str(raw).strip())
    return list(dict.fromkeys(values))


def _potential_clients(metadata: dict[str, Any], flow: str) -> list[str]:
    option = _flows._flow_option(metadata, flow)
    if not isinstance(option, dict) or not isinstance(option.get("potential_clients"), list):
        return []
    return [str(item).strip().lower() for item in option["potential_clients"] if isinstance(item, str) and item.strip()]


def _uses_client_capability_selection(metadata: dict[str, Any]) -> bool:
    protected = metadata.get("protected_resource_metadata")
    hints = protected.get("authorization_hints") if isinstance(protected, dict) else metadata.get("authorization_hints")
    return "client_capability_based" in json.dumps(hints or {}, sort_keys=True).lower()


def _pkce_is_not_for_projectrai(metadata: dict[str, Any]) -> bool:
    clients = set(_potential_clients(metadata, "authorization_code_pkce"))
    return bool(clients) and not bool(clients & PROJECTRAI_CLIENT_NAMES)


def _has_device_code_option(metadata: dict[str, Any]) -> bool:
    return _flows._flow_option(metadata, "device_code") is not None


def _unsupported_pkce_message(metadata: dict[str, Any]) -> str:
    pkce_clients = _potential_clients(metadata, "authorization_code_pkce")
    device_clients = _potential_clients(metadata, "device_code")
    parts = [
        "This MCP provider advertises client-capability-based OAuth and does not list ProjectRAI as an authorization-code PKCE client.",
        "Use the MCP device-code flow or configure provider-issued ProjectRAI OAuth client credentials.",
    ]
    if pkce_clients:
        parts.append(f"PKCE clients advertised by provider: {', '.join(pkce_clients)}.")
    if device_clients:
        parts.append(f"Device-code clients advertised by provider: {', '.join(device_clients)}.")
    return " ".join(parts)


def _input_has_explicit_oauth(input_dto: _flows.McpOAuthStartInput) -> bool:
    return any(
        value
        for value in (
            input_dto.authorization_endpoint,
            input_dto.token_endpoint,
            input_dto.registration_endpoint,
            input_dto.authorization_server_issuer,
            input_dto.client_id,
        )
    )


def _config_advertises_oauth(config: dict[str, Any]) -> bool:
    diagnostic = config.get("mcp_discovery") if isinstance(config.get("mcp_discovery"), dict) else {}
    protected_metadata = config.get("mcp_resource_metadata")
    oauth = config.get("oauth") if isinstance(config.get("oauth"), dict) else {}
    if oauth.get("authorization_endpoint") and oauth.get("token_endpoint"):
        return True
    return has_mcp_oauth_challenge(
        diagnostic.get("www_authenticate"),
        protected_metadata if isinstance(protected_metadata, dict) else None,
    )


class ProviderAwareMcpOAuthStartUseCase(_flows.ProviderAwareMcpOAuthStartUseCase):
    def __init__(self, *, tool_repo: ToolRepository, executor: ToolExecutionPort, cipher: SecretCipherAdapter) -> None:
        super().__init__(tool_repo=tool_repo, executor=executor, cipher=cipher)
        self._safe_tool_repo = tool_repo
        self._safe_executor = executor

    async def execute(self, input_dto: _flows.McpOAuthStartInput) -> _flows.McpOAuthStartOutput:
        tool = await self._safe_tool_repo.get_by_id(input_dto.tool_id)
        if tool is None:
            raise ValueError("MCP tool provider not found")
        config = dict(tool.config or {})
        server = config.get("server") or {}
        server_url = str(server.get("url") or config.get("url") or "")
        if not server_url:
            raise ValueError("MCP server.url is required before OAuth connect")
        if not _input_has_explicit_oauth(input_dto) and not _config_advertises_oauth(config):
            raise ValueError(
                "This MCP server did not advertise a compatible OAuth flow. Configure the required API key or headers, or use the provider-managed connection details instead."
            )
        metadata = await McpOAuthMetadataResolver(self._safe_executor).resolve(
            server_url=server_url,
            authorization_endpoint=input_dto.authorization_endpoint,
            token_endpoint=input_dto.token_endpoint,
            registration_endpoint=input_dto.registration_endpoint,
            authorization_server_issuer=input_dto.authorization_server_issuer,
            timeout_ms=input_dto.timeout_ms,
        )
        if not input_dto.client_id and _uses_client_capability_selection(metadata) and _pkce_is_not_for_projectrai(metadata) and _has_device_code_option(metadata):
            raise ValueError(_unsupported_pkce_message(metadata))
        return await super().execute(input_dto)


_flows._flow_authorization_servers = _valid_authorization_servers

McpOAuthDevicePollInput = _flows.McpOAuthDevicePollInput
McpOAuthDevicePollOutput = _flows.McpOAuthDevicePollOutput
McpOAuthDevicePollUseCase = _flows.McpOAuthDevicePollUseCase
McpOAuthDeviceStartInput = _flows.McpOAuthDeviceStartInput
McpOAuthDeviceStartOutput = _flows.McpOAuthDeviceStartOutput
McpOAuthDeviceStartUseCase = _flows.McpOAuthDeviceStartUseCase
