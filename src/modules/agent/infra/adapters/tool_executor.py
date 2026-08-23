from __future__ import annotations

import ipaddress
import json
import logging
import socket
import time
from urllib.parse import urlparse
from uuid import UUID

import httpx

from modules.agent.application.interfaces.ports import (
    ExecutionResult,
    ToolExecutionPort,
    ToolSecretResolverPort,
)
from shared.security.redaction import redact_sensitive_data, redact_text, redact_url

logger = logging.getLogger(__name__)

ALLOWED_HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"})
ALLOWED_SCHEMES = frozenset({"http", "https"})
SAFE_RESPONSE_HEADERS = frozenset(
    {"content-type", "mcp-session-id", "x-mcp-session-id", "www-authenticate"}
)


def _safe_response_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() in SAFE_RESPONSE_HEADERS
    }


def _blocked_address(
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    *,
    allow_local_networks: bool = False,
) -> bool:
    if address.is_link_local or address.is_multicast or address.is_unspecified:
        return True

    if allow_local_networks and address.is_loopback:
        return False

    if address.is_reserved:
        return True

    if address.is_global:
        return False

    if allow_local_networks and address.is_private:
        return False

    return True


def _resolved_addresses(hostname: str) -> frozenset[str]:
    try:
        addrinfo = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except OSError:
        return frozenset()
    return frozenset(str(sockaddr[0]) for *_prefix, sockaddr in addrinfo)


def _validated_addresses(
    url: str,
    *,
    allow_local_networks: bool,
) -> frozenset[str] | None:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        return None
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        return None
    if parsed.fragment:
        return None

    addresses = _resolved_addresses(parsed.hostname)
    if not addresses:
        return None
    for raw_address in addresses:
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError:
            return None
        if _blocked_address(address, allow_local_networks=allow_local_networks):
            return None
    return addresses


def _validated_public_addresses(url: str) -> frozenset[str] | None:
    return _validated_addresses(url, allow_local_networks=False)


def _validated_local_addresses(url: str) -> frozenset[str] | None:
    return _validated_addresses(url, allow_local_networks=True)


def _connected_peer_address(response: httpx.Response) -> str | None:
    network_stream = response.extensions.get("network_stream")
    get_extra_info = getattr(network_stream, "get_extra_info", None)
    if not callable(get_extra_info):
        return None
    try:
        server_address = get_extra_info("server_addr")
    except (OSError, RuntimeError, TypeError, ValueError):
        return None
    if isinstance(server_address, (tuple, list)) and server_address:
        return str(server_address[0])
    if isinstance(server_address, str):
        return server_address
    return None


def _peer_matches_validation(
    response: httpx.Response,
    validated_addresses: frozenset[str],
) -> bool:
    peer = _connected_peer_address(response)
    if peer is None:
        return True
    try:
        normalized_peer = str(ipaddress.ip_address(peer))
    except ValueError:
        return False
    return normalized_peer in validated_addresses


def _is_private_url(url: str) -> bool:
    return _validated_public_addresses(url) is None


def _sanitize_error(error: str) -> str:
    sanitized = redact_text(error).replace("\n", " ").replace("\r", " ")
    return sanitized[:500] + "..." if len(sanitized) > 500 else sanitized


class HttpToolExecutor(ToolExecutionPort):
    """HTTP tool executor with bounded I/O and configurable SSRF controls."""

    def __init__(
        self,
        default_timeout_ms: int = 30000,
        client: httpx.AsyncClient | None = None,
        *,
        max_timeout_ms: int = 30000,
        max_response_bytes: int = 1048576,
        allow_local_networks: bool = False,
    ) -> None:
        self._default_timeout_ms = min(default_timeout_ms, max_timeout_ms)
        self._max_timeout_ms = max_timeout_ms
        self._max_response_bytes = max_response_bytes
        self._allow_local_networks = allow_local_networks
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0,
            ),
            follow_redirects=False,
        )

    async def aclose(self) -> None:
        if self._owns_client and not self._client.is_closed:
            await self._client.aclose()

    async def execute(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        normalized_method = method.upper().strip()
        if normalized_method not in ALLOWED_HTTP_METHODS:
            return ExecutionResult(success=False, error="HTTP method is not allowed")

        validator = (
            _validated_local_addresses
            if self._allow_local_networks
            else _validated_public_addresses
        )
        first_resolution = validator(url)
        if first_resolution is None:
            allowed_scope = "public or local" if self._allow_local_networks else "public"
            return ExecutionResult(
                success=False,
                error=(
                    f"SSRF blocked: target URL is not {allowed_scope}: "
                    f"{redact_url(url)}"
                ),
            )
        second_resolution = validator(url)
        if second_resolution != first_resolution:
            return ExecutionResult(
                success=False,
                error="SSRF blocked: target DNS resolution changed during validation",
            )

        requested_timeout = timeout_ms or self._default_timeout_ms
        effective_timeout = max(1, min(requested_timeout, self._max_timeout_ms))
        started_at = time.monotonic()
        response: httpx.Response | None = None

        try:
            request = self._client.build_request(
                method=normalized_method,
                url=url,
                headers=headers,
                content=body.encode("utf-8") if body else None,
                timeout=httpx.Timeout(effective_timeout / 1000),
            )
            response = await self._client.send(
                request,
                stream=True,
                follow_redirects=False,
            )
            duration_ms = round((time.monotonic() - started_at) * 1000)

            if not _peer_matches_validation(response, first_resolution):
                return ExecutionResult(
                    success=False,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    error="SSRF blocked: connected peer did not match validated DNS addresses",
                )

            if 300 <= response.status_code < 400:
                return ExecutionResult(
                    success=False,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    error="HTTP redirects are not allowed for tools",
                )

            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > self._max_response_bytes:
                        return ExecutionResult(
                            success=False,
                            status_code=response.status_code,
                            duration_ms=duration_ms,
                            error="HTTP tool response exceeded the configured size limit",
                        )
                except ValueError:
                    pass

            payload = bytearray()
            async for chunk in response.aiter_bytes():
                payload.extend(chunk)
                if len(payload) > self._max_response_bytes:
                    return ExecutionResult(
                        success=False,
                        status_code=response.status_code,
                        duration_ms=round((time.monotonic() - started_at) * 1000),
                        error="HTTP tool response exceeded the configured size limit",
                    )

            try:
                output_body = json.loads(payload) if payload else None
            except (ValueError, TypeError, UnicodeDecodeError):
                output_body = {"raw": payload.decode("utf-8", errors="replace")}

            output = redact_sensitive_data(
                {
                    "status_code": response.status_code,
                    "headers": _safe_response_headers(response.headers),
                    "body": output_body,
                }
            )
            return ExecutionResult(
                success=response.is_success,
                status_code=response.status_code,
                output=output,
                duration_ms=round((time.monotonic() - started_at) * 1000),
                error=None if response.is_success else f"HTTP {response.status_code}",
            )
        except httpx.TimeoutException:
            return ExecutionResult(
                success=False,
                duration_ms=round((time.monotonic() - started_at) * 1000),
                error=f"Request timed out after {effective_timeout}ms",
            )
        except httpx.RequestError as exc:
            return ExecutionResult(
                success=False,
                duration_ms=round((time.monotonic() - started_at) * 1000),
                error=f"Request failed: {_sanitize_error(str(exc))}",
            )
        finally:
            if response is not None:
                await response.aclose()


