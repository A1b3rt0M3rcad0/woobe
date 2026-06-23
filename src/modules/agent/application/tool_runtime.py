from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID, uuid4

from modules.agent.application.ports import (
    ExecutionResult,
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
    variables = _extract_template_variables(config.get("url", ""), config.get("body", ""))
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


def _extract_mcp_result_body(result: ExecutionResult) -> Any:
    output = result.output or {}
    if isinstance(output, dict) and "body" in output:
        return output["body"]
    if result.body:
        try:
            return json.loads(result.body)
        except ValueError:
            return result.body
    return output


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
    """Remote MCP runtime for JSON-RPC tool calls over an HTTP endpoint.

    This runtime intentionally supports remote HTTP-style MCP calls only. Local stdio
    servers are rejected by default because they would require process execution and
    sandbox policy outside this module.
    """

    def __init__(
        self,
        executor: ToolExecutionPort,
        secret_resolver: ToolSecretResolverPort | None = None,
    ) -> None:
        self._executor = executor
        self._secret_resolver = secret_resolver

    async def execute(self, tool: Any, input_data: dict[str, Any] | None = None) -> ExecutionResult:
        config = getattr(tool, "config", None) or {}
        return await self._call_mcp_tool(
            config=config,
            input_data=input_data or {},
            timeout_ms=getattr(tool, "timeout_ms", None) or int(config.get("timeout_ms") or 30000),
            project_id=getattr(tool, "project_id", None),
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
            resolve_secrets=False,
        )

    async def _call_mcp_tool(
        self,
        *,
        config: dict[str, Any],
        input_data: dict[str, Any],
        timeout_ms: int,
        project_id: UUID | None,
        resolve_secrets: bool,
    ) -> ExecutionResult:
        server = config.get("server", {}) or {}
        transport = server.get("transport", "streamable_http")
        if transport != "streamable_http":
            return ExecutionResult(
                success=False,
                error=f"MCP transport '{transport}' is not supported by this runtime",
            )

        url = server.get("url") or config.get("url")
        tool_name = config.get("tool_name")
        if not url:
            return ExecutionResult(success=False, error="MCP server.url is required")
        if not tool_name:
            return ExecutionResult(success=False, error="MCP tool_name is required")

        raw_headers = config.get("server_headers") or server.get("headers") or []
        if resolve_secrets and self._secret_resolver is not None and project_id is not None:
            headers = await self._secret_resolver.resolve_headers(raw_headers, project_id)
        else:
            headers = {
                h.get("key", ""): h.get("value", "")
                for h in raw_headers
                if h.get("key")
            }
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **headers,
        }

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": input_data,
            },
        }
        result = await self._executor.execute(
            method="POST",
            url=str(url),
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
) -> ToolRuntimeRegistry:
    http_runtime = HttpToolRuntime(executor, secret_resolver)
    mcp_runtime = McpToolRuntime(executor, secret_resolver)
    return ToolRuntimeRegistry(
        {
            HTTP_PROTOCOL: http_runtime,
            MCP_PROTOCOL: mcp_runtime,
        }
    )
