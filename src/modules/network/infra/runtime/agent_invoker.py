from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.composers.tool_runtime_factory import (
    build_tool_runtime_registry,
)
from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.dtos.tools_dtos import ExecuteToolInput
from modules.agent.application.runtime_tool_inventory import (
    execute_runtime_tool_inventory,
    is_runtime_tool_inventory_id,
)
from modules.agent.application.runtime_tool_use_cases import RuntimeExecuteToolUseCase
from modules.agent.application.tool_release_snapshots import tool_from_release_snapshot
from modules.agent.application.tool_runtime import MCP_AGENT_SESSION_INPUT_KEY
from modules.agent.application.use_cases.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.use_cases.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_embedding_factory import (
    LangchainEmbeddingFactory,
)
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.network.application.runtime import (
    AgentInvocationResult,
    InternalDelegationTool,
)
from modules.network.application.runtime_failures import classify_runtime_exception
from shared.infra.config import Settings


class ProjectRAIAgentInvoker:
    """Invokes the existing Agent runtime in-process with Network-only tools."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def invoke(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        release_id: UUID | None,
        snapshot_override: dict[str, Any] | None,
        message: str,
        agent_session_id: UUID | None,
        execution_context: str,
        internal_tools: list[InternalDelegationTool],
        network_context: dict[str, object],
    ) -> AgentInvocationResult:
        settings = self._settings
        cipher = SecretCipherAdapter(settings.encryption_key)
        http_executor = get_http_tool_executor()
        internal_handlers = {tool.id: tool.handler for tool in internal_tools}

        async def read_runtime_tools(tool_ids: list[UUID]):
            async with AgentUnitOfWork(self._session_factory) as uow:
                tools = []
                for tool_id in tool_ids:
                    tool = await uow.tools.get_by_id(tool_id)
                    if tool is not None:
                        tools.append(tool)
                return tools

        async def execute_tool(tool_id: UUID, input_data: dict) -> dict:
            internal_handler = internal_handlers.get(tool_id)
            if internal_handler is not None:
                return await internal_handler(dict(input_data or {}))
            if is_runtime_tool_inventory_id(tool_id):
                return execute_runtime_tool_inventory(input_data)

            runtime_input = dict(input_data or {})
            context = current_execution.get()
            active_session_id = context.session_id if context else agent_session_id
            if active_session_id:
                runtime_input[MCP_AGENT_SESSION_INPUT_KEY] = str(active_session_id)
            snapshot = (
                context.tool_snapshots.get(str(tool_id))
                if context and context.tool_snapshots
                else None
            )
            async with AgentUnitOfWork(self._session_factory) as uow:
                resolver = ToolSecretResolverAdapter(uow.tool_secrets, cipher)
                registry = build_tool_runtime_registry(
                    settings=settings,
                    executor=http_executor,
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
                result = await RuntimeExecuteToolUseCase(
                    tool_repo=uow.tools,
                    runtime_registry=registry,
                ).execute(ExecuteToolInput(tool_id=tool_id, input_data=runtime_input))
                return result.model_dump()

        use_case = StructuredOutputAskAgentUseCase(
            session_factory=self._session_factory,
            llm_factory=LangchainLLMFactory(),
            encryption_key=settings.encryption_key,
            tool_executor_factory=execute_tool,
        )
        use_case.configure_rag_embedding_factory(LangchainEmbeddingFactory())
        use_case.configure_runtime_tool_reader(read_runtime_tools)

        context = new_execution_context()
        context.project_id = project_id
        context.agent_id = agent_id
        context.session_id = agent_session_id
        context.execution_context = execution_context
        context.agent_release_id = release_id
        context.internal_tool_definitions = [
            tool.definition() for tool in internal_tools
        ]
        context.internal_tool_name_to_id = {
            tool.name: str(tool.id) for tool in internal_tools
        }
        uuid_context_fields = {
            "network_id",
            "network_version_id",
            "network_session_id",
            "network_execution_id",
            "network_invocation_id",
            "parent_invocation_id",
            "network_node_id",
        }
        for key, value in network_context.items():
            if hasattr(context, key):
                if key in uuid_context_fields and value is not None:
                    value = UUID(str(value))
                setattr(context, key, value)

        token = current_execution.set(context)
        try:
            try:
                output = await use_case.execute(
                    AskInput(
                        project_id=project_id,
                        agent_id=agent_id,
                        message=message,
                        session_id=agent_session_id,
                        metadata={"source": "network_runtime", **network_context},
                        execution_context=execution_context,
                        loaded_release_id=release_id,
                        snapshot_override=snapshot_override,
                    )
                )
            except Exception as exc:
                failure = classify_runtime_exception(exc).with_agent_context(
                    trace_id=context.trace_id,
                    agent_session_id=context.session_id,
                )
                raise failure from exc
            return AgentInvocationResult(
                answer=output.answer,
                session_id=output.session_id,
                trace_id=output.trace_id,
                provider=output.provider,
                model=output.model,
                usage=output.usage.model_dump() if output.usage else None,
                tool_calls=[item.model_dump() for item in output.tool_calls],
                sources=[item.model_dump() for item in output.sources],
                parsed_output=output.parsed_output,
                output_parse_error=output.output_parse_error,
            )
        finally:
            current_execution.reset(token)
