from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.infra.adapters.agent_runtime_environment_guard import (
    AgentRuntimeEnvironmentGuard,
)
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_embedding_factory import (
    LangchainEmbeddingFactory,
)
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.execution.agent_tool_runtime_gateway import AgentToolRuntimeGateway
from modules.agent.infra.execution.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)
from modules.agent.presentation.controllers.ask_agent_controller import AskAgentController
from shared.infra.config import Settings
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


AskHttpHandler = Callable[[Request], Awaitable[Response]]


def build_ask_agent_handler(
    engine: AsyncEngine,
    settings: Settings,
    http_executor: HttpToolExecutor | None = None,
) -> AskHttpHandler:
    executor = http_executor or get_http_tool_executor()
    tool_runtime = AgentToolRuntimeGateway(engine, settings, executor)
    use_case = StructuredOutputAskAgentUseCase(
        session_factory=engine,
        llm_factory=LangchainLLMFactory(),
        encryption_key=settings.encryption_key,
        tool_executor_factory=tool_runtime.execute_tool,
    )
    use_case.configure_rag_embedding_factory(LangchainEmbeddingFactory())
    use_case.configure_runtime_tool_reader(tool_runtime.read_runtime_tools)
    guarded_use_case = AgentRuntimeEnvironmentGuard(
        use_case,
        engine,
        default_environment="production",
    )
    return AskAgentController(guarded_use_case).handle
