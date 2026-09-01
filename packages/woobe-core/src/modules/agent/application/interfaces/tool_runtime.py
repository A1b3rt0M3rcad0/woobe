from __future__ import annotations

from typing import Any

from modules.agent.application.interfaces.ports import ExecutionResult, ToolRuntimePort
from modules.agent.application.interfaces.tool_types import normalize_tool_protocol

MCP_REMOTE_TOOL_INPUT_KEY = "__mcp_tool_name"
MCP_AGENT_SESSION_INPUT_KEY = "__projectrai_agent_session_id"

ERROR_UNSUPPORTED_RUNTIME = "UNSUPPORTED_RUNTIME"


def _safe_tool_name(tool: Any) -> str:
    name = str(getattr(tool, "name", "")).lower().strip().replace(" ", "_").replace("-", "_")
    name = "".join(c for c in name if c.isalnum() or c == "_")
    if not name or name[0].isdigit():
        name = f"tool_{name}"
    return name


class UnsupportedToolRuntime(ToolRuntimePort):
    def __init__(self, protocol: str) -> None:
        self._protocol = protocol

    async def execute(
        self,
        tool: Any,
        input_data: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        message = f"Tool runtime is not supported for protocol '{self._protocol}'"
        return ExecutionResult(
            success=False,
            error=message,
            output={
                "error_code": ERROR_UNSUPPORTED_RUNTIME,
                "message": message,
                "protocol": self._protocol,
            },
        )

    async def test(
        self,
        config: dict[str, Any],
        input_data: dict[str, Any] | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        message = f"Tool runtime is not supported for protocol '{self._protocol}'"
        return ExecutionResult(
            success=False,
            error=message,
            output={
                "error_code": ERROR_UNSUPPORTED_RUNTIME,
                "message": message,
                "protocol": self._protocol,
            },
        )

    def to_openai_definition(self, tool: Any) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": _safe_tool_name(tool),
                "description": getattr(tool, "description", None)
                or "Unsupported tool runtime",
                "parameters": getattr(tool, "input_schema", None)
                or {"type": "object", "properties": {}, "required": []},
            },
        }


class ToolRuntimeRegistry:
    def __init__(self, runtimes: dict[str, ToolRuntimePort]) -> None:
        self._runtimes = runtimes

    def runtime_for(self, tool_type: Any) -> ToolRuntimePort:
        protocol = normalize_tool_protocol(tool_type)
        return self._runtimes.get(protocol) or UnsupportedToolRuntime(protocol)

    async def execute(
        self,
        tool: Any,
        input_data: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        return await self.runtime_for(getattr(tool, "type", None)).execute(
            tool,
            input_data or {},
        )

    async def test(
        self,
        tool_type: Any,
        config: dict[str, Any],
        input_data: dict[str, Any] | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        return await self.runtime_for(tool_type).test(
            config,
            input_data or {},
            timeout_ms=timeout_ms,
        )

    def to_openai_definition(self, tool: Any) -> dict[str, Any]:
        return self.runtime_for(getattr(tool, "type", None)).to_openai_definition(tool)
