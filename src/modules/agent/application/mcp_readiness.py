from __future__ import annotations

from typing import Any


def _permission_mode(item: dict[str, Any]) -> str:
    permission = item.get("permission") if isinstance(item, dict) else None
    mode = permission.get("mode") if isinstance(permission, dict) else None
    return mode if mode in {"allow", "deny", "review"} else "review"


def _has_device_code_hint(config: dict[str, Any], diagnostic: dict[str, Any]) -> bool:
    sources: list[Any] = [diagnostic.get("authorization_hints")]
    metadata = config.get("mcp_resource_metadata")
    if isinstance(metadata, dict):
        sources.append(metadata.get("authorization_hints"))
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
    return any("client_capability_based" in str(source).lower() for source in sources if source)


def build_mcp_readiness(config: dict[str, Any] | None, tool_status: Any | None = None) -> dict[str, Any]:
    cfg = dict(config or {})
    oauth = cfg.get("oauth") if isinstance(cfg.get("oauth"), dict) else {}
    diagnostic = cfg.get("mcp_discovery") if isinstance(cfg.get("mcp_discovery"), dict) else {}
    discovered_tools = cfg.get("discovered_tools") if isinstance(cfg.get("discovered_tools"), list) else []

    discovered_count = len(discovered_tools)
    exposed_count = sum(1 for item in discovered_tools if isinstance(item, dict) and _permission_mode(item) == "allow")
    oauth_status = str(oauth.get("status") or "disconnected")
    mcp_status = str(cfg.get("mcp_status") or diagnostic.get("status") or "disconnected")
    discovery_status = str(diagnostic.get("status") or "")
    http_status = diagnostic.get("http_status")
    provider_client_rejected = discovery_status == "provider_client_rejected" or (
        http_status == 401 and _provider_advertises_client_capability(cfg, diagnostic)
    )
    supports_device_code = _has_device_code_hint(cfg, diagnostic)

    if provider_client_rejected:
        state = "provider_not_supported"
        label = "Not supported"
        message = "This provider does not accept ProjectRAI with the normal OAuth flow. Use device code or provider-issued OAuth credentials."
        action = "device_code" if supports_device_code else "provider_credentials"
        can_use_tools = False
    elif oauth_status != "connected":
        state = "needs_connection"
        label = "Connect"
        message = "Connect this MCP provider before agents can use its tools."
        action = "connect"
        can_use_tools = False
    elif mcp_status == "ready" and discovered_count > 0 and exposed_count > 0:
        state = "ready"
        label = "Ready"
        message = f"{exposed_count} MCP tool{'s' if exposed_count != 1 else ''} available to agents."
        action = "configure_permissions"
        can_use_tools = True
    elif mcp_status == "ready" and discovered_count > 0:
        state = "needs_permission"
        label = "Needs permission"
        message = "Tools were found, but none are exposed to agents yet."
        action = "configure_permissions"
        can_use_tools = False
    elif mcp_status == "ready":
        state = "no_tools"
        label = "No tools"
        message = "The MCP server connected, but did not expose any tools."
        action = "refresh"
        can_use_tools = False
    elif http_status == 401:
        state = "token_rejected"
        label = "Token rejected"
        message = "The provider rejected the current token. Disconnect and reconnect with an accepted OAuth client."
        action = "disconnect"
        can_use_tools = False
    else:
        state = "discovery_failed" if diagnostic else "not_ready"
        label = "Not ready"
        message = "MCP tools are not available yet. Connect or refresh discovery."
        action = "connect" if oauth_status != "connected" else "refresh"
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
        "needs_provider_client": state == "provider_not_supported",
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
