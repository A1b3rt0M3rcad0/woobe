from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from uuid import UUID

from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.tool_runtime import MCP_AGENT_SESSION_INPUT_KEY
from modules.agent.application.runtime_tool_inventory import (
    execute_runtime_tool_inventory,
    is_runtime_tool_inventory_id,
)
from modules.agent.application.tool_release_snapshots import tool_from_release_snapshot
from modules.agent.domain.enums import ToolStatus
from modules.agent.domain.errors import ToolNotFoundError
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.runtime_secret_resolver import RuntimeToolSecretResolver
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.execution.tool_invocation_metrics import (
    record_tool_provider_latency,
)
from modules.agent.infra.execution.tool_runtime_registry import build_tool_runtime_registry
from shared.infra.config import Settings

InternalToolHandler = Callable[[dict], Awaitable[dict]]


class AgentToolRuntimeGateway:
    """Execute Tools from the immutable acceptance-time Run material only."""

    def __init__(
        self,
        _transactions: Any,
        settings: Settings,
        executor: HttpToolExecutor | None = None,
        *,
        internal_tool_handlers: Mapping[UUID, InternalToolHandler] | None = None,
    ) -> None:
        self._settings = settings
        self._executor = executor or get_http_tool_executor()
        self._internal_tool_handlers = dict(internal_tool_handlers or {})
        self._secret_resolver = RuntimeToolSecretResolver()

    async def read_runtime_tools(self, tool_ids: list[UUID]):
        context = current_execution.get()
        prepared = context.prepared_tools if context else None
        if prepared is None:
            raise RuntimeError("Agent Tool state was not prepared during Run acceptance")
        tools = []
        for tool_id in tool_ids:
            tool = prepared.get(str(tool_id))
            if tool is None:
                raise ToolNotFoundError(tool_id)
            tools.append(tool)
        return tools

    async def execute_tool(self, tool_id: UUID, input_data: dict) -> dict:
        context = current_execution.get()
        dynamic_handlers = context.internal_tool_handlers if context else None
        internal_handler = (dynamic_handlers or {}).get(tool_id)
        if internal_handler is None:
            internal_handler = self._internal_tool_handlers.get(tool_id)
        if internal_handler is not None:
            return await internal_handler(dict(input_data or {}))
        if is_runtime_tool_inventory_id(tool_id):
            return execute_runtime_tool_inventory(input_data)

        runtime_input = dict(input_data or {})
        if context and context.session_id:
            runtime_input.setdefault(MCP_AGENT_SESSION_INPUT_KEY, str(context.session_id))

        snapshot = (
            (context.tool_snapshots or {}).get(str(tool_id))
            if context is not None
            else None
        )
        if snapshot is not None:
            tool = tool_from_release_snapshot(snapshot)
        else:
            prepared = context.prepared_tools if context else None
            tool = prepared.get(str(tool_id)) if prepared else None
            if tool is None or tool.status != ToolStatus.ACTIVE:
                raise ToolNotFoundError(tool_id)

        registry = build_tool_runtime_registry(
            settings=self._settings,
            executor=self._executor,
            secret_resolver=self._secret_resolver,
        )
        result = await registry.execute(tool, runtime_input)
        # Provider timing is operational metadata. Capture it out-of-band so the
        # logical Tool result consumed by Agents/Networks remains stable.
        record_tool_provider_latency(result.duration_ms)
        return {
            "success": result.success,
            "output": result.output,
            "duration_ms": result.duration_ms,
            "error": result.error,
        }
