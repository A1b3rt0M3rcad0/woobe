from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from uuid import UUID

from modules.agent.application.context_assembler_registry import (
    build_runtime_context_assembler,
)
from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.composition.factories.agent_uow_factory import (
    build_agent_read_uow,
    build_agent_uow,
)
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_embedding_factory import LangchainEmbeddingFactory
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner
from modules.agent.infra.database.runtime_vector_search_reader import AgentRuntimeVectorSearchReader
from modules.agent.infra.execution.agent_tool_runtime_gateway import AgentToolRuntimeGateway
from modules.agent.infra.execution.frozen_snapshot_runtime import (
    FrozenSnapshotStructuredOutputRuntime,
)
from modules.agent.presentation.controllers.ask_agent_controller import AskAgentController
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.infra.best_effort_execution_state import BestEffortExecutionStateStore
from shared.infra.config import Settings
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult

AskRequestHandler = Callable[[OperationRequest], Awaitable[OperationResult]]
InternalToolHandler = Callable[[dict], Awaitable[dict]]


def build_agent_runtime_transactions() -> AgentRuntimeTransactionRunner:
    return AgentRuntimeTransactionRunner(build_agent_uow, build_agent_read_uow)


def _build_agent_runtime(
    settings: Settings,
    http_executor: HttpToolExecutor | None = None,
    *,
    internal_tool_handlers: Mapping[UUID, InternalToolHandler] | None = None,
    context_assembler: ContextAssembler | None = None,
) -> tuple[FrozenSnapshotStructuredOutputRuntime, AgentRuntimeTransactionRunner]:
    transactions = build_agent_runtime_transactions()
    executor = http_executor or get_http_tool_executor()
    tool_runtime = AgentToolRuntimeGateway(
        transactions,
        settings,
        executor,
        internal_tool_handlers=internal_tool_handlers,
    )
    runtime = FrozenSnapshotStructuredOutputRuntime(
        transactions=transactions,
        llm_factory=LangchainLLMFactory(),
        encryption_key=settings.encryption_key,
        tool_executor_factory=tool_runtime.execute_tool,
    )
    assembler: ContextAssembler = (
        context_assembler
        if context_assembler is not None
        else build_runtime_context_assembler(settings.default_context_manager)
    )
    runtime.configure_context_assembler(assembler)
    runtime.configure_rag_embedding_factory(LangchainEmbeddingFactory())
    runtime.configure_runtime_tool_reader(tool_runtime.read_runtime_tools)

    runtime.configure_vector_search_reader(
        AgentRuntimeVectorSearchReader(transactions).search
    )
    # Standalone Agent execution must remain valid when realtime infrastructure
    # degrades. Redis is an observability/reattach path here, not the durable Run.
    runtime.configure_execution_state_store(
        BestEffortExecutionStateStore(EXECUTION_STATE_STORE)
    )
    return runtime, transactions


def build_ask_agent_use_case(
    settings: Settings,
    http_executor: HttpToolExecutor | None = None,
    *,
    context_assembler: ContextAssembler | None = None,
) -> tuple[FrozenSnapshotStructuredOutputRuntime, AgentRuntimeTransactionRunner]:
    return _build_agent_runtime(
        settings,
        http_executor,
        context_assembler=context_assembler,
    )


def build_internal_agent_runtime(
    settings: Settings,
    http_executor: HttpToolExecutor | None = None,
    *,
    internal_tool_handlers: Mapping[UUID, InternalToolHandler] | None = None,
    context_assembler: ContextAssembler | None = None,
) -> FrozenSnapshotStructuredOutputRuntime:
    runtime, _transactions = _build_agent_runtime(
        settings,
        http_executor,
        internal_tool_handlers=internal_tool_handlers,
        context_assembler=context_assembler,
    )
    return runtime


def build_ask_agent_handler(
    settings: Settings,
    http_executor: HttpToolExecutor | None = None,
    *,
    context_assembler: ContextAssembler | None = None,
) -> AskRequestHandler:
    runtime, _transactions = build_ask_agent_use_case(
        settings,
        http_executor,
        context_assembler=context_assembler,
    )
    return AskAgentController(runtime).handle
