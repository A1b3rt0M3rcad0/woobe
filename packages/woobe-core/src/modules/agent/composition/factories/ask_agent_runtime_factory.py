from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from uuid import UUID

from modules.agent.application.context_assembler_registry import (
    build_runtime_context_assembler,
)
from modules.agent.application.execution_snapshot import (
    AgentExecutionSnapshotResolver,
    apply_agent_execution_snapshot,
)
from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.application.skill_bindings import (
    freeze_skill_bindings,
    frozen_enabled_skills,
)
from modules.agent.application.skill_runtime import SkillRuntime
from modules.agent.application.tool_release_snapshots import (
    tool_from_release_snapshot,
    tool_with_permission_overrides,
)
from modules.agent.composition.factories.agent_uow_factory import (
    build_agent_read_uow,
    build_agent_uow,
)
from modules.agent.composition.factories.rag_runtime_factory import (
    build_rag_runtime_adapter,
)
from modules.agent.composition.factories.run_persistence_factory import (
    build_agent_run_persistence,
)
from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner
from modules.agent.infra.execution.agent_run_recovery_runtime import (
    AgentRunRecoveryExecutor,
    AgentRunRecoveryRuntime,
)
from modules.agent.infra.execution.agent_tool_runtime_gateway import AgentToolRuntimeGateway
from modules.agent.infra.execution.canonical_execution_snapshot_runtime_resolver import (
    configure_execution_snapshot_runtime,
)
from modules.agent.infra.execution.frozen_snapshot_runtime import (
    FrozenSnapshotStructuredOutputRuntime,
)
from modules.agent.infra.execution.instrumented_execution_runner import (
    configure_skill_runtime,
)
from modules.agent.infra.execution.runtime_preparation import (
    configure_skill_binding_freezer,
)
from modules.agent.presentation.controllers.ask_agent_controller import AskAgentController
from shared.composition_resources import (
    EXECUTION_STATE_STORE,
    RUN_DURABILITY_BARRIER,
    RUN_EVENT_BUFFER,
)
from shared.infra.best_effort_execution_state import BestEffortExecutionStateStore
from shared.infra.config import Settings
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult

AskRequestHandler = Callable[[OperationRequest], Awaitable[OperationResult]]
InternalToolHandler = Callable[[dict], Awaitable[dict]]


def build_agent_runtime_transactions() -> AgentRuntimeTransactionRunner:
    return AgentRuntimeTransactionRunner(build_agent_uow, build_agent_read_uow)


def _build_runtime_components(
    settings: Settings,
    http_executor: HttpToolExecutor | None,
    *,
    internal_tool_handlers: Mapping[UUID, InternalToolHandler] | None = None,
) -> tuple[AgentRuntimeTransactionRunner, AgentToolRuntimeGateway]:
    configure_skill_runtime(frozen_enabled_skills, SkillRuntime)
    configure_skill_binding_freezer(freeze_skill_bindings)
    configure_execution_snapshot_runtime(
        AgentExecutionSnapshotResolver,
        apply_agent_execution_snapshot,
    )
    transactions = build_agent_runtime_transactions()
    executor = http_executor or get_http_tool_executor()
    tool_runtime = AgentToolRuntimeGateway(
        transactions,
        settings,
        executor,
        internal_tool_handlers=internal_tool_handlers,
    )
    return transactions, tool_runtime


def _resolve_context_assembler(
    settings: Settings,
    context_assembler: ContextAssembler | None,
) -> ContextAssembler:
    return (
        context_assembler
        if context_assembler is not None
        else build_runtime_context_assembler(settings.default_context_manager)
    )


def _configure_agent_runtime_dependencies(
    runtime: FrozenSnapshotStructuredOutputRuntime,
    *,
    settings: Settings,
    transactions: AgentRuntimeTransactionRunner,
    tool_runtime: AgentToolRuntimeGateway,
) -> None:
    runtime.configure_rag_runtime(
        build_rag_runtime_adapter(
            transactions,
            encryption_key=settings.encryption_key,
        )
    )
    runtime.configure_runtime_tool_reader(tool_runtime.read_runtime_tools)
    runtime.configure_execution_state_store(
        BestEffortExecutionStateStore(EXECUTION_STATE_STORE)
    )
    run_persistence = build_agent_run_persistence(settings)
    runtime.configure_run_persistence(run_persistence)
    if settings.run_persistence_mode == "event_journal":
        if RUN_EVENT_BUFFER is None or RUN_DURABILITY_BARRIER is None:
            raise RuntimeError(
                "event_journal Run persistence requires WOOBE_REDIS_URL and WOOBE_MONGODB_URL"
            )
        runtime.configure_run_event_journal(
            RUN_EVENT_BUFFER,
            RUN_DURABILITY_BARRIER,
        )


def _build_agent_runtime(
    settings: Settings,
    http_executor: HttpToolExecutor | None = None,
    *,
    internal_tool_handlers: Mapping[UUID, InternalToolHandler] | None = None,
    context_assembler: ContextAssembler | None = None,
) -> tuple[FrozenSnapshotStructuredOutputRuntime, AgentRuntimeTransactionRunner]:
    transactions, tool_runtime = _build_runtime_components(
        settings,
        http_executor,
        internal_tool_handlers=internal_tool_handlers,
    )
    runtime = FrozenSnapshotStructuredOutputRuntime(
        transactions=transactions,
        llm_factory=LangchainLLMFactory(),
        encryption_key=settings.encryption_key,
        tool_executor_factory=tool_runtime.execute_tool,
    )
    runtime.configure_context_assembler(
        _resolve_context_assembler(settings, context_assembler)
    )
    _configure_agent_runtime_dependencies(
        runtime,
        settings=settings,
        transactions=transactions,
        tool_runtime=tool_runtime,
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


def build_agent_run_recovery_executor(
    settings: Settings,
    http_executor: HttpToolExecutor | None = None,
    *,
    context_assembler: ContextAssembler | None = None,
) -> AgentRunRecoveryExecutor:
    if settings.run_persistence_mode != "event_journal":
        raise RuntimeError("Agent Run recovery executor requires event_journal persistence")
    transactions, tool_runtime = _build_runtime_components(settings, http_executor)
    runtime = AgentRunRecoveryRuntime(
        transactions=transactions,
        llm_factory=LangchainLLMFactory(),
        encryption_key=settings.encryption_key,
        tool_executor_factory=tool_runtime.execute_tool,
    )
    runtime.configure_context_assembler(
        _resolve_context_assembler(settings, context_assembler)
    )
    runtime.configure_recovery_tool_runtime(
        tool_from_snapshot=tool_from_release_snapshot,
        tool_with_permissions=tool_with_permission_overrides,
        tool_definition_builder=tool_runtime.build_tool_definitions,
    )
    _configure_agent_runtime_dependencies(
        runtime,
        settings=settings,
        transactions=transactions,
        tool_runtime=tool_runtime,
    )
    return AgentRunRecoveryExecutor(runtime)


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
