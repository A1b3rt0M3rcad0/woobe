from __future__ import annotations

from typing import Any


CREDENTIAL_REQUIRED_STATES = {"needs_credentials", "unauthorized"}
TOKEN_REJECTED_STATES = {"token_invalid", "token_rejected"}
PROVIDER_REJECTED_STATES = {"provider_client_rejected"}
PROVIDER_MANAGED_STATES = {"provider_managed"}
OAUTH_METADATA_INVALID_STATES = {"oauth_metadata_invalid"}
INVALID_ENDPOINT_STATES = {"invalid_endpoint"}
UNAVAILABLE_STATES = {"unavailable"}
SCOPE_DENIED_STATES = {"scope_denied"}


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


def has_mcp_oauth_challenge(
    www_authenticate: str | None,
    protected_resource_metadata: dict[str, Any] | None = None,
) -> bool:
    scheme, params = _parse_www_authenticate_params(www_authenticate)
    if scheme == "bearer" and bool(params.get("resource_metadata")):
        return True
    if not isinstance(protected_resource_metadata, dict):
        return False
    authorization_servers = protected_resource_metadata.get("authorization_servers")
    return isinstance(authorization_servers, list) and any(
        isinstance(value, str) and value.strip() for value in authorization_servers
    )


def has_valid_mcp_oauth_metadata(config: dict[str, Any] | None) -> bool:
    cfg = config or {}
    oauth = cfg.get("oauth") if isinstance(cfg.get("oauth"), dict) else {}
    if oauth.get("authorization_endpoint") and oauth.get("token_endpoint"):
        return True
    discovery = cfg.get("mcp_oauth_discovery") if isinstance(cfg.get("mcp_oauth_discovery"), dict) else {}
    return (
        discovery.get("status") == "valid"
        and bool(discovery.get("authorization_endpoint"))
        and bool(discovery.get("token_endpoint"))
    )


def classify_mcp_discovery_status(
    *,
    has_tools: bool,
    error: str | None,
    http_status: int | None,
    www_authenticate: str | None,
    oauth_connected: bool = False,
    protected_resource_metadata: dict[str, Any] | None = None,
) -> str:
    if not error and has_tools:
        return "ready"
    if http_status == 401:
        if oauth_connected:
            return "token_invalid"
        if has_mcp_oauth_challenge(www_authenticate, protected_resource_metadata):
            return "oauth_required"
        return "needs_credentials"
    if http_status == 403:
        return "scope_denied"
    if http_status in {404, 405}:
        return "invalid_endpoint"
    if http_status is not None and http_status >= 500:
        return "unavailable"
    if error:
        return "discovery_failed"
    return "empty"


def _permission_mode(item: dict[str, Any]) -> str:
    permission = item.get("permission") if isinstance(item, dict) else None
    mode = permission.get("mode") if isinstance(permission, dict) else None
    return mode if mode in {"allow", "deny", "review"} else "review"


def _has_device_code_hint(config: dict[str, Any], diagnostic: dict[str, Any]) -> bool:
    sources: list[Any] = [diagnostic.get("authorization_hints")]
    metadata = config.get("mcp_resource_metadata")
    if isinstance(metadata, dict):
        sources.append(metadata.get("authorization_hints"))
    oauth_discovery = config.get("mcp_oauth_discovery")
    if isinstance(oauth_discovery, dict):
        protected = oauth_discovery.get("protected_resource_metadata")
        if isinstance(protected, dict):
            sources.append(protected.get("authorization_hints"))
    for source in sources:
        if not isinstance(source, dict):
            continue
        text = str(source).lower()
        if "device_code" in text:
            return True
    return False


def _provider_advertises_client_capability(config: dict[str, Any], diagnostic: dict[str, Any]) -> bool:
    sources: list[Any] = [diagnostic.get("authorization_hints")]
    metadata = config.get("mcp_resource_metadata")
    if isinstance(metadata, dict):
        sources.append(metadata.get("authorization_hints"))
    oauth_discovery = config.get("mcp_oauth_discovery")
    if isinstance(oauth_discovery, dict):
        protected = oauth_discovery.get("protected_resource_metadata")
        if isinstance(protected, dict):
            sources.append(protected.get("authorization_hints"))
    return any("client_capability_based" in str(source).lower() for source in sources if source)


def _has_auth_challenge(config: dict[str, Any], diagnostic: dict[str, Any]) -> bool:
    return has_valid_mcp_oauth_metadata(config)


def _has_loaded_tools(discovered_count: int) -> bool:
    return discovered_count > 0


def build_mcp_readiness(config: dict[str, Any] | None, tool_status: Any | None = None) -> dict[str, Any]:
    cfg = dict(config or {})
    oauth = cfg.get("oauth") if isinstance(cfg.get("oauth"), dict) else {}
    diagnostic = cfg.get("mcp_discovery") if isinstance(cfg.get("mcp_discovery"), dict) else {}
    oauth_discovery = cfg.get("mcp_oauth_discovery") if isinstance(cfg.get("mcp_oauth_discovery"), dict) else {}
    discovered_tools = cfg.get("discovered_tools") if isinstance(cfg.get("discovered_tools"), list) else []

    discovered_count = len(discovered_tools)
    exposed_count = sum(1 for item in discovered_tools if isinstance(item, dict) and _permission_mode(item) == "allow")
    oauth_status = str(oauth.get("status") or "disconnected")
    mcp_status = str(cfg.get("mcp_status") or diagnostic.get("status") or "")
    discovery_status = str(diagnostic.get("status") or "")
    oauth_metadata_status = str(oauth_discovery.get("status") or diagnostic.get("oauth_metadata_status") or "")
    http_status = diagnostic.get("http_status")
    supports_device_code = _has_device_code_hint(cfg, diagnostic)
    auth_required = _has_auth_challenge(cfg, diagnostic)
    credentials_required = (
        mcp_status in CREDENTIAL_REQUIRED_STATES
        or discovery_status in CREDENTIAL_REQUIRED_STATES
        or (http_status == 401 and oauth_status != "connected" and not has_mcp_oauth_challenge(diagnostic.get("www_authenticate")))
    )
    token_rejected = (http_status == 401 and oauth_status == "connected") or mcp_status in TOKEN_REJECTED_STATES or discovery_status in TOKEN_REJECTED_STATES
    provider_client_rejected = discovery_status in PROVIDER_REJECTED_STATES or mcp_status in PROVIDER_REJECTED_STATES or (
        http_status == 401 and _provider_advertises_client_capability(cfg, diagnostic)
    )
    provider_managed = (
        mcp_status in PROVIDER_MANAGED_STATES
        or discovery_status in PROVIDER_MANAGED_STATES
        or oauth_metadata_status == "provider_managed"
    )
    oauth_metadata_invalid = (
        mcp_status in OAUTH_METADATA_INVALID_STATES
        or discovery_status in OAUTH_METADATA_INVALID_STATES
        or oauth_metadata_status == "invalid_metadata"
        or (mcp_status == "oauth_required" and oauth_status != "connected" and not auth_required)
    )
    scope_denied = mcp_status in SCOPE_DENIED_STATES or discovery_status in SCOPE_DENIED_STATES
    invalid_endpoint = mcp_status in INVALID_ENDPOINT_STATES or discovery_status in INVALID_ENDPOINT_STATES
    unavailable = mcp_status in UNAVAILABLE_STATES or discovery_status in UNAVAILABLE_STATES

    if provider_client_rejected:
        state = "provider_not_supported"
        label = "Provider setup needed"
        message = "This provider does not accept the normal OAuth flow. Use device code or provider-issued OAuth credentials."
        action = "device_code" if supports_device_code else "provider_credentials"
        can_use_tools = False
    elif token_rejected:
        state = "token_rejected"
        label = "Token rejected"
        message = "The provider rejected the current OAuth token. Disconnect and reconnect with an accepted OAuth client."
        action = "disconnect"
        can_use_tools = False
    elif provider_managed:
        provider = str(oauth_discovery.get("provider") or diagnostic.get("managed_provider") or "provider")
        state = "provider_managed"
        label = "Managed connection required"
        message = f"This MCP endpoint is managed by {provider}. Use the provider-issued connection details instead of direct MCP OAuth discovery."
        action = "provider_credentials"
        can_use_tools = False
    elif oauth_metadata_invalid:
        state = "oauth_metadata_invalid"
        label = "OAuth metadata invalid"
        message = "The server advertised OAuth, but Woobe could not validate both authorization_endpoint and token_endpoint. Verify the MCP URL or use the provider-managed connection flow."
        action = "review_provider"
        can_use_tools = False
    elif oauth_status != "connected" and auth_required:
        state = "needs_connection"
        label = "Connect"
        message = "This MCP provider exposed a complete OAuth configuration. Connect before loading its tools."
        action = "connect"
        can_use_tools = False
    elif credentials_required:
        state = "needs_credentials"
        label = "Credentials required"
        message = "The server rejected the request without advertising MCP OAuth. Configure the required API key or headers, or use the provider-managed connection URL."
        action = "configure_credentials"
        can_use_tools = False
    elif scope_denied:
        state = "scope_denied"
        label = "Permission denied"
        message = "The server accepted the credential but denied access. Review the configured scopes, permissions, or API key policy."
        action = "configure_credentials"
        can_use_tools = False
    elif invalid_endpoint:
        state = "invalid_endpoint"
        label = "Invalid endpoint"
        message = "The host responded, but this URL is not accepting MCP requests. Verify the MCP path, commonly /mcp."
        action = "edit_endpoint"
        can_use_tools = False
    elif unavailable:
        state = "unavailable"
        label = "Unavailable"
        message = "The MCP server is temporarily unavailable. Retry discovery after the provider recovers."
        action = "refresh"
        can_use_tools = False
    elif _has_loaded_tools(discovered_count) and exposed_count > 0:
        state = "ready"
        label = "Ready"
        message = f"{exposed_count} MCP tool{'s' if exposed_count != 1 else ''} available to agents."
        action = "manage_tools"
        can_use_tools = True
    elif _has_loaded_tools(discovered_count):
        state = "needs_permission"
        label = "Needs permission"
        message = "Tools were found, but none are exposed to agents yet."
        action = "configure_permissions"
        can_use_tools = False
    elif mcp_status in {"ready", "empty", "no_tools"}:
        state = "no_tools"
        label = "No tools"
        message = "The MCP server connected, but did not expose any tools."
        action = "refresh"
        can_use_tools = False
    elif diagnostic or mcp_status == "discovery_failed":
        state = "discovery_failed"
        label = "Discovery failed"
        message = "Woobe could not complete MCP discovery. Retry or review the endpoint and configured headers."
        action = "refresh"
        can_use_tools = False
    else:
        state = "needs_discovery"
        label = "Load tools"
        message = "Load this MCP provider to see which tools it exposes."
        action = "refresh"
        can_use_tools = False

    return {
        "state": state,
        "label": label,
        "message": message,
        "action": action,
        "can_use_tools": can_use_tools,
        "oauth_connected": oauth_status == "connected",
        "mcp_ready": mcp_status == "ready",
        "discovered_count": discovered_count,
        "exposed_count": exposed_count,
        "supports_device_code": supports_device_code,
        "needs_provider_client": state in {"provider_not_supported", "provider_managed"},
    }


def with_mcp_readiness(config: dict[str, Any] | None, tool_status: Any | None = None) -> dict[str, Any] | None:
    if config is None:
        return None
    cfg = dict(config)
    is_mcp = str(cfg.get("protocol") or "").lower() == "mcp" or "mcp_discovery" in cfg or "discovered_tools" in cfg
    if not is_mcp:
        return cfg
    cfg["mcp_readiness"] = build_mcp_readiness(cfg, tool_status)
    return cfg
