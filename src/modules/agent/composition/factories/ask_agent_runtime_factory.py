from __future__ import annotations

from collections.abc import Awaitable, Callable

from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_embedding_factory import (
    LangchainEmbeddingFactory,
)
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.database import AgentDatabase, agent_session_factory
from modules.agent.presentation.controllers.ask_agent_controller import AskAgentController
from modules.agent.runtime.agent_tool_runtime_gateway import AgentToolRuntimeGateway
from modules.agent.runtime.runtime_environment_guard import AgentRuntimeEnvironmentGuard
from modules.agent.runtime.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)
from shared.infra.config import Settings
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


AskHttpHandler = Callable[[Request], Awaitable[Response]]


def build_ask_agent_handler(
    database: AgentDatabase,
    settings: Settings,
    http_executor: HttpToolExecutor | None = None,
) -> AskHttpHandler:
    executor = http_executor or get_http_tool_executor()
    tool_runtime = AgentToolRuntimeGateway(database, settings, executor)
    use_case = StructuredOutputAskAgentUseCase(
        session_factory=agent_session_factory(database),
        llm_factory=LangchainLLMFactory(),
        encryption_key=settings.encryption_key,
        tool_executor_factory=tool_runtime.execute_tool,
    )
    use_case.configure_rag_embedding_factory(LangchainEmbeddingFactory())
    use_case.configure_runtime_tool_reader(tool_runtime.read_runtime_tools)
    guarded_use_case = AgentRuntimeEnvironmentGuard(
        use_case,
        agent_session_factory(database),
        default_environment="production",
    )
    return AskAgentController(guarded_use_case).handle
