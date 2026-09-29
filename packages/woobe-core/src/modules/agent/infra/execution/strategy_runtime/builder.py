from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.knowledge import KnowledgeStrategy
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


def _restored_replacement_ids(
    value: dict[str, Any],
    messages: list[Any],
) -> tuple[str, ...]:
    raw_ids = value.get("replaces_message_ids")
    if isinstance(raw_ids, list):
        return tuple(
            normalized
            for item in raw_ids
            if isinstance(item, str) and (normalized := item.strip())
        )

    # Backwards compatibility for checkpoints created before stable message IDs.
    raw_indexes = value.get("replaces_message_indexes")
    if not isinstance(raw_indexes, list):
        return ()
    restored: list[str] = []
    for index in raw_indexes:
        if not isinstance(index, int) or index < 0 or index >= len(messages):
            continue
        message_id = getattr(messages[index], "id", None)
        if message_id is not None:
            restored.append(str(message_id))
    return tuple(restored)


def build_strategy_context_from_capabilities(
    *,
    strategy: ExecutionStrategy[Any],
    capabilities: ExecutionCapabilities,
    messages: list[Any],
    initial_phase: str | None = None,
    final_model: Any | None = None,
    final_model_factory: Any | None = None,
    structured_repair_model_factory: Any | None = None,
    final_json_instruction: str | None = None,
    tool_definitions: list[dict[str, Any]] | None = None,
    bootstrap: dict[str, Any] | None = None,
    knowledge_strategy: KnowledgeStrategy | None = None,
    knowledge_runtime_config: dict[str, Any] | None = None,
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
    )
    if final_json_instruction:
        runtime_state.context_contributions.setdefault(
            "output.structured_contract",
            StrategyContextContribution(
                key="output.structured_contract",
                source_type="SYSTEM",
                content=final_json_instruction,
                metadata={
                    "selection_method": "execution_output_contract",
                },
            ),
        )

    if resume is not None:
        runtime_state.context_replacements = {
            key: _restored_replacement_ids(value, runtime_state.messages)
            for key, value in resume.context_contributions.items()
            if isinstance(value, dict)
        }

    base_messages = runtime_state.messages[: len(messages)]
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
        structured_repair_model_factory=structured_repair_model_factory,
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
            base_messages=base_messages,
        ),
        model=runtime_model,
        tools=runtime_tools,
        knowledge=RuntimeStrategyKnowledge(
            capability=capabilities.knowledge,
            runtime_state=runtime_state,
            strategy=knowledge_strategy,
            runtime_config=knowledge_runtime_config,
        ),
        context=RuntimeStrategyContextManager(
            capability=capabilities.context,
            runtime_state=runtime_state,
            base_messages=base_messages,
            model_capabilities=runtime_model,
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
        structured_repair_model_factory=prepared.structured_repair_model_factory,
        final_json_instruction=prepared.final_json_instruction,
        tool_definitions=prepared.tool_definitions,
        knowledge_strategy=prepared.knowledge_strategy,
        knowledge_runtime_config=prepared.knowledge_runtime_config,
    )
    built.context.model.set_fallback_model_factory(
        prepared.fallback_model_factory
    )
    built.context.output = RuntimeStrategyOutput.from_prepared(
        prepared=prepared,
        runtime_state=built.runtime_state,
        context_capability=capabilities.context,
        model_capabilities=built.context.model,
    )
    return BuiltStrategyExecution(
        context=built.context,
        runtime_state=built.runtime_state,
        prepared=prepared,
    )
