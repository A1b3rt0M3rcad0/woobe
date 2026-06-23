from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from modules.agent.application.ports import ToolExecutionPort


class McpDiscoverInput(BaseModel):
    server_url: str = Field(..., min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_ms: int = Field(default=30000, ge=1)


class McpDiscoveredTool(BaseModel):
    name: str
    title: str | None = None
    description: str | None = None
    input_schema: dict[str, Any] | None = None


class McpDiscoverOutput(BaseModel):
    tools: list[McpDiscoveredTool]
    initialized: bool = False
    error: str | None = None


def _parse_json_candidate(value: str) -> Any:
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _parse_sse_payload(value: str) -> Any:
    # Streamable HTTP MCP servers may return JSON-RPC messages as SSE frames:
    # event: message
    # data: {"jsonrpc":"2.0","result":...}
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


def _extract_body(output: dict[str, Any] | None) -> Any:
    if not output:
        return None
    body = output.get("body")
    if isinstance(body, str):
        return _parse_json_candidate(body) or _parse_sse_payload(body) or body
    return body


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
            )
        )
    return tools


class DiscoverMcpToolsUseCase:
    def __init__(self, executor: ToolExecutionPort) -> None:
        self._executor = executor

    async def execute(self, input_dto: McpDiscoverInput) -> McpDiscoverOutput:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **input_dto.headers,
        }

        initialized = False
        initialize_payload = {
            "jsonrpc": "2.0",
            "id": "initialize",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "ProjectRAI", "version": "0.1.0"},
            },
        }
        init_result = await self._executor.execute(
            method="POST",
            url=input_dto.server_url,
            headers=headers,
            body=json.dumps(initialize_payload),
            timeout_ms=input_dto.timeout_ms,
        )
        initialized = bool(init_result.success)

        if initialized:
            initialized_payload = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
            await self._executor.execute(
                method="POST",
                url=input_dto.server_url,
                headers=headers,
                body=json.dumps(initialized_payload),
                timeout_ms=input_dto.timeout_ms,
            )

        list_payload = {
            "jsonrpc": "2.0",
            "id": "tools-list",
            "method": "tools/list",
            "params": {},
        }
        list_result = await self._executor.execute(
            method="POST",
            url=input_dto.server_url,
            headers=headers,
            body=json.dumps(list_payload),
            timeout_ms=input_dto.timeout_ms,
        )
        if not list_result.success:
            return McpDiscoverOutput(
                tools=[],
                initialized=initialized,
                error=list_result.error or "MCP tools/list failed",
            )

        tools = _extract_tools(_extract_body(list_result.output))
        if not tools:
            return McpDiscoverOutput(
                tools=[],
                initialized=initialized,
                error="MCP server did not return any tools",
            )
        return McpDiscoverOutput(tools=tools, initialized=initialized)
