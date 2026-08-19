from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.dtos.tools_dtos import ExecuteToolInput
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.runtime_tool_inventory import (
    execute_runtime_tool_inventory,
    is_runtime_tool_inventory_id,
)
from modules.agent.application.runtime_tool_use_cases import RuntimeExecuteToolUseCase
from modules.agent.application.tool_release_snapshots import tool_from_release_snapshot
from modules.agent.application.tool_runtime import MCP_AGENT_SESSION_INPUT_KEY
from modules.agent.composition.composers.tool_runtime_factory import build_tool_runtime_registry
from modules.agent.composition.runtime.runtime_environment_guard import (
    AgentRuntimeEnvironmentGuard,
)
from modules.agent.composition.runtime.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_embedding_factory import LangchainEmbeddingFactory
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.ask_agent_controller import AskAgentController
from shared.infra.config import Settings
from shared.infra.transactional_handler import TransactionalHandler
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


AskHttpHandler = Callable[[Request], Awaitable[Response]]


def _build_ask_handler(
    session_factory: async_sessionmaker[AsyncSession],
    http_executor: HttpToolExecutor | None = None,
) -> AskHttpHandler:
    settings = Settings.model_validate({})
    llm_factory = LangchainLLMFactory()
    cipher = SecretCipherAdapter(settings.encryption_key)
    executor = http_executor or get_http_tool_executor()

    async def read_runtime_tools(tool_ids: list[UUID]):
        async with AgentUnitOfWork(session_factory) as uow:
            tools = []
            for tool_id in tool_ids:
                tool = await uow.tools.get_by_id(tool_id)
                if tool is not None:
                    tools.append(tool)
            return tools

    async def execute_tool(tool_id: UUID, input_data: dict) -> dict:
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

        async with AgentUnitOfWork(session_factory) as uow:
            resolver = ToolSecretResolverAdapter(uow.tool_secrets, cipher)
            registry = build_tool_runtime_registry(
                settings=settings,
                executor=executor,
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
                tool_repo=uow.tools,
                runtime_registry=registry,
            )
            result = await use_case.execute(
                ExecuteToolInput(tool_id=tool_id, input_data=runtime_input)
            )
            return result.model_dump()

    use_case = StructuredOutputAskAgentUseCase(
        session_factory=session_factory,
        llm_factory=llm_factory,
        encryption_key=settings.encryption_key,
        tool_executor_factory=execute_tool,
    )
    use_case.configure_rag_embedding_factory(LangchainEmbeddingFactory())
    use_case.configure_runtime_tool_reader(read_runtime_tools)
    guarded_use_case = AgentRuntimeEnvironmentGuard(
        use_case,
        session_factory,
        default_environment="production",
    )
    return AskAgentController(guarded_use_case).handle


def ask_agent_composer(
    session_factory: async_sessionmaker[AsyncSession],
    http_executor: HttpToolExecutor | None = None,
) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    return TransactionalHandler(
        uow,
        _build_ask_handler(session_factory, http_executor),
    )
