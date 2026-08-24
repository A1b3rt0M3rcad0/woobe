from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine

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
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentToolRepository,
    SQLAlchemyAgentToolSecretRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.execution.tool_runtime_registry import build_tool_runtime_registry
from shared.infra.config import Settings


class AgentToolRuntimeGateway:
    """Short-lived persistence boundary for Agent execution Tool operations."""

    def __init__(
        self,
        engine: AsyncEngine,
        settings: Settings,
        executor: HttpToolExecutor | None = None,
    ) -> None:
        self._engine = engine
        self._settings = settings
        self._executor = executor or get_http_tool_executor()
        self._cipher = SecretCipherAdapter(settings.encryption_key)

    async def read_runtime_tools(self, tool_ids: list[UUID]):
        async with AgentUnitOfWork(self._engine) as uow:
            tool_repo = SQLAlchemyAgentToolRepository(uow)
            tools = []
            for tool_id in tool_ids:
                tool = await tool_repo.get_by_id(tool_id)
                if tool is not None:
                    tools.append(tool)
            return tools

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

        async with AgentUnitOfWork(self._engine) as uow:
            tool_repo = SQLAlchemyAgentToolRepository(uow)
            tool_secret_repo = SQLAlchemyAgentToolSecretRepository(uow)
            resolver = ToolSecretResolverAdapter(tool_secret_repo, self._cipher)
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
                tool_repo=tool_repo,
                runtime_registry=registry,
            )
            result = await use_case.execute(
                ExecuteToolInput(tool_id=tool_id, input_data=runtime_input)
            )
            return result.model_dump()
