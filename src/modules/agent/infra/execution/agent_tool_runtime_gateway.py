from __future__ import annotations

from uuid import UUID

from modules.agent.application.dtos.tools_dtos import ExecuteToolInput
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.tool_runtime import MCP_AGENT_SESSION_INPUT_KEY
from modules.agent.application.runtime_tool_inventory import (
    execute_runtime_tool_inventory,
    is_runtime_tool_inventory_id,
)
from modules.agent.application.runtime_tool_use_cases import RuntimeExecuteToolUseCase
from modules.agent.application.tool_release_snapshots import tool_from_release_snapshot
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.infra.execution.tool_runtime_registry import build_tool_runtime_registry
from shared.infra.config import Settings


class AgentToolRuntimeGateway:
    """Tool runtime backed by explicit short-lived transaction phases."""

    def __init__(
        self,
        transactions: AgentRuntimeTransactionRunner,
        settings: Settings,
        executor: HttpToolExecutor | None = None,
    ) -> None:
        self._transactions = transactions
        self._settings = settings
        self._executor = executor or get_http_tool_executor()
        self._cipher = SecretCipherAdapter(settings.encryption_key)

    async def read_runtime_tools(self, tool_ids: list[UUID]):
        async def read(repositories, _outbox):
            tools = []
            for tool_id in tool_ids:
                tool = await repositories.tools.get_by_id(tool_id)
                if tool is not None:
                    tools.append(tool)
            return tools

        return await self._transactions.run(read)

    async def execute_tool(self, tool_id: UUID, input_data: dict) -> dict:
        if is_runtime_tool_inventory_id(tool_id):
            return execute_runtime_tool_inventory(input_data)

        runtime_input = dict(input_data or {})
        context = current_execution.get()
        if context and context.session_id:
            runtime_input[MCP_AGENT_SESSION_INPUT_KEY] = str(context.session_id)
        snapshot = (
            context.tool_snapshots.get(str(tool_id))
            if context and context.tool_snapshots
            else None
        )

        async def execute(repositories, _outbox):
            resolver = ToolSecretResolverAdapter(
                repositories.tool_secrets,
                self._cipher,
            )
            registry = build_tool_runtime_registry(
                settings=self._settings,
                executor=self._executor,
                secret_resolver=resolver,
            )
            if snapshot is not None:
                result = await registry.execute(
                    tool_from_release_snapshot(snapshot),
                    runtime_input,
                )
                return {
                    "success": result.success,
                    "output": result.output,
                    "duration_ms": result.duration_ms,
                    "error": result.error,
                }

            use_case = RuntimeExecuteToolUseCase(
                tool_repo=repositories.tools,
                runtime_registry=registry,
            )
            result = await use_case.execute(
                ExecuteToolInput(tool_id=tool_id, input_data=runtime_input)
            )
            return result.model_dump()

        return await self._transactions.run(execute)
