from __future__ import annotations

import ipaddress
import logging
import socket
import time
from urllib.parse import urlparse
from uuid import UUID

import httpx

from modules.agent.application.ports import (
    ExecutionResult,
    ToolExecutionPort,
    ToolSecretResolverPort,
)
from modules.agent.application.tool_converter import (
    agent_tool_to_openai_definition,
)
from modules.agent.domain.ports.tool_executor import ToolExecutor
from modules.agent.domain.ports.tool_repository import ToolRepository

logger = logging.getLogger(__name__)

PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return True
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return True
    try:
        addrinfo = socket.getaddrinfo(hostname, None)
        for _family, _type, _proto, _canonname, sockaddr in addrinfo:
            address = ipaddress.ip_address(sockaddr[0])
            if any(address in network for network in PRIVATE_NETWORKS):
                return True
    except OSError:
        return True
    return False


def _sanitize_error(error: str) -> str:
    sanitized = error.replace("\n", " ").replace("\r", " ")
    return sanitized[:500] + "..." if len(sanitized) > 500 else sanitized


class HttpToolExecutor(ToolExecutionPort):
    """HTTP Tool executor backed by a reusable connection pool."""

    def __init__(
        self,
        default_timeout_ms: int = 30000,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._default_timeout_ms = default_timeout_ms
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
        if _is_private_url(url):
            return ExecutionResult(
                success=False,
                error=(
                    "SSRF blocked: target URL resolves to a private network: "
                    f"{url}"
                ),
            )

        effective_timeout = timeout_ms or self._default_timeout_ms
        started_at = time.monotonic()

        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                content=body.encode() if body else None,
                timeout=httpx.Timeout(effective_timeout / 1000),
            )
            duration_ms = round((time.monotonic() - started_at) * 1000)

            try:
                output = response.json()
            except (ValueError, TypeError):
                output = {"raw": response.text}

            return ExecutionResult(
                success=response.is_success,
                status_code=response.status_code,
                output={
                    "status_code": response.status_code,
                    "body": output,
                },
                duration_ms=duration_ms,
                error=(
                    None
                    if response.is_success
                    else f"HTTP {response.status_code}"
                ),
            )
        except httpx.TimeoutException:
            duration_ms = round((time.monotonic() - started_at) * 1000)
            return ExecutionResult(
                success=False,
                duration_ms=duration_ms,
                error=f"Request timed out after {effective_timeout}ms",
            )
        except httpx.RequestError as exc:
            duration_ms = round((time.monotonic() - started_at) * 1000)
            return ExecutionResult(
                success=False,
                duration_ms=duration_ms,
                error=f"Request failed: {_sanitize_error(str(exc))}",
            )


class AgentToolExecutor(ToolExecutor):
    def __init__(
        self,
        tool_repo: ToolRepository,
        tool_executor: ToolExecutionPort | None = None,
        secret_resolver: ToolSecretResolverPort | None = None,
    ) -> None:
        self._tool_repo = tool_repo
        self._tool_executor = tool_executor or HttpToolExecutor()
        self._secret_resolver = secret_resolver

    async def execute_tool(self, tool_id: UUID, input_data: dict) -> dict:
        from modules.agent.application.use_cases.tools_use_cases import (
            ExecuteToolInput,
            ExecuteToolUseCase,
        )

        use_case = ExecuteToolUseCase(
            tool_repo=self._tool_repo,
            tool_executor=self._tool_executor,
            secret_resolver=self._secret_resolver,
        )
        result = await use_case.execute(
            ExecuteToolInput(tool_id=tool_id, input_data=input_data)
        )
        return result.model_dump()

    async def tool_to_openai_definition(
        self,
        tool_id: UUID,
    ) -> dict | None:
        tool = await self._tool_repo.get_by_id(tool_id)
        if tool:
            return agent_tool_to_openai_definition(tool)
        return None
