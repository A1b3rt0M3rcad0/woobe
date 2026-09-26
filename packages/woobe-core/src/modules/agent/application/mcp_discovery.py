from __future__ import annotations

import json
from typing import Any

from modules.agent.application.dtos.mcp_discovery_dtos import (
    McpDiscoverInput,
    McpDiscoveredTool,
    McpDiscoverOutput,
)
from modules.agent.application.interfaces.ports import ExecutionResult, ToolExecutionPort
from modules.agent.application.mcp_permissions import default_mcp_permission

MCP_PROTOCOL_VERSION = "2025-06-18"


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


def _extract_body(output: dict[str, Any] | None) -> Any:
    if not output:
        return None
    return _parse_body_value(output.get("body"))


def _extract_headers(output: dict[str, Any] | None) -> dict[str, str]:
    if not output or not isinstance(output.get("headers"), dict):
        return {}
    return {str(k).lower(): str(v) for k, v in output["headers"].items()}


def _result_headers(result: ExecutionResult) -> dict[str, str]:
    output_headers = _extract_headers(result.output if isinstance(result.output, dict) else None)
    direct_headers = {str(k).lower(): str(v) for k, v in (result.headers or {}).items()}
    return {**direct_headers, **output_headers}


def _discovery_error(*, phase: str, result: ExecutionResult, initialized: bool) -> McpDiscoverOutput:
    headers = _result_headers(result)
    return McpDiscoverOutput(
        tools=[],
        initialized=initialized,
        error=result.error or f"MCP {phase} failed",
        phase=phase,
        http_status=result.status_code,
        www_authenticate=headers.get("www-authenticate"),
    )


def _session_headers(init_output: dict[str, Any] | None) -> dict[str, str]:
    headers = _extract_headers(init_output)
    session_id = headers.get("mcp-session-id") or headers.get("x-mcp-session-id")
    if not session_id:
        return {}
    return {"Mcp-Session-Id": session_id}


def _extract_tools(payload: Any) -> list[McpDiscoveredTool]:
    if not isinstance(payload, dict):
        return []
    result = payload.get("result") if isinstance(payload.get("result"), dict) else payload
    raw_tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(raw_tools, list):
        return []

    tools: list[McpDiscoveredTool] = []
    for raw in raw_tools:
        if not isinstance(raw, dict):
            continue
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        input_schema = raw.get("inputSchema") or raw.get("input_schema")
        tools.append(
            McpDiscoveredTool(
                name=name,
                title=raw.get("title") if isinstance(raw.get("title"), str) else None,
                description=raw.get("description") if isinstance(raw.get("description"), str) else None,
                input_schema=input_schema if isinstance(input_schema, dict) else None,
                permission=default_mcp_permission(),
            )
        )
    return tools


class DiscoverMcpToolsUseCase:
    def __init__(self, executor: ToolExecutionPort) -> None:
        self._executor = executor

    async def execute(self, input_dto: McpDiscoverInput) -> McpDiscoverOutput:
        base_headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            **input_dto.headers,
        }
        initialize_payload = {
            "jsonrpc": "2.0",
            "id": "initialize",
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "Woobe", "version": "0.12.1"},
            },
        }
        init_result = await self._executor.execute(
            method="POST",
            url=input_dto.server_url,
            headers=base_headers,
            body=json.dumps(initialize_payload),
            timeout_ms=input_dto.timeout_ms,
        )
        initialized = bool(init_result.success)
        if not init_result.success:
            return _discovery_error(phase="initialize", result=init_result, initialized=False)

        session_headers = _session_headers(init_result.output if isinstance(init_result.output, dict) else None)
        request_headers = {**base_headers, **session_headers}
        initialized_payload = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        await self._executor.execute(
            method="POST",
            url=input_dto.server_url,
            headers=request_headers,
            body=json.dumps(initialized_payload),
            timeout_ms=input_dto.timeout_ms,
        )
        list_payload = {"jsonrpc": "2.0", "id": "tools-list", "method": "tools/list", "params": {}}
        list_result = await self._executor.execute(
            method="POST",
            url=input_dto.server_url,
            headers=request_headers,
            body=json.dumps(list_payload),
            timeout_ms=input_dto.timeout_ms,
        )
        if not list_result.success:
            return _discovery_error(phase="tools/list", result=list_result, initialized=initialized)

        tools = _extract_tools(_extract_body(list_result.output if isinstance(list_result.output, dict) else None))
        if not tools:
            return McpDiscoverOutput(
                tools=[],
                initialized=initialized,
                error="MCP server did not return any tools",
                phase="tools/list",
                http_status=list_result.status_code,
            )
        return McpDiscoverOutput(
            tools=tools,
            initialized=initialized,
            phase="tools/list",
            http_status=list_result.status_code,
        )
