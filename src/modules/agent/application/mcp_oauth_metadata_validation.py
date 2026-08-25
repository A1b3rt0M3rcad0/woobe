from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

from modules.agent.application.interfaces.ports import ExecutionResult, ToolExecutionPort

MANAGED_MCP_HOST_SUFFIXES = {
    ".run.tools": "smithery",
}


@dataclass
class McpOAuthMetadataValidation:
    status: str
    advertised: bool
    provider: str | None = None
    resource_metadata_url: str | None = None
    authorization_server_issuer: str | None = None
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    registration_endpoint: str | None = None
    protected_resource_metadata: dict[str, Any] | None = None
    error: str | None = None
    checked_urls: list[str] = field(default_factory=list)


def _origin_from_url(value: str) -> str:
    parsed = urlparse(value)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not host:
        raise ValueError("MCP server URL must be an absolute HTTP URL")
    netloc = host
    if parsed.port:
        netloc = f"{host}:{parsed.port}"
    return f"{scheme}://{netloc}"


def _absolute_url(value: Any, base_url: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    resolved = urljoin(base_url.rstrip("/") + "/", value.strip())
    parsed = urlparse(resolved)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return resolved


def _body(result: ExecutionResult) -> Any:
    output = result.output or {}
    value = output.get("body") if isinstance(output, dict) else None
    if value is None:
        value = result.body
    if isinstance(value, dict) and isinstance(value.get("raw"), str):
        value = value["raw"]
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _parse_www_authenticate_params(header: str | None) -> tuple[str, dict[str, str]]:
    if not header:
        return "", {}
    text = header.strip()
    if not text:
        return "", {}
    parts = text.split(None, 1)
    scheme = parts[0].lower()
    text = parts[1] if len(parts) > 1 else ""
    params: dict[str, str] = {}
    index = 0
    while index < len(text):
        while index < len(text) and text[index] in " ,":
            index += 1
        key_start = index
        while index < len(text) and text[index] not in "=, ":
            index += 1
        key = text[key_start:index].strip().lower()
        while index < len(text) and text[index] == " ":
            index += 1
        if not key or index >= len(text) or text[index] != "=":
            while index < len(text) and text[index] != ",":
                index += 1
            continue
        index += 1
        while index < len(text) and text[index] == " ":
            index += 1
        if index < len(text) and text[index] == '"':
            index += 1
            escaped = False
            value_chars: list[str] = []
            while index < len(text):
                char = text[index]
                if escaped:
                    value_chars.append(char)
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    break
                else:
                    value_chars.append(char)
                index += 1
            params[key] = "".join(value_chars)
            if index < len(text) and text[index] == '"':
                index += 1
        else:
            value_start = index
            while index < len(text) and text[index] != ",":
                index += 1
            params[key] = text[value_start:index].strip()
    return scheme, params


def _managed_provider_for_url(server_url: str) -> str | None:
    host = (urlparse(server_url).hostname or "").lower()
    for suffix, provider in MANAGED_MCP_HOST_SUFFIXES.items():
        if host == suffix.lstrip(".") or host.endswith(suffix):
            return provider
    return None


def _well_known_url(issuer: str, suffix: str) -> str:
    parsed = urlparse(issuer.rstrip("/"))
    path = (parsed.path or "").rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}/.well-known/{suffix}{path}"


async def _get_json(
    executor: ToolExecutionPort,
    url: str,
    *,
    timeout_ms: int,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        result = await executor.execute(
            method="GET",
            url=url,
            headers={"Accept": "application/json"},
            timeout_ms=timeout_ms,
        )
    except Exception as exc:
        return None, str(exc)
    if not result.success:
        return None, result.error or f"HTTP {result.status_code or 'error'}"
    value = _body(result)
    if not isinstance(value, dict):
        return None, "OAuth metadata response is not a JSON object"
    return value, None


def _invalid_validation(
    *,
    server_url: str,
    resource_metadata_url: str | None,
    protected_resource_metadata: dict[str, Any] | None,
    error: str,
    checked_urls: list[str],
) -> McpOAuthMetadataValidation:
    provider = _managed_provider_for_url(server_url)
    return McpOAuthMetadataValidation(
        status="provider_managed" if provider else "invalid_metadata",
        advertised=True,
        provider=provider,
        resource_metadata_url=resource_metadata_url,
        protected_resource_metadata=protected_resource_metadata,
        error=error,
        checked_urls=checked_urls,
    )


async def validate_mcp_oauth_metadata(
    executor: ToolExecutionPort,
    *,
    server_url: str,
    www_authenticate: str | None,
    timeout_ms: int,
) -> McpOAuthMetadataValidation:
    scheme, params = _parse_www_authenticate_params(www_authenticate)
    raw_resource_metadata_url = params.get("resource_metadata") if scheme == "bearer" else None
    if not raw_resource_metadata_url:
        return McpOAuthMetadataValidation(status="not_advertised", advertised=False)

    server_origin = _origin_from_url(server_url)
    resource_metadata_url = _absolute_url(raw_resource_metadata_url, server_origin)
    if not resource_metadata_url:
        return _invalid_validation(
            server_url=server_url,
            resource_metadata_url=None,
            protected_resource_metadata=None,
            error="The MCP OAuth resource_metadata URL is not a valid HTTP URL.",
            checked_urls=[],
        )

    checked_urls = [resource_metadata_url]
    resource_metadata, resource_error = await _get_json(
        executor,
        resource_metadata_url,
        timeout_ms=timeout_ms,
    )
    if not isinstance(resource_metadata, dict):
        return _invalid_validation(
            server_url=server_url,
            resource_metadata_url=resource_metadata_url,
            protected_resource_metadata=None,
            error=f"Could not load MCP protected resource metadata: {resource_error or 'invalid response'}.",
            checked_urls=checked_urls,
        )

    metadata_origin = _origin_from_url(resource_metadata_url)
    authorization_servers = [
        resolved
        for raw in resource_metadata.get("authorization_servers", [])
        if (resolved := _absolute_url(raw, metadata_origin))
    ] if isinstance(resource_metadata.get("authorization_servers"), list) else []
    normalized_resource_metadata = {
        key: value
        for key, value in {
            "resource": _absolute_url(resource_metadata.get("resource"), metadata_origin),
            "authorization_servers": authorization_servers,
            "scopes_supported": resource_metadata.get("scopes_supported") if isinstance(resource_metadata.get("scopes_supported"), list) else [],
            "bearer_methods_supported": resource_metadata.get("bearer_methods_supported") if isinstance(resource_metadata.get("bearer_methods_supported"), list) else [],
            "authorization_hints": resource_metadata.get("authorization_hints") if isinstance(resource_metadata.get("authorization_hints"), dict) else None,
        }.items()
        if value not in (None, [], {})
    }

    if not authorization_servers:
        return _invalid_validation(
            server_url=server_url,
            resource_metadata_url=resource_metadata_url,
            protected_resource_metadata=normalized_resource_metadata,
            error="The MCP protected resource metadata did not provide authorization_servers.",
            checked_urls=checked_urls,
        )

    last_error: str | None = None
    for issuer in authorization_servers:
        for metadata_url in (
            _well_known_url(issuer, "oauth-authorization-server"),
            _well_known_url(issuer, "openid-configuration"),
        ):
            if metadata_url not in checked_urls:
                checked_urls.append(metadata_url)
            authorization_metadata, metadata_error = await _get_json(
                executor,
                metadata_url,
                timeout_ms=timeout_ms,
            )
            if not isinstance(authorization_metadata, dict):
                last_error = metadata_error or "invalid authorization server metadata"
                continue
            metadata_base = _absolute_url(authorization_metadata.get("issuer"), issuer) or issuer
            authorization_endpoint = _absolute_url(authorization_metadata.get("authorization_endpoint"), metadata_base)
            token_endpoint = _absolute_url(authorization_metadata.get("token_endpoint"), metadata_base)
            if not authorization_endpoint or not token_endpoint:
                last_error = "authorization server metadata did not provide both authorization_endpoint and token_endpoint"
                continue
            return McpOAuthMetadataValidation(
                status="valid",
                advertised=True,
                resource_metadata_url=resource_metadata_url,
                authorization_server_issuer=metadata_base,
                authorization_endpoint=authorization_endpoint,
                token_endpoint=token_endpoint,
                registration_endpoint=_absolute_url(authorization_metadata.get("registration_endpoint"), metadata_base),
                protected_resource_metadata=normalized_resource_metadata,
                checked_urls=checked_urls,
            )

    return _invalid_validation(
        server_url=server_url,
        resource_metadata_url=resource_metadata_url,
        protected_resource_metadata=normalized_resource_metadata,
        error=(
            "The server advertised MCP OAuth, but no authorization server metadata exposed both "
            f"authorization_endpoint and token_endpoint. Last error: {last_error or 'metadata unavailable'}."
        ),
        checked_urls=checked_urls,
    )


def validated_mcp_status(validation: McpOAuthMetadataValidation) -> str:
    if validation.status == "valid":
        return "oauth_required"
    if validation.status == "provider_managed":
        return "provider_managed"
    if validation.status == "invalid_metadata":
        return "oauth_metadata_invalid"
    return "needs_credentials"


def write_mcp_oauth_validation(
    config: dict[str, Any],
    validation: McpOAuthMetadataValidation,
    *,
    checked_at: str,
) -> None:
    payload = {
        "status": validation.status,
        "advertised": validation.advertised,
        "provider": validation.provider,
        "resource_metadata_url": validation.resource_metadata_url,
        "authorization_server_issuer": validation.authorization_server_issuer,
        "authorization_endpoint": validation.authorization_endpoint,
        "token_endpoint": validation.token_endpoint,
        "registration_endpoint": validation.registration_endpoint,
        "protected_resource_metadata": validation.protected_resource_metadata,
        "error": validation.error,
        "checked_urls": validation.checked_urls,
        "checked_at": checked_at,
    }
    config["mcp_oauth_discovery"] = {
        key: value for key, value in payload.items() if value not in (None, [], {})
    }
    if validation.status == "valid":
        config["mcp_resource_metadata"] = validation.protected_resource_metadata or {}
        config.pop("oauth_discovery_error", None)
    else:
        config.pop("mcp_resource_metadata", None)
        if validation.error:
            config["oauth_discovery_error"] = validation.error


def oauth_validation_diagnostic_fields(
    validation: McpOAuthMetadataValidation | None,
) -> dict[str, Any]:
    if validation is None:
        return {}
    return {
        "oauth_metadata_status": validation.status,
        "managed_provider": validation.provider,
        "resource_metadata_url": validation.resource_metadata_url,
        "authorization_server_issuer": validation.authorization_server_issuer,
        "authorization_endpoint": validation.authorization_endpoint,
        "token_endpoint": validation.token_endpoint,
        "oauth_metadata_error": validation.error,
    }
