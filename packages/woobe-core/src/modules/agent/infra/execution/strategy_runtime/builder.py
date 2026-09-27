from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_strategy import (
    ExecutionStrategy,
    ExecutionStrategyRequest,
)
from modules.agent.application.strategy_sdk import (
    StrategyBootstrap,
    StrategyContextContribution,
    StrategyToolCall,
)
from modules.agent.infra.execution.capabilities.bundle import (
    ExecutionCapabilities,
    build_execution_capabilities,
)
from modules.agent.infra.execution.capabilities.preparation import (
    PreparedExecution,
    prepare_execution,
)
from modules.agent.infra.execution.strategy_runtime.checkpoint import (
    RuntimeStrategyCheckpoint,
)
from modules.agent.infra.execution.strategy_runtime.context import RuntimeStrategyContext
from modules.agent.infra.execution.strategy_runtime.context_manager import (
    RuntimeStrategyContextManager,
)
from modules.agent.infra.execution.strategy_runtime.conversation import (
    RuntimeStrategyConversation,
)
from modules.agent.infra.execution.strategy_runtime.knowledge import RuntimeStrategyKnowledge
from modules.agent.infra.execution.strategy_runtime.model import RuntimeStrategyModel
from modules.agent.infra.execution.strategy_runtime.output import RuntimeStrategyOutput
from modules.agent.infra.execution.strategy_runtime.runtime_state import StrategyRuntimeState
from modules.agent.infra.execution.strategy_runtime.state import RuntimeStrategyStateStore
from modules.agent.infra.execution.strategy_runtime.tools import RuntimeStrategyTools


@dataclass(frozen=True, slots=True)
class BuiltStrategyContext:
    context: RuntimeStrategyContext[Any]
    runtime_state: StrategyRuntimeState


@dataclass(frozen=True, slots=True)
class BuiltStrategyExecution:
    context: RuntimeStrategyContext[Any]
    runtime_state: StrategyRuntimeState
    prepared: PreparedExecution


def _next_call_index(cursor: dict[str, Any] | None) -> int:
    if cursor is None:
        return 1
    try:
        next_call_index = int(cursor.get("next_call_index") or 1)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Execution Strategy recovery cursor has invalid call index") from exc
    if next_call_index <= 0:
        raise RuntimeError("Execution Strategy recovery cursor has invalid call index")
    return next_call_index


def _preflight_tool_call(
    bootstrap: dict[str, Any] | None,
    *,
    resuming: bool,
) -> StrategyToolCall | None:
    if resuming or not bootstrap:
        return None
    value = bootstrap.get("initial_tool_call")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Execution Strategy initial_tool_call must be a mapping")
    name = value.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Execution Strategy initial_tool_call requires a Tool name")
    args = value.get("args")
    if not isinstance(args, dict):
        args = {}
    call_id = value.get("id")
    return StrategyToolCall(
        id=str(call_id) if call_id is not None else None,
        name=name,
        arguments=args,
    )


def build_strategy_context_from_capabilities(
    *,
    strategy: ExecutionStrategy[Any],
    capabilities: ExecutionCapabilities,
    messages: list[Any],
    initial_phase: str | None = None,
    final_model: Any | None = None,
    final_model_factory: Any | None = None,
    final_json_instruction: str | None = None,
    tool_definitions: list[dict[str, Any]] | None = None,
    bootstrap: dict[str, Any] | None = None,
) -> BuiltStrategyContext:
    resume = capabilities.recovery.load()
    cursor = dict(resume.cursor) if resume is not None else None
    next_call_index = _next_call_index(cursor)

    runtime_state = StrategyRuntimeState(
        execution=(
            resume.execution if resume is not None else InstrumentedExecution(result=None)
        ),
        call_index=max(0, next_call_index - 1),
        messages=[
            *messages,
            *(resume.capability_messages if resume is not None else []),
        ],
        base_message_count=len(messages),
        context_contributions={
            key: StrategyContextContribution(
                key=str(value.get("key") or key),
                source_type=str(value.get("source_type") or "RUNTIME"),
                content=value.get("content"),
                metadata=(
                    dict(value.get("metadata"))
                    if isinstance(value.get("metadata"), dict)
                    else {}
                ),
            )
            for key, value in (
                resume.context_contributions.items()
                if resume is not None
                else ()
            )
        },
        context_replacements={
            key: tuple(
                int(index)
                for index in (
                    value.get("replaces_message_indexes")
                    if isinstance(value.get("replaces_message_indexes"), list)
                    else ()
                )
                if isinstance(index, int) and index >= 0
            )
            for key, value in (
                resume.context_contributions.items()
                if resume is not None
                else ()
            )
            if isinstance(value, dict)
        },
    )
    state_store = RuntimeStrategyStateStore()
    state = state_store.create(
        strategy.state_type,
        cursor,
        strategy_name=strategy.name,
    )
    checkpoint = RuntimeStrategyCheckpoint(
        recovery=capabilities.recovery,
        runtime_state=runtime_state,
        state_store=state_store,
    )
    runtime_tools = RuntimeStrategyTools(
        capability=capabilities.tools,
        runtime_state=runtime_state,
    )
    runtime_model = RuntimeStrategyModel(
        capability=capabilities.model,
        runtime_state=runtime_state,
        final_model=final_model,
        final_model_factory=final_model_factory,
        fallback_model_factory=None,
        tool_definitions=tool_definitions,
    )
    context = RuntimeStrategyContext(
        state=state,
        bootstrap=StrategyBootstrap(
            initial_tool_call=_preflight_tool_call(
                bootstrap,
                resuming=resume is not None,
            ),
        ),
        conversation=RuntimeStrategyConversation(
            runtime_state=runtime_state,
            base_messages=messages,
        ),
        model=runtime_model,
        tools=runtime_tools,
        knowledge=RuntimeStrategyKnowledge(
            capability=capabilities.knowledge,
            runtime_state=runtime_state,
        ),
        context=RuntimeStrategyContextManager(
            capability=capabilities.context,
            runtime_state=runtime_state,
            base_messages=messages,
            final_json_instruction=final_json_instruction,
            model=runtime_model,
        ),
        output=RuntimeStrategyOutput.disabled(runtime_state=runtime_state),
        checkpoint=checkpoint,
    )
    return BuiltStrategyContext(
        context=context,
        runtime_state=runtime_state,
    )


def build_strategy_execution(
    *,
    strategy: ExecutionStrategy[Any],
    request: ExecutionStrategyRequest,
) -> BuiltStrategyExecution:
    prepared = prepare_execution(request)
    capabilities = build_execution_capabilities(
        prepared=prepared,
        strategy_name=strategy.name,
    )
    built = build_strategy_context_from_capabilities(
        strategy=strategy,
        capabilities=capabilities,
        messages=prepared.messages,
        final_model=prepared.final_model,
        final_model_factory=prepared.final_model_factory,
        final_json_instruction=prepared.final_json_instruction,
        tool_definitions=prepared.tool_definitions,
    )
    built.context.model.set_fallback_model_factory(
        prepared.fallback_model_factory
    )
    built.context.output = RuntimeStrategyOutput.from_prepared(
        prepared=prepared,
        runtime_state=built.runtime_state,
    )
    return BuiltStrategyExecution(
        context=built.context,
        runtime_state=built.runtime_state,
        prepared=prepared,
    )
