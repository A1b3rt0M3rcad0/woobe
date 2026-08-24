from __future__ import annotations

from collections.abc import Awaitable, Callable

from modules.agent.composition.factories.agent_uow_factory import build_agent_uow
from modules.agent.infra.adapters.agent_runtime_environment_guard import (
    AgentRuntimeEnvironmentGuard,
)
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_embedding_factory import (
    LangchainEmbeddingFactory,
)
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.infra.execution.agent_tool_runtime_gateway import AgentToolRuntimeGateway
from modules.agent.infra.execution.transaction_bounded_structured_output import (
    TransactionBoundedStructuredOutputAskAgentUseCase,
)
from modules.agent.presentation.controllers.ask_agent_controller import AskAgentController
from shared.infra.config import Settings
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


AskHttpHandler = Callable[[Request], Awaitable[Response]]


def build_agent_runtime_transactions() -> AgentRuntimeTransactionRunner:
    return AgentRuntimeTransactionRunner(build_agent_uow)


def build_ask_agent_use_case(
    settings: Settings,
    http_executor: HttpToolExecutor | None = None,
) -> tuple[
    TransactionBoundedStructuredOutputAskAgentUseCase,
    AgentRuntimeTransactionRunner,
]:
    transactions = build_agent_runtime_transactions()
    executor = http_executor or get_http_tool_executor()
    tool_runtime = AgentToolRuntimeGateway(transactions, settings, executor)
    use_case = TransactionBoundedStructuredOutputAskAgentUseCase(
        transactions=transactions,
        llm_factory=LangchainLLMFactory(),
        encryption_key=settings.encryption_key,
        tool_executor_factory=tool_runtime.execute_tool,
    )
    use_case.configure_rag_embedding_factory(LangchainEmbeddingFactory())
    use_case.configure_runtime_tool_reader(tool_runtime.read_runtime_tools)
    return use_case, transactions


def build_ask_agent_handler(
    settings: Settings,
    http_executor: HttpToolExecutor | None = None,
) -> AskHttpHandler:
    use_case, transactions = build_ask_agent_use_case(settings, http_executor)
    guarded_use_case = AgentRuntimeEnvironmentGuard(
        use_case,
        transactions,
        default_environment="production",
    )
    return AskAgentController(guarded_use_case).handle
