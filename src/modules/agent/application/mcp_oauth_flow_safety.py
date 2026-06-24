from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from modules.agent.application import mcp_oauth_flows as _flows


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


_flows._flow_authorization_servers = _valid_authorization_servers

McpOAuthDevicePollInput = _flows.McpOAuthDevicePollInput
McpOAuthDevicePollOutput = _flows.McpOAuthDevicePollOutput
McpOAuthDevicePollUseCase = _flows.McpOAuthDevicePollUseCase
McpOAuthDeviceStartInput = _flows.McpOAuthDeviceStartInput
McpOAuthDeviceStartOutput = _flows.McpOAuthDeviceStartOutput
McpOAuthDeviceStartUseCase = _flows.McpOAuthDeviceStartUseCase
ProviderAwareMcpOAuthStartUseCase = _flows.ProviderAwareMcpOAuthStartUseCase
