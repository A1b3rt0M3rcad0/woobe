from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, urlparse
from uuid import UUID

from pydantic import BaseModel, Field

from modules.agent.application.mcp_discovery import DiscoverMcpToolsUseCase, McpDiscoverInput
from modules.agent.application.mcp_permissions import merge_discovered_tools_with_existing_permissions
from modules.agent.application.ports import ExecutionResult, ToolExecutionPort
from modules.agent.domain.entities import Tool
from modules.agent.domain.repositories import ToolRepository
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from shared.infra.time import utc_now

MCP_PROTOCOL_VERSION = "2025-06-18"
OAUTH_STATE_TTL_SECONDS = 600
OAUTH_EXPIRY_SKEW_SECONDS = 60


class McpOAuthStartInput(BaseModel):
    tool_id: UUID
    redirect_uri: str = Field(..., min_length=1)
    scopes: list[str] = Field(default_factory=list)
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    registration_endpoint: str | None = None
    authorization_server_issuer: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    timeout_ms: int = Field(default=30000, ge=1)


class McpOAuthStartOutput(BaseModel):
    authorization_url: str
    state: str
    status: str = "pending"


class McpOAuthCompleteInput(BaseModel):
    tool_id: UUID
    code: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)
    timeout_ms: int = Field(default=30000, ge=1)


class McpOAuthStatusInput(BaseModel):
    tool_id: UUID


class McpOAuthStatusOutput(BaseModel):
    status: str
    connected: bool
    authorization_server_issuer: str | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_at: str | None = None


class McpOAuthDisconnectInput(BaseModel):
    tool_id: UUID


class McpOAuthDisconnectOutput(BaseModel):
    status: str = "disconnected"


def _canonical_resource_uri(server_url: str) -> str:
    parsed = urlparse(server_url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if not scheme or not host:
        raise ValueError("MCP server URL must be an absolute URL")
    netloc = host
    if parsed.port:
        netloc = f"{host}:{parsed.port}"
    path = parsed.path or ""
    if path == "/":
        path = ""
    return f"{scheme}://{netloc}{path}"


def _code_verifier() -> str:
    return secrets.token_urlsafe(64)[:96]


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _body(result: ExecutionResult) -> Any:
    output = result.output or {}
    value = output.get("body") if isinstance(output, dict) else None
    if isinstance(value, dict) and isinstance(value.get("raw"), str):
        value = value["raw"]
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _headers(result: ExecutionResult) -> dict[str, str]:
    output = result.output or {}
    raw = output.get("headers") if isinstance(output, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {str(key).lower(): str(value) for key, value in raw.items()}


def _parse_www_authenticate_resource_metadata(header: str | None) -> str | None:
    if not header:
        return None
    lower = header.lower()
    marker = "resource_metadata="
    idx = lower.find(marker)
    if idx < 0:
        return None
    value = header[idx + len(marker):].strip()
    if value.startswith('"'):
        end = value.find('"', 1)
        return value[1:end] if end > 1 else None
    return value.split(",", 1)[0].strip() or None


def _well_known_authorization_server_url(issuer: str) -> str:
    return issuer.rstrip("/") + "/.well-known/oauth-authorization-server"


def _oauth_config(tool: Tool) -> dict[str, Any]:
    config = tool.config or {}
    oauth = config.get("oauth")
    return oauth if isinstance(oauth, dict) else {}


def _raw_headers_from_config(config: dict[str, Any]) -> list[dict[str, Any]]:
    server = config.get("server") or {}
    raw_headers = config.get("server_headers") or server.get("headers") or []
    if isinstance(raw_headers, dict):
        return [{"key": str(k), "value": str(v)} for k, v in raw_headers.items() if k]
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


def _expires_at_from_token_response(payload: dict[str, Any]) -> str | None:
    expires_in = payload.get("expires_in")
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None
    return (utc_now() + timedelta(seconds=seconds)).isoformat()


def _is_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    try:
        parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed <= utc_now() + timedelta(seconds=OAUTH_EXPIRY_SKEW_SECONDS)


class McpOAuthMetadataResolver:
    def __init__(self, executor: ToolExecutionPort) -> None:
        self._executor = executor

    async def resolve(
        self,
        *,
        server_url: str,
        authorization_endpoint: str | None,
        token_endpoint: str | None,
        registration_endpoint: str | None,
        authorization_server_issuer: str | None,
        timeout_ms: int,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "authorization_endpoint": authorization_endpoint,
            "token_endpoint": token_endpoint,
            "registration_endpoint": registration_endpoint,
            "authorization_server_issuer": authorization_server_issuer,
        }
        if metadata["authorization_endpoint"] and metadata["token_endpoint"]:
            return metadata

        resource_metadata_url = await self._resource_metadata_url(server_url=server_url, timeout_ms=timeout_ms)
        if resource_metadata_url:
            resource_metadata = await self._get_json(resource_metadata_url, timeout_ms=timeout_ms)
            auth_servers = resource_metadata.get("authorization_servers") if isinstance(resource_metadata, dict) else None
            if isinstance(auth_servers, list) and auth_servers:
                metadata["authorization_server_issuer"] = str(auth_servers[0])

        issuer = metadata.get("authorization_server_issuer")
        if issuer:
            as_metadata = await self._get_json(_well_known_authorization_server_url(str(issuer)), timeout_ms=timeout_ms)
            if isinstance(as_metadata, dict):
                metadata["authorization_endpoint"] = metadata["authorization_endpoint"] or as_metadata.get("authorization_endpoint")
                metadata["token_endpoint"] = metadata["token_endpoint"] or as_metadata.get("token_endpoint")
                metadata["registration_endpoint"] = metadata["registration_endpoint"] or as_metadata.get("registration_endpoint")

        if not metadata.get("authorization_endpoint") or not metadata.get("token_endpoint"):
            raise ValueError("Could not discover MCP OAuth authorization and token endpoints")
        return metadata

    async def _resource_metadata_url(self, *, server_url: str, timeout_ms: int) -> str | None:
        initialize_payload = {
            "jsonrpc": "2.0",
            "id": "oauth-discovery",
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "ProjectRAI", "version": "0.1.0"},
            },
        }
        result = await self._executor.execute(
            method="POST",
            url=server_url,
            headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json", "MCP-Protocol-Version": MCP_PROTOCOL_VERSION},
            body=json.dumps(initialize_payload),
            timeout_ms=timeout_ms,
        )
        return _parse_www_authenticate_resource_metadata(_headers(result).get("www-authenticate"))

    async def _get_json(self, url: str, *, timeout_ms: int) -> dict[str, Any]:
        result = await self._executor.execute(method="GET", url=url, headers={"Accept": "application/json"}, timeout_ms=timeout_ms)
        if not result.success:
            raise ValueError(result.error or f"OAuth metadata request failed for {url}")
        body = _body(result)
        if not isinstance(body, dict):
            raise ValueError(f"OAuth metadata response is not a JSON object for {url}")
        return body


class McpOAuthStartUseCase:
    def __init__(self, *, tool_repo: ToolRepository, executor: ToolExecutionPort, cipher: SecretCipherAdapter) -> None:
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
        resource = _canonical_resource_uri(server_url)

        metadata = await McpOAuthMetadataResolver(self._executor).resolve(
            server_url=server_url,
            authorization_endpoint=input_dto.authorization_endpoint,
            token_endpoint=input_dto.token_endpoint,
            registration_endpoint=input_dto.registration_endpoint,
            authorization_server_issuer=input_dto.authorization_server_issuer,
            timeout_ms=input_dto.timeout_ms,
        )
        client_id = input_dto.client_id
        client_secret = input_dto.client_secret
        if not client_id and metadata.get("registration_endpoint"):
            registered = await self._register_client(registration_endpoint=str(metadata["registration_endpoint"]), redirect_uri=input_dto.redirect_uri, timeout_ms=input_dto.timeout_ms)
            client_id = str(registered.get("client_id") or "") or None
            client_secret = str(registered.get("client_secret") or "") or None
        if not client_id:
            raise ValueError("OAuth client_id is required and dynamic client registration was not available")

        state = secrets.token_urlsafe(32)
        verifier = _code_verifier()
        scopes = input_dto.scopes or []
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

        oauth = {
            "status": "pending",
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
        }
        if client_secret:
            oauth["client_secret_encrypted"] = await self._cipher.encrypt(client_secret)
        config["oauth"] = oauth
        tool.config = config
        await self._tool_repo.update(tool)
        return McpOAuthStartOutput(authorization_url=f"{metadata['authorization_endpoint']}?{urlencode(params)}", state=state)

    async def _register_client(self, *, registration_endpoint: str, redirect_uri: str, timeout_ms: int) -> dict[str, Any]:
        payload = {
            "client_name": "ProjectRAI",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        }
        result = await self._executor.execute(method="POST", url=registration_endpoint, headers={"Accept": "application/json", "Content-Type": "application/json"}, body=json.dumps(payload), timeout_ms=timeout_ms)
        if not result.success:
            raise ValueError(result.error or "OAuth dynamic client registration failed")
        body = _body(result)
        if not isinstance(body, dict):
            raise ValueError("OAuth dynamic client registration did not return JSON")
        return body


class McpOAuthCompleteUseCase:
    def __init__(self, *, tool_repo: ToolRepository, executor: ToolExecutionPort, cipher: SecretCipherAdapter) -> None:
        self._tool_repo = tool_repo
        self._executor = executor
        self._cipher = cipher

    async def execute(self, input_dto: McpOAuthCompleteInput) -> McpOAuthStatusOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)
        if tool is None:
            raise ValueError("MCP tool provider not found")
        config = dict(tool.config or {})
        server = config.get("server") or {}
        server_url = str(server.get("url") or config.get("url") or "")
        oauth = _oauth_config(tool)
        if oauth.get("status") != "pending" or oauth.get("state") != input_dto.state:
            raise ValueError("Invalid or expired OAuth state")
        if _is_expired(oauth.get("state_expires_at")):
            raise ValueError("OAuth state expired")
        verifier = await self._cipher.decrypt(str(oauth["code_verifier_encrypted"]))
        client_secret = None
        if oauth.get("client_secret_encrypted"):
            client_secret = await self._cipher.decrypt(str(oauth["client_secret_encrypted"]))
        token_payload = await self._exchange_code(
            token_endpoint=str(oauth["token_endpoint"]),
            code=input_dto.code,
            redirect_uri=str(oauth["redirect_uri"]),
            client_id=str(oauth["client_id"]),
            client_secret=client_secret,
            code_verifier=verifier,
            resource=str(oauth["resource"]),
            timeout_ms=input_dto.timeout_ms,
        )
        oauth = await self._connected_oauth_config(oauth, token_payload)
        config["oauth"] = oauth
        if server_url:
            await self._discover_connected_tools(config=config, server_url=server_url, oauth=oauth, timeout_ms=input_dto.timeout_ms)
        tool.config = config
        await self._tool_repo.update(tool)
        return McpOAuthStatusOutput(status="connected", connected=True, authorization_server_issuer=oauth.get("authorization_server_issuer"), scopes=list(oauth.get("scopes") or []), expires_at=oauth.get("expires_at"))

    async def _exchange_code(
        self,
        *,
        token_endpoint: str,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str | None,
        code_verifier: str,
        resource: str,
        timeout_ms: int,
    ) -> dict[str, Any]:
        data: dict[str, str] = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri, "client_id": client_id, "code_verifier": code_verifier, "resource": resource}
        if client_secret:
            data["client_secret"] = client_secret
        result = await self._executor.execute(method="POST", url=token_endpoint, headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}, body=urlencode(data), timeout_ms=timeout_ms)
        if not result.success:
            raise ValueError(result.error or "OAuth token exchange failed")
        body = _body(result)
        if not isinstance(body, dict) or not body.get("access_token"):
            raise ValueError("OAuth token exchange did not return an access token")
        return body

    async def _connected_oauth_config(self, oauth: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        next_oauth = dict(oauth)
        next_oauth["status"] = "connected"
        next_oauth["token_type"] = str(payload.get("token_type") or "Bearer")
        next_oauth["access_token_encrypted"] = await self._cipher.encrypt(str(payload["access_token"]))
        if payload.get("refresh_token"):
            next_oauth["refresh_token_encrypted"] = await self._cipher.encrypt(str(payload["refresh_token"]))
        next_oauth["expires_at"] = _expires_at_from_token_response(payload)
        for key in ("state", "state_expires_at", "code_verifier_encrypted"):
            next_oauth.pop(key, None)
        return next_oauth

    async def _discover_connected_tools(self, *, config: dict[str, Any], server_url: str, oauth: dict[str, Any], timeout_ms: int) -> None:
        try:
            access_token = await self._cipher.decrypt(str(oauth["access_token_encrypted"]))
            token_type = str(oauth.get("token_type") or "Bearer")
            headers = _headers_from_raw(_raw_headers_from_config(config))
            headers["Authori" + "zation"] = f"{token_type} {access_token}"
            output = await DiscoverMcpToolsUseCase(self._executor).execute(McpDiscoverInput(server_url=server_url, headers=headers, timeout_ms=timeout_ms))
            if output.error or not output.tools:
                config["oauth_discovery_error"] = output.error or "OAuth-connected MCP discovery returned no tools"
                return
            next_tools = [item.model_dump() for item in output.tools]
            config["discovered_tools"] = merge_discovered_tools_with_existing_permissions(next_tools, config.get("discovered_tools"))
            config["discovered_at"] = utc_now().isoformat()
            config.pop("oauth_discovery_error", None)
        except Exception as exc:
            config["oauth_discovery_error"] = str(exc)


class McpOAuthStatusUseCase:
    def __init__(self, *, tool_repo: ToolRepository) -> None:
        self._tool_repo = tool_repo

    async def execute(self, input_dto: McpOAuthStatusInput) -> McpOAuthStatusOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)
        if tool is None:
            raise ValueError("MCP tool provider not found")
        oauth = _oauth_config(tool)
        status = str(oauth.get("status") or "disconnected")
        return McpOAuthStatusOutput(status=status, connected=status == "connected", authorization_server_issuer=oauth.get("authorization_server_issuer"), scopes=list(oauth.get("scopes") or []), expires_at=oauth.get("expires_at"))


class McpOAuthDisconnectUseCase:
    def __init__(self, *, tool_repo: ToolRepository) -> None:
        self._tool_repo = tool_repo

    async def execute(self, input_dto: McpOAuthDisconnectInput) -> McpOAuthDisconnectOutput:
        tool = await self._tool_repo.get_by_id(input_dto.tool_id)
        if tool is None:
            raise ValueError("MCP tool provider not found")
        config = dict(tool.config or {})
        config.pop("oauth", None)
        tool.config = config
        await self._tool_repo.update(tool)
        return McpOAuthDisconnectOutput()


class McpOAuthConfigTokenProvider:
    def __init__(self, *, executor: ToolExecutionPort, cipher: SecretCipherAdapter) -> None:
        self._executor = executor
        self._cipher = cipher

    async def authorization_headers_for(self, tool: Tool) -> dict[str, str]:
        oauth = _oauth_config(tool)
        if oauth.get("status") != "connected" or not oauth.get("access_token_encrypted"):
            return {}
        if _is_expired(oauth.get("expires_at")) and oauth.get("refresh_token_encrypted"):
            refreshed = await self._refresh(oauth)
            if refreshed:
                oauth = refreshed
        access_token = await self._cipher.decrypt(str(oauth["access_token_encrypted"]))
        token_type = str(oauth.get("token_type") or "Bearer")
        return {"Authori" + "zation": f"{token_type} {access_token}"}

    async def _refresh(self, oauth: dict[str, Any]) -> dict[str, Any] | None:
        refresh_token = await self._cipher.decrypt(str(oauth["refresh_token_encrypted"]))
        data = {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": str(oauth.get("client_id") or ""), "resource": str(oauth.get("resource") or "")}
        if oauth.get("client_secret_encrypted"):
            data["client_secret"] = await self._cipher.decrypt(str(oauth["client_secret_encrypted"]))
        result = await self._executor.execute(method="POST", url=str(oauth["token_endpoint"]), headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}, body=urlencode(data), timeout_ms=30000)
        if not result.success:
            return None
        body = _body(result)
        if not isinstance(body, dict) or not body.get("access_token"):
            return None
        next_oauth = dict(oauth)
        next_oauth["access_token_encrypted"] = await self._cipher.encrypt(str(body["access_token"]))
        if body.get("refresh_token"):
            next_oauth["refresh_token_encrypted"] = await self._cipher.encrypt(str(body["refresh_token"]))
        next_oauth["expires_at"] = _expires_at_from_token_response(body)
        next_oauth["token_type"] = str(body.get("token_type") or next_oauth.get("token_type") or "Bearer")
        return next_oauth
