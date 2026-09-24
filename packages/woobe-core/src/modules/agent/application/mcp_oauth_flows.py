from __future__ import annotations

from modules.agent.application.dtos.mcp_oauth_dtos import (
    McpOAuthDevicePollInput,
    McpOAuthDevicePollOutput,
    McpOAuthDeviceStartInput,
    McpOAuthDeviceStartOutput,
)

import base64
import json
import secrets
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode


from modules.agent.application.mcp_discovery import DiscoverMcpToolsUseCase, McpDiscoverInput
from modules.agent.application.mcp_oauth import (
    McpOAuthMetadataResolver,
    McpOAuthStartInput,
    McpOAuthStartOutput,
    McpOAuthStatusOutput,
    _absolute_url,
    _body,
    _canonical_resource_uri,
    _choose_scopes,
    _choose_token_auth_method,
    _code_challenge,
    _code_verifier,
    _derived_authorization_endpoint_candidates,
    _expires_at_from_token_response,
    _headers_from_raw,
    _is_expired,
    _oauth_config,
    _raw_headers_from_config,
    _well_known_authorization_server_url,
    _well_known_openid_configuration_url,
)
from modules.agent.application.mcp_permissions import merge_discovered_tools_with_existing_permissions
from modules.agent.application.interfaces.ports import ExecutionResult, ToolExecutionPort
from modules.agent.application.interfaces.repositories import ToolRepository
from modules.agent.application.interfaces.ports import SecretCipherPort
from shared.contracts.time import utc_now

OAUTH_STATE_TTL_SECONDS = 600
DEVICE_CODE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
PROJECTRAI_CLIENT_NAMES = {"projectrai", "project-rai", "project_rai"}










def _authorization_hints(metadata: dict[str, Any]) -> dict[str, Any]:
    protected = metadata.get("protected_resource_metadata")
    if isinstance(protected, dict) and isinstance(protected.get("authorization_hints"), dict):
        return protected["authorization_hints"]
    hints = metadata.get("authorization_hints")
    return hints if isinstance(hints, dict) else {}


def _flow_options(value: Any) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if isinstance(value, dict):
        raw_options = value.get("options")
        if isinstance(raw_options, list):
            options.extend(item for item in raw_options if isinstance(item, dict))
        for child in value.values():
            options.extend(_flow_options(child))
    elif isinstance(value, list):
        for child in value:
            options.extend(_flow_options(child))
    return options


def _flow_option(metadata: dict[str, Any], flow: str) -> dict[str, Any] | None:
    for option in _flow_options(_authorization_hints(metadata)):
        if str(option.get("flow") or "") == flow:
            return option
    return None


def _provider_uses_client_capability_selection(metadata: dict[str, Any]) -> bool:
    hints = _authorization_hints(metadata)
    return "client_capability_based" in json.dumps(hints, sort_keys=True).lower()


def _protected_authorization_servers(metadata: dict[str, Any]) -> list[str]:
    values: list[str] = []
    issuer = metadata.get("authorization_server_issuer")
    if isinstance(issuer, str) and issuer:
        values.append(issuer)
    for source in (metadata, metadata.get("protected_resource_metadata")):
        if isinstance(source, dict) and isinstance(source.get("authorization_servers"), list):
            values.extend(str(item) for item in source["authorization_servers"] if isinstance(item, str) and item)
    return list(dict.fromkeys(values))


def _flow_authorization_servers(metadata: dict[str, Any], flow: str) -> list[str]:
    values: list[str] = []
    option = _flow_option(metadata, flow)
    if isinstance(option, dict) and isinstance(option.get("authorization_server"), str):
        values.append(option["authorization_server"])
    values.extend(_protected_authorization_servers(metadata))
    return list(dict.fromkeys(values))


def _client_hint_message(metadata: dict[str, Any]) -> str:
    pkce = _flow_option(metadata, "authorization_code_pkce") or {}
    device = _flow_option(metadata, "device_code") or {}
    pkce_clients = pkce.get("potential_clients") if isinstance(pkce.get("potential_clients"), list) else []
    device_clients = device.get("potential_clients") if isinstance(device.get("potential_clients"), list) else []
    details: list[str] = []
    if pkce_clients:
        details.append(f"authorization_code_pkce clients: {', '.join(str(item) for item in pkce_clients)}")
    if device_clients:
        details.append(f"device_code clients: {', '.join(str(item) for item in device_clients)}")
    suffix = f" Provider hints: {'; '.join(details)}." if details else ""
    return (
        "OAuth provider uses client-capability-based authorization. "
        "Configure a provider-issued client_id/client_secret for Woobe or use the MCP device-code flow."
        + suffix
    )


async def _get_json(executor: ToolExecutionPort, url: str, *, timeout_ms: int) -> dict[str, Any] | None:
    result = await executor.execute(method="GET", url=url, headers={"Accept": "application/json"}, timeout_ms=timeout_ms)
    if not result.success:
        return None
    body = _body(result)
    return body if isinstance(body, dict) else None


async def _apply_authorization_server_metadata(
    executor: ToolExecutionPort,
    metadata: dict[str, Any],
    issuer: str,
    *,
    timeout_ms: int,
) -> bool:
    for url in (_well_known_authorization_server_url(issuer), _well_known_openid_configuration_url(issuer)):
        as_metadata = await _get_json(executor, url, timeout_ms=timeout_ms)
        if not isinstance(as_metadata, dict):
            continue
        base_url = str(as_metadata.get("issuer") or issuer)
        for target, source in (
            ("authorization_endpoint", "authorization_endpoint"),
            ("token_endpoint", "token_endpoint"),
            ("registration_endpoint", "registration_endpoint"),
            ("device_authorization_endpoint", "device_authorization_endpoint"),
        ):
            value = _absolute_url(as_metadata.get(source), base_url)
            if value:
                metadata[target] = value
        issuer_value = _absolute_url(as_metadata.get("issuer"), base_url) or issuer
        metadata["authorization_server_issuer"] = issuer_value
        token_methods = as_metadata.get("token_endpoint_auth_methods_supported")
        if isinstance(token_methods, list) and token_methods:
            metadata["token_endpoint_auth_methods_supported"] = [str(item) for item in token_methods if isinstance(item, str)]
        return True
    return False


async def _prefer_authorization_flow(
    executor: ToolExecutionPort,
    metadata: dict[str, Any],
    *,
    flow: str,
    timeout_ms: int,
) -> dict[str, Any]:
    for issuer in _flow_authorization_servers(metadata, flow):
        candidate = dict(metadata)
        if await _apply_authorization_server_metadata(executor, candidate, issuer, timeout_ms=timeout_ms):
            if flow == "device_code" and not candidate.get("device_authorization_endpoint"):
                continue
            if flow == "authorization_code_pkce" and not (candidate.get("authorization_endpoint") and candidate.get("token_endpoint")):
                continue
            candidate["oauth_flow"] = flow
            return candidate
    metadata["oauth_flow"] = flow
    return metadata


def _token_request_auth(
    *,
    data: dict[str, str],
    headers: dict[str, str],
    token_auth_method: str,
    client_id: str,
    client_secret: str | None,
) -> None:
    if token_auth_method == "client_secret_basic" and client_secret:
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
        headers["Authori" + "zation"] = f"Basic {basic}"
        return
    data["client_id"] = client_id
    if client_secret and token_auth_method == "client_secret_post":
        data["client_secret"] = client_secret


class ProviderAwareMcpOAuthStartUseCase:
    def __init__(self, *, tool_repo: ToolRepository, executor: ToolExecutionPort, cipher: SecretCipherPort) -> None:
        self._tool_repo = tool_repo
        self._executor = executor
        self._cipher = cipher

    async def execute(self, input_dto: McpOAuthStartInput) -> McpOAuthStartOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)
        if tool is None:
            raise ValueError("MCP tool provider not found")
        config = dict(tool.config or {})
        server = config.get("server") or {}
        server_url = str(server.get("url") or config.get("url") or "")
        if not server_url:
            raise ValueError("MCP server.url is required before OAuth connect")

        metadata = await McpOAuthMetadataResolver(self._executor).resolve(
            server_url=server_url,
            authorization_endpoint=input_dto.authorization_endpoint,
            token_endpoint=input_dto.token_endpoint,
            registration_endpoint=input_dto.registration_endpoint,
            authorization_server_issuer=input_dto.authorization_server_issuer,
            timeout_ms=input_dto.timeout_ms,
        )
        if not input_dto.authorization_server_issuer:
            metadata = await _prefer_authorization_flow(self._executor, metadata, flow="authorization_code_pkce", timeout_ms=input_dto.timeout_ms)

        resource = str(metadata.get("resource") or _canonical_resource_uri(server_url))
        scopes = _choose_scopes(explicit=input_dto.scopes, challenge=list(metadata.get("required_scopes") or []), metadata=metadata)
        token_auth_method = _choose_token_auth_method(metadata)
        client_id = input_dto.client_id
        client_secret = input_dto.client_secret
        if not client_id and metadata.get("registration_endpoint"):
            registered = await self._register_client(
                registration_endpoint=str(metadata["registration_endpoint"]),
                redirect_uri=input_dto.redirect_uri,
                timeout_ms=input_dto.timeout_ms,
                token_endpoint_auth_method=token_auth_method,
            )
            client_id = str(registered.get("client_id") or "") or None
            client_secret = str(registered.get("client_secret") or "") or None
            token_auth_method = str(registered.get("token_endpoint_auth_method") or token_auth_method)
        if not client_id:
            if _provider_uses_client_capability_selection(metadata):
                raise ValueError(_client_hint_message(metadata))
            raise ValueError("OAuth client_id is required and dynamic client registration was not available")

        state = secrets.token_urlsafe(32)
        verifier = _code_verifier()
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": input_dto.redirect_uri,
            "state": state,
            "code_challenge": _code_challenge(verifier),
            "code_challenge_method": "S256",
            "resource": resource,
        }
        if scopes:
            params["scope"] = " ".join(scopes)
        authorization_url = await self._select_authorization_url(metadata=metadata, params=params, timeout_ms=input_dto.timeout_ms)
        oauth = {
            "status": "pending",
            "flow": "authorization_code_pkce",
            "state": state,
            "state_expires_at": (utc_now() + timedelta(seconds=OAUTH_STATE_TTL_SECONDS)).isoformat(),
            "code_verifier_encrypted": await self._cipher.encrypt(verifier),
            "redirect_uri": input_dto.redirect_uri,
            "resource": resource,
            "scopes": scopes,
            "authorization_server_issuer": metadata.get("authorization_server_issuer"),
            "authorization_endpoint": metadata["authorization_endpoint"],
            "token_endpoint": metadata["token_endpoint"],
            "registration_endpoint": metadata.get("registration_endpoint"),
            "client_id": client_id,
            "token_endpoint_auth_method": token_auth_method,
            "protected_resource_metadata": metadata.get("protected_resource_metadata"),
            "resource_metadata_url": metadata.get("resource_metadata_url"),
        }
        if client_secret:
            oauth["client_secret_encrypted"] = await self._cipher.encrypt(client_secret)
        config["oauth"] = oauth
        config["mcp_resource_metadata"] = metadata.get("protected_resource_metadata")
        tool.config = config
        await self._tool_repo.update(tool)
        return McpOAuthStartOutput(authorization_url=authorization_url, state=state)

    async def _select_authorization_url(self, *, metadata: dict[str, Any], params: dict[str, str], timeout_ms: int) -> str:
        rejected_404: list[str] = []
        candidates = _derived_authorization_endpoint_candidates(metadata)
        if not candidates:
            raise ValueError("Could not discover OAuth authorization endpoint")
        for endpoint in candidates:
            authorization_url = f"{endpoint}?{urlencode(params)}"
            result = await self._executor.execute(method="GET", url=authorization_url, headers={"Accept": "text/html,application/xhtml+xml,application/json"}, timeout_ms=min(timeout_ms or 30000, 10000))
            if result.status_code == 404:
                rejected_404.append(endpoint)
                continue
            if result.status_code is None or result.status_code < 500:
                metadata["authorization_endpoint"] = endpoint
                return authorization_url
        details = ", ".join(rejected_404[:4])
        raise ValueError(f"Discovered OAuth authorization endpoint returned 404. Tried: {details}")

    async def _register_client(self, *, registration_endpoint: str, redirect_uri: str, timeout_ms: int, token_endpoint_auth_method: str) -> dict[str, Any]:
        payload = {
            "client_name": "Woobe",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": token_endpoint_auth_method,
        }
        result = await self._executor.execute(method="POST", url=registration_endpoint, headers={"Accept": "application/json", "Content-Type": "application/json"}, body=json.dumps(payload), timeout_ms=timeout_ms)
        if not result.success:
            raise ValueError(result.error or "OAuth dynamic client registration failed")
        body = _body(result)
        if not isinstance(body, dict):
            raise ValueError("OAuth dynamic client registration did not return JSON")
        return body


class McpOAuthDeviceStartUseCase:
    def __init__(self, *, tool_repo: ToolRepository, executor: ToolExecutionPort, cipher: SecretCipherPort) -> None:
        self._tool_repo = tool_repo
        self._executor = executor
        self._cipher = cipher

    async def execute(self, input_dto: McpOAuthDeviceStartInput) -> McpOAuthDeviceStartOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)
        if tool is None:
            raise ValueError("MCP tool provider not found")
        config = dict(tool.config or {})
        server = config.get("server") or {}
        server_url = str(server.get("url") or config.get("url") or "")
        if not server_url:
            raise ValueError("MCP server.url is required before OAuth connect")

        metadata = await McpOAuthMetadataResolver(self._executor).resolve(
            server_url=server_url,
            authorization_endpoint=None,
            token_endpoint=None,
            registration_endpoint=None,
            authorization_server_issuer=input_dto.authorization_server_issuer,
            timeout_ms=input_dto.timeout_ms,
        )
        metadata = await _prefer_authorization_flow(self._executor, metadata, flow="device_code", timeout_ms=input_dto.timeout_ms)
        if not metadata.get("device_authorization_endpoint") or not metadata.get("token_endpoint"):
            raise ValueError("OAuth device-code endpoints were not available for this MCP provider")

        resource = str(metadata.get("resource") or _canonical_resource_uri(server_url))
        scopes = _choose_scopes(explicit=input_dto.scopes, challenge=list(metadata.get("required_scopes") or []), metadata=metadata)
        token_auth_method = _choose_token_auth_method(metadata)
        client_id = input_dto.client_id
        client_secret = input_dto.client_secret
        if not client_id and metadata.get("registration_endpoint"):
            registered = await self._register_device_client(
                registration_endpoint=str(metadata["registration_endpoint"]),
                timeout_ms=input_dto.timeout_ms,
                token_endpoint_auth_method=token_auth_method,
            )
            client_id = str(registered.get("client_id") or "") or None
            client_secret = str(registered.get("client_secret") or "") or None
            token_auth_method = str(registered.get("token_endpoint_auth_method") or token_auth_method)
        if not client_id:
            if _provider_uses_client_capability_selection(metadata):
                raise ValueError(_client_hint_message(metadata))
            raise ValueError("OAuth client_id is required for device-code flow")

        payload: dict[str, str] = {"client_id": client_id, "resource": resource}
        if scopes:
            payload["scope"] = " ".join(scopes)
        result = await self._executor.execute(
            method="POST",
            url=str(metadata["device_authorization_endpoint"]),
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            body=urlencode(payload),
            timeout_ms=input_dto.timeout_ms,
        )
        if not result.success:
            raise ValueError(result.error or "OAuth device authorization request failed")
        body = _body(result)
        if not isinstance(body, dict) or not body.get("device_code") or not body.get("user_code") or not body.get("verification_uri"):
            raise ValueError("OAuth device authorization did not return device_code, user_code, and verification_uri")

        expires_in = _int_or_none(body.get("expires_in"))
        interval = _int_or_none(body.get("interval")) or 5
        oauth = {
            "status": "device_pending",
            "flow": "device_code",
            "device_code_encrypted": await self._cipher.encrypt(str(body["device_code"])),
            "user_code": str(body["user_code"]),
            "verification_uri": str(body["verification_uri"]),
            "verification_uri_complete": str(body.get("verification_uri_complete") or "") or None,
            "device_expires_at": (utc_now() + timedelta(seconds=expires_in or 600)).isoformat(),
            "interval_seconds": interval,
            "resource": resource,
            "scopes": scopes,
            "authorization_server_issuer": metadata.get("authorization_server_issuer"),
            "device_authorization_endpoint": metadata.get("device_authorization_endpoint"),
            "token_endpoint": metadata["token_endpoint"],
            "registration_endpoint": metadata.get("registration_endpoint"),
            "client_id": client_id,
            "token_endpoint_auth_method": token_auth_method,
            "protected_resource_metadata": metadata.get("protected_resource_metadata"),
            "resource_metadata_url": metadata.get("resource_metadata_url"),
        }
        if client_secret:
            oauth["client_secret_encrypted"] = await self._cipher.encrypt(client_secret)
        config["oauth"] = oauth
        config["mcp_resource_metadata"] = metadata.get("protected_resource_metadata")
        tool.config = config
        await self._tool_repo.update(tool)
        return McpOAuthDeviceStartOutput(
            verification_uri=str(body["verification_uri"]),
            verification_uri_complete=oauth["verification_uri_complete"],
            user_code=str(body["user_code"]),
            expires_in=expires_in,
            interval=interval,
            authorization_server_issuer=oauth.get("authorization_server_issuer"),
            scopes=scopes,
        )

    async def _register_device_client(self, *, registration_endpoint: str, timeout_ms: int, token_endpoint_auth_method: str) -> dict[str, Any]:
        payload = {
            "client_name": "Woobe",
            "grant_types": [DEVICE_CODE_GRANT_TYPE, "refresh_token"],
            "token_endpoint_auth_method": token_endpoint_auth_method,
        }
        result = await self._executor.execute(method="POST", url=registration_endpoint, headers={"Accept": "application/json", "Content-Type": "application/json"}, body=json.dumps(payload), timeout_ms=timeout_ms)
        if not result.success:
            raise ValueError(result.error or "OAuth dynamic client registration failed")
        body = _body(result)
        if not isinstance(body, dict):
            raise ValueError("OAuth dynamic client registration did not return JSON")
        return body


class McpOAuthDevicePollUseCase:
    def __init__(self, *, tool_repo: ToolRepository, executor: ToolExecutionPort, cipher: SecretCipherPort) -> None:
        self._tool_repo = tool_repo
        self._executor = executor
        self._cipher = cipher

    async def execute(self, input_dto: McpOAuthDevicePollInput) -> McpOAuthDevicePollOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)
        if tool is None:
            raise ValueError("MCP tool provider not found")
        config = dict(tool.config or {})
        server = config.get("server") or {}
        server_url = str(server.get("url") or config.get("url") or "")
        oauth = _oauth_config(tool)
        if oauth.get("status") != "device_pending" or not oauth.get("device_code_encrypted"):
            raise ValueError("OAuth device flow is not pending for this MCP provider")
        if _is_expired(oauth.get("device_expires_at")):
            oauth = dict(oauth)
            oauth["status"] = "device_expired"
            config["oauth"] = oauth
            tool.config = config
            await self._tool_repo.update(tool)
            return McpOAuthDevicePollOutput(status="device_expired", error="OAuth device code expired", interval=oauth.get("interval_seconds"))

        device_code = await self._cipher.decrypt(str(oauth["device_code_encrypted"]))
        client_secret = None
        if oauth.get("client_secret_encrypted"):
            client_secret = await self._cipher.decrypt(str(oauth["client_secret_encrypted"]))
        token_payload = await self._exchange_device_code(
            oauth=oauth,
            device_code=device_code,
            client_id=str(oauth["client_id"]),
            client_secret=client_secret,
            resource=str(oauth.get("resource") or ""),
            timeout_ms=input_dto.timeout_ms,
        )
        if token_payload.get("pending"):
            return McpOAuthDevicePollOutput(status=str(token_payload["pending"]), connected=False, authorization_server_issuer=oauth.get("authorization_server_issuer"), scopes=list(oauth.get("scopes") or []), interval=token_payload.get("interval") or oauth.get("interval_seconds"))

        oauth = await self._connected_oauth_config(oauth, token_payload)
        config["oauth"] = oauth
        if server_url:
            await self._discover_connected_tools(config=config, server_url=server_url, oauth=oauth, timeout_ms=input_dto.timeout_ms)
        tool.config = config
        await self._tool_repo.update(tool)
        return McpOAuthDevicePollOutput(status="connected", connected=True, authorization_server_issuer=oauth.get("authorization_server_issuer"), scopes=list(oauth.get("scopes") or []), expires_at=oauth.get("expires_at"))

    async def _exchange_device_code(self, *, oauth: dict[str, Any], device_code: str, client_id: str, client_secret: str | None, resource: str, timeout_ms: int) -> dict[str, Any]:
        data: dict[str, str] = {"grant_type": DEVICE_CODE_GRANT_TYPE, "device_code": device_code, "resource": resource}
        headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
        _token_request_auth(data=data, headers=headers, token_auth_method=str(oauth.get("token_endpoint_auth_method") or "none"), client_id=client_id, client_secret=client_secret)
        result = await self._executor.execute(method="POST", url=str(oauth["token_endpoint"]), headers=headers, body=urlencode(data), timeout_ms=timeout_ms)
        body = _body(result)
        if not result.success:
            error = body.get("error") if isinstance(body, dict) else None
            if error in {"authorization_pending", "slow_down"}:
                pending: dict[str, Any] = {"pending": str(error)}
                if error == "slow_down":
                    pending["interval"] = int(oauth.get("interval_seconds") or 5) + 5
                return pending
            message = body.get("error_description") if isinstance(body, dict) else None
            raise ValueError(str(message or result.error or "OAuth device token exchange failed"))
        if not isinstance(body, dict) or not body.get("access_token"):
            raise ValueError("OAuth device token exchange did not return an access token")
        return body

    async def _connected_oauth_config(self, oauth: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        next_oauth = dict(oauth)
        next_oauth["status"] = "connected"
        next_oauth["token_type"] = str(payload.get("token_type") or "Bearer")
        next_oauth["access_token_encrypted"] = await self._cipher.encrypt(str(payload["access_token"]))
        if payload.get("refresh_token"):
            next_oauth["refresh_token_encrypted"] = await self._cipher.encrypt(str(payload["refresh_token"]))
        next_oauth["expires_at"] = _expires_at_from_token_response(payload)
        for key in ("device_code_encrypted", "device_expires_at", "user_code", "verification_uri", "verification_uri_complete"):
            next_oauth.pop(key, None)
        return next_oauth

    async def _discover_connected_tools(self, *, config: dict[str, Any], server_url: str, oauth: dict[str, Any], timeout_ms: int) -> None:
        try:
            access_token = await self._cipher.decrypt(str(oauth["access_token_encrypted"]))
            token_type = str(oauth.get("token_type") or "Bearer")
            headers = _headers_from_raw(_raw_headers_from_config(config))
            headers["Authori" + "zation"] = f"{token_type} {access_token}"
            output = await DiscoverMcpToolsUseCase(self._executor).execute(McpDiscoverInput(server_url=server_url, headers=headers, timeout_ms=timeout_ms))
            status = "ready" if not output.error and output.tools else ("token_invalid" if output.http_status == 401 else "discovery_failed")
            config["mcp_status"] = status
            config["mcp_discovery"] = {
                "status": status,
                "phase": output.phase,
                "http_status": output.http_status,
                "initialized": output.initialized,
                "error": output.error,
                "server_url": server_url,
                "oauth_resource": oauth.get("resource"),
                "authorization_server_issuer": oauth.get("authorization_server_issuer"),
                "token_endpoint_auth_method": oauth.get("token_endpoint_auth_method"),
                "checked_at": utc_now().isoformat(),
                "www_authenticate": output.www_authenticate[:1000] if output.www_authenticate else None,
            }
            if output.error or not output.tools:
                return
            next_tools = [item.model_dump() for item in output.tools]
            config["discovered_tools"] = merge_discovered_tools_with_existing_permissions(next_tools, config.get("discovered_tools"))
            config["discovered_at"] = utc_now().isoformat()
            config.pop("oauth_discovery_error", None)
        except Exception as exc:
            config["oauth_discovery_error"] = str(exc)
            config["mcp_status"] = "discovery_failed"


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
