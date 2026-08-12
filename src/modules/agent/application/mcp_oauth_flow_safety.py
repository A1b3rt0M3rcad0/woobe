from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from modules.agent.application import mcp_oauth_flows as _flows
from modules.agent.application.mcp_oauth import McpOAuthMetadataResolver
from modules.agent.application.mcp_readiness import has_valid_mcp_oauth_metadata
from modules.agent.application.ports import ToolExecutionPort
from modules.agent.domain.repositories import ToolRepository
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter

WOOBE_CLIENT_NAMES = {"woobe"}


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
    return [
        str(item).strip().lower()
        for item in option["potential_clients"]
        if isinstance(item, str) and item.strip()
    ]


def _uses_client_capability_selection(metadata: dict[str, Any]) -> bool:
    protected = metadata.get("protected_resource_metadata")
    hints = (
        protected.get("authorization_hints")
        if isinstance(protected, dict)
        else metadata.get("authorization_hints")
    )
    return "client_capability_based" in json.dumps(hints or {}, sort_keys=True).lower()


def _pkce_is_not_for_woobe(metadata: dict[str, Any]) -> bool:
    clients = set(_potential_clients(metadata, "authorization_code_pkce"))
    return bool(clients) and not bool(clients & WOOBE_CLIENT_NAMES)


def _has_device_code_option(metadata: dict[str, Any]) -> bool:
    return _flows._flow_option(metadata, "device_code") is not None


def _unsupported_pkce_message(metadata: dict[str, Any]) -> str:
    pkce_clients = _potential_clients(metadata, "authorization_code_pkce")
    device_clients = _potential_clients(metadata, "device_code")
    parts = [
        "This MCP provider advertises client-capability-based OAuth and does not list Woobe as an authorization-code PKCE client.",
        "Use the MCP device-code flow or configure provider-issued Woobe OAuth client credentials.",
    ]
    if pkce_clients:
        parts.append(f"PKCE clients advertised by provider: {', '.join(pkce_clients)}.")
    if device_clients:
        parts.append(
            f"Device-code clients advertised by provider: {', '.join(device_clients)}."
        )
    return " ".join(parts)


def _input_has_explicit_oauth(input_dto: _flows.McpOAuthStartInput) -> bool:
    return any(
        value
        for value in (
            input_dto.authorization_endpoint,
            input_dto.token_endpoint,
            input_dto.registration_endpoint,
            input_dto.authorization_server_issuer,
        )
    )


def _validated_discovery(config: dict[str, Any]) -> dict[str, Any]:
    discovery = config.get("mcp_oauth_discovery")
    if not isinstance(discovery, dict) or discovery.get("status") != "valid":
        return {}
    if not discovery.get("authorization_endpoint") or not discovery.get("token_endpoint"):
        return {}
    return discovery


def _cached_metadata(config: dict[str, Any]) -> dict[str, Any]:
    discovery = _validated_discovery(config)
    if not discovery:
        return {}
    return {
        "authorization_endpoint": discovery.get("authorization_endpoint"),
        "token_endpoint": discovery.get("token_endpoint"),
        "registration_endpoint": discovery.get("registration_endpoint"),
        "authorization_server_issuer": discovery.get("authorization_server_issuer"),
        "resource_metadata_url": discovery.get("resource_metadata_url"),
        "protected_resource_metadata": discovery.get("protected_resource_metadata"),
        "resource": (discovery.get("protected_resource_metadata") or {}).get("resource")
        if isinstance(discovery.get("protected_resource_metadata"), dict)
        else None,
    }


def _input_with_cached_metadata(
    input_dto: _flows.McpOAuthStartInput,
    config: dict[str, Any],
) -> _flows.McpOAuthStartInput:
    cached = _validated_discovery(config)
    if not cached:
        return input_dto
    return input_dto.model_copy(
        update={
            "authorization_endpoint": input_dto.authorization_endpoint
            or cached.get("authorization_endpoint"),
            "token_endpoint": input_dto.token_endpoint or cached.get("token_endpoint"),
            "registration_endpoint": input_dto.registration_endpoint
            or cached.get("registration_endpoint"),
            "authorization_server_issuer": input_dto.authorization_server_issuer
            or cached.get("authorization_server_issuer"),
        }
    )


def _invalid_discovery_message(config: dict[str, Any]) -> str:
    discovery = (
        config.get("mcp_oauth_discovery")
        if isinstance(config.get("mcp_oauth_discovery"), dict)
        else {}
    )
    status = str(discovery.get("status") or "")
    if status == "provider_managed":
        provider = str(discovery.get("provider") or "the provider")
        return (
            f"This MCP endpoint uses a connection managed by {provider}. "
            "Use the provider-issued connection details instead of starting direct MCP OAuth."
        )
    if status == "invalid_metadata":
        return (
            "This MCP server advertised OAuth, but Woobe could not validate both authorization_endpoint "
            "and token_endpoint. Refresh discovery, verify the MCP URL, or use the provider-managed connection flow."
        )
    return (
        "This MCP server did not expose a complete OAuth configuration. Configure the required API key or headers, "
        "or use the provider-managed connection details instead."
    )


class ProviderAwareMcpOAuthStartUseCase(_flows.ProviderAwareMcpOAuthStartUseCase):
    def __init__(
        self,
        *,
        tool_repo: ToolRepository,
        executor: ToolExecutionPort,
        cipher: SecretCipherAdapter,
    ) -> None:
        super().__init__(tool_repo=tool_repo, executor=executor, cipher=cipher)
        self._safe_tool_repo = tool_repo
        self._safe_executor = executor

    async def execute(
        self, input_dto: _flows.McpOAuthStartInput
    ) -> _flows.McpOAuthStartOutput:
        tool = await self._safe_tool_repo.get_by_id(input_dto.tool_id)
        if tool is None:
            raise ValueError("MCP tool provider not found")
        config = dict(tool.config or {})
        server = config.get("server") or {}
        server_url = str(server.get("url") or config.get("url") or "")
        if not server_url:
            raise ValueError("MCP server.url is required before OAuth connect")
        if not _input_has_explicit_oauth(
            input_dto
        ) and not has_valid_mcp_oauth_metadata(config):
            raise ValueError(_invalid_discovery_message(config))

        resolved_input = _input_with_cached_metadata(input_dto, config)
        metadata = _cached_metadata(config)
        if not metadata:
            try:
                metadata = await McpOAuthMetadataResolver(self._safe_executor).resolve(
                    server_url=server_url,
                    authorization_endpoint=resolved_input.authorization_endpoint,
                    token_endpoint=resolved_input.token_endpoint,
                    registration_endpoint=resolved_input.registration_endpoint,
                    authorization_server_issuer=resolved_input.authorization_server_issuer,
                    timeout_ms=resolved_input.timeout_ms,
                )
            except ValueError as exc:
                if "Could not discover MCP OAuth authorization and token endpoints" in str(
                    exc
                ):
                    raise ValueError(
                        "This MCP server advertised OAuth, but Woobe could not validate both authorization_endpoint and token_endpoint. Verify the MCP URL or use the provider-managed connection flow."
                    ) from exc
                raise

        if (
            not resolved_input.client_id
            and _uses_client_capability_selection(metadata)
            and _pkce_is_not_for_woobe(metadata)
            and _has_device_code_option(metadata)
        ):
            raise ValueError(_unsupported_pkce_message(metadata))
        return await super().execute(resolved_input)


_flows._flow_authorization_servers = _valid_authorization_servers

McpOAuthDevicePollInput = _flows.McpOAuthDevicePollInput
McpOAuthDevicePollOutput = _flows.McpOAuthDevicePollOutput
McpOAuthDevicePollUseCase = _flows.McpOAuthDevicePollUseCase
McpOAuthDeviceStartInput = _flows.McpOAuthDeviceStartInput
McpOAuthDeviceStartOutput = _flows.McpOAuthDeviceStartOutput
McpOAuthDeviceStartUseCase = _flows.McpOAuthDeviceStartUseCase
