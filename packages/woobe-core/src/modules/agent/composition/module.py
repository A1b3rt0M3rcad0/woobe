from __future__ import annotations

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.interfaces.runtime_environment import (
    RuntimeEnvironmentGuard,
)
from modules.agent.application.runtime_output_validation import EmptyModelOutputError
from modules.agent.composition.composers.public_runtime_composers import (
    public_run_composer,
)
from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_ask_agent_use_case,
    build_internal_agent_runtime,
)
from modules.agent.composition.factories.agent_uow_factory import (
    build_agent_read_uow,
    build_agent_uow,
)
from modules.agent.composition.resources import EXECUTION_STATE_STORE
from modules.agent.composition.resources import SETTINGS
from modules.agent.infra.adapters.http_tool_runtime import (
    close_http_tool_executor,
    configure_http_tool_executor,
    get_http_tool_executor,
)
from modules.agent.infra.adapters.langchain_embedding_factory import (
    LangchainEmbeddingFactory,
)
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.runtime_environment_guard import (
    build_agent_runtime_environment_guard,
)
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.execution.agent_tool_runtime_gateway import AgentToolRuntimeGateway
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)
from modules.agent.infra.execution.agent_run_reattach_service import (
    AgentRunReattachService,
)
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import (
    RuntimeStreamChannel,
    current_runtime_stream,
)
from modules.agent.infra.execution.transaction_bounded_structured_output import (
    TransactionBoundedStructuredOutputRuntime,
)
from shared.composition_resources import RUN_EVENT_JOURNAL


def build_http_tool_executor() -> HttpToolExecutor:
    executor = HttpToolExecutor(
        default_timeout_ms=SETTINGS.http_tool_timeout_max_ms,
        max_timeout_ms=SETTINGS.http_tool_timeout_max_ms,
        max_response_bytes=SETTINGS.http_tool_response_max_bytes,
        allow_local_networks=SETTINGS.http_tool_allow_local_networks,
    )
    configure_http_tool_executor(executor)
    return executor


def build_agent_stream_service() -> AskAgentStreamService:
    runtime, transactions = build_ask_agent_use_case(
        SETTINGS,
        get_http_tool_executor(),
    )
    return AskAgentStreamService(runtime, transactions)


def build_agent_stream_components() -> tuple[
    AskAgentStreamService,
    RuntimeEnvironmentGuard,
]:
    runtime, transactions = build_ask_agent_use_case(
        SETTINGS,
        get_http_tool_executor(),
    )
    return (
        AskAgentStreamService(runtime, transactions),
        build_agent_runtime_environment_guard(transactions),
    )


def build_agent_run_reattach_operations() -> AgentRunReattachService:
    transactions = AgentRuntimeTransactionRunner(
        build_agent_uow,
        build_agent_read_uow,
    )
    return AgentRunReattachService(
        transactions=transactions,
        state_store=EXECUTION_STATE_STORE,
        journal=RUN_EVENT_JOURNAL,
    )


StructuredOutputAskAgentUseCase = TransactionBoundedStructuredOutputRuntime


__all__ = [
    "AgentToolRuntimeGateway",
    "AskInput",
    "EmptyModelOutputError",
    "HttpToolExecutor",
    "LangchainEmbeddingFactory",
    "LangchainLLMFactory",
    "RuntimeStreamChannel",
    "SETTINGS",
    "StructuredOutputAskAgentUseCase",
    "build_agent_stream_service",
    "build_agent_stream_components",
    "build_agent_run_reattach_operations",
    "build_http_tool_executor",
    "build_internal_agent_runtime",
    "close_http_tool_executor",
    "current_execution",
    "current_runtime_stream",
    "new_execution_context",
    "public_run_composer",
]
