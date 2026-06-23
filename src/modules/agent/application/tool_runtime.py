from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID, uuid4

from modules.agent.application.ports import (
    ExecutionResult,
    McpSessionStorePort,
    ToolExecutionPort,
    ToolRuntimePort,
    ToolSecretResolverPort,
)
from modules.agent.application.tool_types import (
    HTTP_PROTOCOL,
    MCP_PROTOCOL,
    normalize_tool_protocol,
)

_TEMPLATE_PATTERN = re.compile(r"\{\{(\w+)\}\}")
MCP_PROTOCOL_VERSION = "2025-06-18"
MCP_REMOTE_TOOL_INPUT_KEY = "__mcp_tool_name"
MCP_AGENT_SESSION_INPUT_KEY = "__projectrai_agent_session_id"


def _replace_template(value: str, variables: dict[str, Any]) -> str:
    def replace_var(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return str(variables.get(var_name, match.group(0)))

    return _TEMPLATE_PATTERN.sub(replace_var, value)


def _safe_tool_name(tool: Any) -> str:
    name = str(getattr(tool, "name", "")).lower().strip().replace(" ", "_").replace("-", "_")
    name = "".join(c for c in name if c.isalnum() or c == "_")
    if not name or name[0].isdigit():
        name = f"tool_{name}"
    return name


def _extract_template_variables(*templates: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for template in templates:
        for match in _TEMPLATE_PATTERN.findall(template or ""):
            if match not in seen:
                seen.add(match)
                result.append(match)
    return result


def _build_http_input_schema(config: dict[str, Any]) -> dict[str, Any]:
    body = config.get("body", "")
    if not isinstance(body, str):
        body = json.dumps(body)
    variables = _extract_template_variables(config.get("url", ""), body)
    properties = {
        var_name: {
            "type": "string",
            "description": f"Parameter {var_name}",
        }
        for var_name in variables
    }
    return {
        "type": "object",
        "properties": properties,
        "required": variables,
    }


def _coerce_body(body: Any) -> str | None:
    if body is None:
        return None
    if isinstance(body, str):
        return body
    return json.dumps(body)


def _parse_json_candidate(value: str) -> Any:
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _parse_sse_payload(value: str) -> Any:
    candidates: list[Any] = []
    data_lines: list[str] = []
    for line in value.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())
            continue
        if line.strip() == "" and data_lines:
            parsed = _parse_json_candidate("\n".join(data_lines))
            if parsed is not None:
                candidates.append(parsed)
            data_lines = []
    if data_lines:
        parsed = _parse_json_candidate("\n".join(data_lines))
        if parsed is not None:
            candidates.append(parsed)
    if not candidates:
        return None
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("result"):
            return candidate
    return candidates[-1]


def _parse_body_value(body: Any) -> Any:
    if isinstance(body, str):
        return _parse_json_candidate(body) or _parse_sse_payload(body) or body
    if isinstance(body, dict) and isinstance(body.get("raw"), str):
        raw = body["raw"]
        return _parse_json_candidate(raw) or _parse_sse_payload(raw) or body
    return body


def _extract_mcp_result_body(result: ExecutionResult) -> Any:
    output = result.output or {}
    if isinstance(output, dict) and "body" in output:
        return _parse_body_value(output["body"])
    if result.body:
        return _parse_body_value(result.body)
    return output


def _extract_headers(output: dict[str, Any] | None) -> dict[str, str]:
    if not output or not isinstance(output.get("headers"), dict):
        return {}
    return {str(k).lower(): str(v) for k, v in output["headers"].items()}


def _extract_session_id(output: dict[str, Any] | None) -> str | None:
    headers = _extract_headers(output)
    return headers.get("mcp-session-id") or headers.get("x-mcp-session-id")


def _session_headers(session_id: str | None) -> dict[str, str]:
    if not session_id:
        return {}
    return {"Mcp-Session-Id": session_id}


def _is_mcp_session_failure(result: ExecutionResult, body: Any) -> bool:
    text = ""
    if result.error:
        text += f" {result.error}"
    if isinstance(body, dict):
        text += f" {body.get('error', '')}"
    elif isinstance(body, str):
        text += f" {body}"
    normalized = text.lower()
    return "session" in normalized and any(
        marker in normalized for marker in ("invalid", "expired", "missing", "not found", "unknown")
    )


class UnsupportedToolRuntime(ToolRuntimePort):
    def __init__(self, protocol: str) -> None:
        self._protocol = protocol

    async def execute(self, tool: Any, input_data: dict[str, Any] | None = None) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            error=f"Tool runtime is not supported for protocol '{self._protocol}'",
        )

    async def test(
        self,
        config: dict[str, Any],
        input_data: dict[str, Any] | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            error=f"Tool runtime is not supported for protocol '{self._protocol}'",
        )

    def to_openai_definition(self, tool: Any) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": _safe_tool_name(tool),
                "description": getattr(tool, "description", None) or "Unsupported tool runtime",
                "parameters": getattr(tool, "input_schema", None)
                or {"type": "object", "properties": {}, "required": []},
            },
        }


class HttpToolRuntime(ToolRuntimePort):
    def __init__(
        self,
        executor: ToolExecutionPort,
        secret_resolver: ToolSecretResolverPort | None = None,
    ) -> None:
        self._executor = executor
        self._secret_resolver = secret_resolver

    async def execute(self, tool: Any, input_data: dict[str, Any] | None = None) -> ExecutionResult:
        return await self._execute_config(
            config=getattr(tool, "config", None) or {},
            input_data=input_data or {},
            timeout_ms=getattr(tool, "timeout_ms", None) or 30000,
            project_id=getattr(tool, "project_id", None),
            resolve_secrets=True,
        )

    async def test(
        self,
        config: dict[str, Any],
        input_data: dict[str, Any] | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        return await self._execute_config(
            config=config or {},
            input_data=input_data or {},
            timeout_ms=timeout_ms,
            project_id=None,
            resolve_secrets=False,
        )

    async def _execute_config(
        self,
        *,
        config: dict[str, Any],
        input_data: dict[str, Any],
        timeout_ms: int,
        project_id: UUID | None,
        resolve_secrets: bool,
    ) -> ExecutionResult:
        url = str(config.get("url", ""))
        method = str(config.get("method", "GET")).upper()
        raw_headers = config.get("headers", []) or []
        body = _coerce_body(config.get("body"))
        variables = config.get("variables", {}) or {}
        merged_input = {**variables, **input_data}

        if resolve_secrets and self._secret_resolver is not None and project_id is not None:
            headers = await self._secret_resolver.resolve_headers(raw_headers, project_id)
        else:
            headers = {
                h.get("key", ""): h.get("value", "")
                for h in raw_headers
                if h.get("key")
            }

        url = _replace_template(url, merged_input)
        if body:
            body = _replace_template(body, merged_input)

        return await self._executor.execute(
            method=method,
            url=url,
            headers=headers,
            body=body,
            timeout_ms=timeout_ms,
        )

    def to_openai_definition(self, tool: Any) -> dict[str, Any]:
        config = getattr(tool, "config", None) or {}
        input_schema = getattr(tool, "input_schema", None) or _build_http_input_schema(config)
        return {
            "type": "function",
            "function": {
                "name": _safe_tool_name(tool),
                "description": getattr(tool, "description", None)
                or f"HTTP {config.get('method', 'GET')} {config.get('url', '')}",
                "parameters": input_schema,
            },
        }


class McpToolRuntime(ToolRuntimePort):
    """Remote MCP runtime for JSON-RPC tool calls over an HTTP endpoint."""

    def __init__(
        self,
        executor: ToolExecutionPort,
        secret_resolver: ToolSecretResolverPort | None = None,
        session_store: McpSessionStorePort | None = None,
        session_ttl_seconds: int = 3600,
    ) -> None:
        self._executor = executor
        self._secret_resolver = secret_resolver
        self._session_store = session_store
        self._session_ttl_seconds = session_ttl_seconds

    async def execute(self, tool: Any, input_data: dict[str, Any] | None = None) -> ExecutionResult:
        config = getattr(tool, "config", None) or {}
        return await self._call_mcp_tool(
            config=config,
            input_data=input_data or {},
            timeout_ms=getattr(tool, "timeout_ms", None) or int(config.get("timeout_ms") or 30000),
            project_id=getattr(tool, "project_id", None),
            provider_id=str(getattr(tool, "id", "")) or None,
            resolve_secrets=True,
        )

    async def test(
        self,
        config: dict[str, Any],
        input_data: dict[str, Any] | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        return await self._call_mcp_tool(
            config=config or {},
            input_data=input_data or {},
            timeout_ms=timeout_ms,
            project_id=None,
            provider_id=None,
            resolve_secrets=False,
        )

    async def _initialize_session(
        self,
        *,
        url: str,
        base_headers: dict[str, str],
        timeout_ms: int,
    ) -> tuple[ExecutionResult | None, str | None, dict[str, str]]:
        initialize_payload = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "ProjectRAI", "version": "0.1.0"},
            },
        }
        init_result = await self._executor.execute(
            method="POST",
            url=url,
            headers=base_headers,
            body=json.dumps(initialize_payload),
            timeout_ms=timeout_ms,
        )
        if not init_result.success:
            return init_result, None, base_headers

        session_id = _extract_session_id(init_result.output if isinstance(init_result.output, dict) else None)
        request_headers = {**base_headers, **_session_headers(session_id)}
        initialized_payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        await self._executor.execute(
            method="POST",
            url=url,
            headers=request_headers,
            body=json.dumps(initialized_payload),
            timeout_ms=timeout_ms,
        )
        return None, session_id, request_headers

    async def _call_remote_tool(
        self,
        *,
        url: str,
        headers: dict[str, str],
        tool_name: str,
        arguments: dict[str, Any],
        timeout_ms: int,
    ) -> ExecutionResult:
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        result = await self._executor.execute(
            method="POST",
            url=url,
            headers=headers,
            body=json.dumps(payload),
            timeout_ms=timeout_ms,
        )
        body = _extract_mcp_result_body(result)
        if not result.success:
            return result
        if isinstance(body, dict) and body.get("error"):
            return ExecutionResult(
                success=False,
                status_code=result.status_code,
                output=body,
                duration_ms=result.duration_ms,
                error=str(body.get("error")),
            )
        output = body.get("result") if isinstance(body, dict) else body
        return ExecutionResult(
            success=True,
            status_code=result.status_code,
            output={"mcp": output},
            duration_ms=result.duration_ms,
        )

    async def _call_mcp_tool(
        self,
        *,
        config: dict[str, Any],
        input_data: dict[str, Any],
        timeout_ms: int,
        project_id: UUID | None,
        provider_id: str | None,
        resolve_secrets: bool,
    ) -> ExecutionResult:
        server = config.get("server", {}) or {}
        transport = server.get("transport", "streamable_http")
        if transport != "streamable_http":
            return ExecutionResult(
                success=False,
                error=f"MCP transport '{transport}' is not supported by this runtime",
            )

        call_input = dict(input_data or {})
        url = server.get("url") or config.get("url")
        tool_name = call_input.pop(MCP_REMOTE_TOOL_INPUT_KEY, None) or config.get("tool_name")
        agent_session_id = call_input.pop(MCP_AGENT_SESSION_INPUT_KEY, None)
        if not url:
            return ExecutionResult(success=False, error="MCP server.url is required")
        if not tool_name:
            return ExecutionResult(success=False, error="MCP tool_name is required")

        raw_headers = config.get("server_headers") or server.get("headers") or []
        if resolve_secrets and self._secret_resolver is not None and project_id is not None:
            configured_headers = await self._secret_resolver.resolve_headers(raw_headers, project_id)
        else:
            configured_headers = {
                h.get("key", ""): h.get("value", "")
                for h in raw_headers
                if h.get("key")
            }
        base_headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            **configured_headers,
        }

        session_cache_key = None
        if agent_session_id and provider_id and self._session_store is not None:
            session_cache_key = f"{agent_session_id}:{provider_id}"
            cached_session_id = await self._session_store.get(session_cache_key)
            if cached_session_id:
                cached_headers = {**base_headers, **_session_headers(cached_session_id)}
                result = await self._call_remote_tool(
                    url=str(url),
                    headers=cached_headers,
                    tool_name=str(tool_name),
                    arguments=call_input,
                    timeout_ms=timeout_ms,
                )
                body = _extract_mcp_result_body(result)
                if result.success or not _is_mcp_session_failure(result, body):
                    return result
                await self._session_store.delete(session_cache_key)

        init_failure, session_id, request_headers = await self._initialize_session(
            url=str(url),
            base_headers=base_headers,
            timeout_ms=timeout_ms,
        )
        if init_failure is not None:
            return init_failure
        if session_cache_key and session_id:
            await self._session_store.set(session_cache_key, session_id, self._session_ttl_seconds)

        return await self._call_remote_tool(
            url=str(url),
            headers=request_headers,
            tool_name=str(tool_name),
            arguments=call_input,
            timeout_ms=timeout_ms,
        )

    def to_openai_definition(self, tool: Any) -> dict[str, Any]:
        config = getattr(tool, "config", None) or {}
        server = config.get("server", {}) or {}
        input_schema = (
            getattr(tool, "input_schema", None)
            or config.get("discovered_input_schema")
            or config.get("input_schema")
            or {"type": "object", "properties": {}, "required": []}
        )
        tool_name = config.get("tool_name", "")
        server_name = server.get("name") or server.get("url") or "remote-server"
        return {
            "type": "function",
            "function": {
                "name": _safe_tool_name(tool),
                "description": getattr(tool, "description", None)
                or config.get("description")
                or f"MCP {server_name}/{tool_name}",
                "parameters": input_schema,
            },
        }


class ToolRuntimeRegistry:
    def __init__(self, runtimes: dict[str, ToolRuntimePort]) -> None:
        self._runtimes = runtimes

    def runtime_for(self, tool_type: Any) -> ToolRuntimePort:
        protocol = normalize_tool_protocol(tool_type)
        return self._runtimes.get(protocol) or UnsupportedToolRuntime(protocol)

    async def execute(self, tool: Any, input_data: dict[str, Any] | None = None) -> ExecutionResult:
        runtime = self.runtime_for(getattr(tool, "type", None))
        return await runtime.execute(tool, input_data or {})

    async def test(
        self,
        tool_type: Any,
        config: dict[str, Any],
        input_data: dict[str, Any] | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        runtime = self.runtime_for(tool_type)
        return await runtime.test(config, input_data or {}, timeout_ms=timeout_ms)

    def to_openai_definition(self, tool: Any) -> dict[str, Any]:
        runtime = self.runtime_for(getattr(tool, "type", None))
        return runtime.to_openai_definition(tool)


def build_default_tool_runtime_registry(
    executor: ToolExecutionPort,
    secret_resolver: ToolSecretResolverPort | None = None,
    mcp_session_store: McpSessionStorePort | None = None,
    mcp_session_ttl_seconds: int = 3600,
) -> ToolRuntimeRegistry:
    http_runtime = HttpToolRuntime(executor, secret_resolver)
    mcp_runtime = McpToolRuntime(
        executor,
        secret_resolver,
        session_store=mcp_session_store,
        session_ttl_seconds=mcp_session_ttl_seconds,
    )
    return ToolRuntimeRegistry(
        {
            HTTP_PROTOCOL: http_runtime,
            MCP_PROTOCOL: mcp_runtime,
        }
    )
