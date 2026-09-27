from __future__ import annotations

import json
from typing import Any

import uuid6
from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.interfaces.context_assembler import (
    ContextManagedContribution,
    ContextManagerCapabilities,
    ContextSummaryOutput,
    ContextSummaryRequest,
)
from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.strategy_sdk import (
    StrategyContextCompactionResult,
    StrategyContextContribution,
    StrategyContextInspection,
    StrategyContextTarget,
    StrategyInvocationContext,
    StrategyPhase,
    StrategyToolSelection,
    StrategyToolSelectionMode,
    strategy_phase_value,
)
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.capabilities.message_progression import (
    terminal_response_messages,
)
from modules.agent.infra.execution.capabilities.preparation import (
    _messages_with_bound_capability_authority,
    _messages_with_skill_usage,
    _messages_with_tool_grounding,
)
from modules.agent.infra.execution.strategy_runtime.model import RuntimeStrategyModel
from modules.agent.infra.execution.strategy_runtime.runtime_state import (
    StrategyRuntimeState,
)


_KNOWLEDGE_PREAMBLE = (
    "Use the following context when relevant. "
    "If the context is not enough, say you do not know.\n\n"
)


def _serialized_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def _materialize_contribution(
    contribution: StrategyContextContribution,
) -> SystemMessage:
    source_type = contribution.source_type.strip().upper()
    content = _serialized_content(contribution.content)
    if source_type == "KNOWLEDGE":
        content = f"{_KNOWLEDGE_PREAMBLE}<context>\n{content}\n</context>"

    metadata = {
        **dict(contribution.metadata),
        "source_type": source_type,
        "source_ref": contribution.key,
    }
    metadata.setdefault("selection_method", "strategy_context_contribution")
    return SystemMessage(
        content=content,
        additional_kwargs={"woobe_context": metadata},
    )


def materialize_context_contributions(
    messages: list[Any],
    contributions: tuple[StrategyContextContribution, ...],
) -> list[Any]:
    if not contributions:
        return list(messages)
    materialized = [_materialize_contribution(item) for item in contributions]
    split = 0
    while split < len(messages) and isinstance(messages[split], SystemMessage):
        split += 1
    return [*messages[:split], *materialized, *messages[split:]]


class _RuntimeContextManagerCapabilities(ContextManagerCapabilities):
    """Runtime mechanisms available to the configured Context Manager."""

    __slots__ = ("_model",)

    def __init__(self, model: RuntimeStrategyModel) -> None:
        self._model = model

    async def summarize(
        self,
        request: ContextSummaryRequest,
    ) -> ContextSummaryOutput:
        if request.target_units <= 0:
            raise ValueError("Context summary target_units must be positive")

        invocation = StrategyInvocationContext(
            invocation_id=uuid6.uuid7(),
            messages=(
                SystemMessage(content=request.instruction),
                HumanMessage(content=request.input_text),
            ),
            snapshot=None,
        )
        no_tools = StrategyToolSelection(StrategyToolSelectionMode.NONE)
        result = await self._model.invoke_auxiliary(
            context=invocation,
            tools=no_tools,
            phase=request.phase,
        )
        content = result.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Context Manager summarization returned no textual content")
        return ContextSummaryOutput(
            content=content,
            metadata={
                "mechanism": "model_summary",
                "target_units": request.target_units,
            },
        )


class RuntimeStrategyContextManager:
    """Execution-facing facade over the frozen programmable Context Manager."""

    __slots__ = (
        "_capability",
        "_runtime_state",
        "_base_messages",
        "_final_json_instruction",
        "_model",
    )

    def __init__(
        self,
        *,
        capability: ContextAssemblyCapability,
        runtime_state: StrategyRuntimeState,
        base_messages: list[Any] | None = None,
        final_json_instruction: str | None = None,
        model: RuntimeStrategyModel | None = None,
    ) -> None:
        self._capability = capability
        self._runtime_state = runtime_state
        self._base_messages = list(base_messages or runtime_state.messages)
        self._final_json_instruction = final_json_instruction
        self._model = model
        self._sync_execution_context()

    def _sync_execution_context(self) -> None:
        execution_context = current_execution.get()
        if execution_context is not None:
            execution_context.strategy_context_contributions = dict(
                self._runtime_state.context_contributions
            )

    def has(self, key: str) -> bool:
        return key in self._runtime_state.context_contributions

    def set(self, contribution: StrategyContextContribution) -> None:
        key = contribution.key.strip()
        if not key:
            raise ValueError("Context contribution key must not be empty")
        self._runtime_state.context_contributions[key] = contribution
        self._runtime_state.context_replacements.pop(key, None)
        self._sync_execution_context()

    def remove(self, key: str) -> None:
        self._runtime_state.context_contributions.pop(key, None)
        self._runtime_state.context_replacements.pop(key, None)
        self._sync_execution_context()

    def _contributions(self) -> tuple[StrategyContextContribution, ...]:
        return tuple(
            contribution
            for contribution in self._runtime_state.context_contributions.values()
            if isinstance(contribution, StrategyContextContribution)
        )

    def _managed_contributions(self) -> tuple[ContextManagedContribution, ...]:
        return tuple(
            ContextManagedContribution(
                key=item.key,
                source_type=item.source_type,
                content=item.content,
                metadata=dict(item.metadata),
                replaces_message_indexes=self._runtime_state.context_replacements.get(
                    item.key,
                    (),
                ),
            )
            for item in self._contributions()
        )

    def _apply_replacements(self, messages: list[Any]) -> list[Any]:
        replaced = {
            index
            for indexes in self._runtime_state.context_replacements.values()
            for index in indexes
        }
        if not replaced:
            return list(messages)
        return [
            message
            for index, message in enumerate(messages)
            if index not in replaced
        ]

    def inspect(self) -> StrategyContextInspection:
        result = self._capability.inspect(
            messages=list(self._runtime_state.messages),
            contributions=self._managed_contributions(),
        )
        return StrategyContextInspection(
            message_count=result.message_count,
            contribution_count=result.contribution_count,
            estimated_input_units=result.estimated_input_units,
            usable_input_units=result.usable_input_units,
            utilization=result.utilization,
            pressure=result.pressure,
        )

    async def compact(
        self,
        *,
        phase: StrategyPhase | None = None,
    ) -> StrategyContextCompactionResult:
        if self._model is None:
            raise RuntimeError("Context Manager Model capabilities are not bound")

        result = await self._capability.compact(
            messages=list(self._runtime_state.messages),
            contributions=self._managed_contributions(),
            phase=strategy_phase_value(phase or "context_compaction"),
            capabilities=_RuntimeContextManagerCapabilities(self._model),
        )
        for key in result.remove_keys:
            self._runtime_state.context_contributions.pop(key, None)
            self._runtime_state.context_replacements.pop(key, None)

        upserted: list[str] = []
        for item in result.upserts:
            contribution = StrategyContextContribution(
                key=item.key,
                source_type=item.source_type,
                content=item.content,
                metadata=dict(item.metadata),
            )
            self._runtime_state.context_contributions[item.key] = contribution
            self._runtime_state.context_replacements[item.key] = (
                item.replaces_message_indexes
            )
            upserted.append(item.key)

        if result.changed or result.remove_keys or result.upserts:
            self._sync_execution_context()

        return StrategyContextCompactionResult(
            changed=result.changed,
            upserted_keys=tuple(upserted),
            removed_keys=tuple(result.remove_keys),
            metadata=dict(result.metadata),
        )

    def _active_tool_definitions(
        self,
        tools: StrategyToolSelection | None,
    ) -> tuple[dict[str, Any], ...]:
        mode = (
            tools.mode.value
            if tools is not None
            else StrategyToolSelectionMode.ALL.value
        )
        active = self._capability.active_tool_definitions(mode)
        return tuple(active or ())

    @staticmethod
    def _tool_name(definition: dict[str, Any]) -> str | None:
        function = definition.get("function")
        if isinstance(function, dict):
            name = function.get("name")
            if isinstance(name, str) and name:
                return name
        name = definition.get("name")
        return name if isinstance(name, str) and name else None

    async def _assemble_messages(
        self,
        *,
        messages: list[Any],
        phase: StrategyPhase,
        tools: StrategyToolSelection | None,
        target: StrategyContextTarget = StrategyContextTarget.PRIMARY,
        include_contributions: bool = True,
        include_skill_context: bool = True,
        apply_replacements: bool = True,
    ) -> StrategyInvocationContext:
        capability = self._capability
        if target is StrategyContextTarget.FALLBACK:
            if self._model is None or not self._model.fallback_available:
                raise RuntimeError("Fallback Context requested without a bound fallback Model")
            if (
                tools is not None
                and tools.mode is not StrategyToolSelectionMode.NONE
            ):
                raise ValueError("Fallback Context currently requires tools=ctx.tools.none()")
            provider, model_name, pricing_snapshot = (
                self._model.fallback_context_binding()
            )
            capability = ContextAssemblyCapability(
                assembler=self._capability.assembler,
                provider=provider,
                model_name=model_name,
                pricing_snapshot=pricing_snapshot,
                tool_definitions=(),
            )

        active_definitions = (
            ()
            if target is StrategyContextTarget.FALLBACK
            else self._active_tool_definitions(tools)
        )
        active_names = tuple(
            name
            for definition in active_definitions
            if (name := self._tool_name(definition)) is not None
        )
        base_messages = (
            self._apply_replacements(messages)
            if apply_replacements
            else list(messages)
        )
        invocation_messages = _messages_with_bound_capability_authority(
            base_messages,
            has_tools=bool(active_definitions),
            has_skills=any(name.startswith("skills_") for name in active_names),
        )
        invocation_messages = _messages_with_skill_usage(
            invocation_messages,
            has_skills=any(name.startswith("skills_") for name in active_names),
        )
        invocation_messages = _messages_with_tool_grounding(
            invocation_messages,
            has_tools=bool(active_definitions),
        )
        materialized = (
            materialize_context_contributions(
                invocation_messages,
                self._contributions(),
            )
            if include_contributions
            else list(invocation_messages)
        )
        next_call_index = self._runtime_state.call_index + 1
        execution_context = current_execution.get()
        previous_skill_context = (
            execution_context.skill_context
            if execution_context is not None
            else None
        )
        if execution_context is not None and not include_skill_context:
            execution_context.skill_context = None
        try:
            result = capability.assemble(
                messages=materialized,
                phase=strategy_phase_value(phase),
                tool_selection_mode=(
                    tools.mode.value
                    if tools is not None
                    else StrategyToolSelectionMode.ALL.value
                ),
                call_index=next_call_index,
            )
        except InstrumentedExecutionError as exc:
            self._runtime_state.call_index = next_call_index
            self._runtime_state.absorb_model_error(exc)
            execution = self._runtime_state.execution
            raise InstrumentedExecutionError(
                str(exc),
                llm_calls=list(execution.llm_calls),
                tool_calls=list(execution.tool_calls),
                knowledge_calls=list(execution.knowledge_calls),
                sources=list(execution.sources),
                timeline=list(execution.timeline),
                tool_wall_latency_ms=execution.tool_wall_latency_ms,
                tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
                failure_context=execution.failure_context,
            ) from exc
        finally:
            if execution_context is not None and not include_skill_context:
                execution_context.skill_context = previous_skill_context

        return StrategyInvocationContext(
            invocation_id=result.invocation_id,
            messages=result.messages,
            snapshot=result.snapshot,
        )

    async def assemble(
        self,
        *,
        tools: StrategyToolSelection,
        phase: StrategyPhase | None = None,
        target: StrategyContextTarget = StrategyContextTarget.PRIMARY,
    ) -> StrategyInvocationContext:
        return await self._assemble_messages(
            messages=list(self._runtime_state.messages),
            phase=phase or "response_generation",
            tools=tools,
            target=target,
        )

    async def assemble_final(
        self,
        *,
        reason: str,
        phase: StrategyPhase,
        tools: StrategyToolSelection,
        target: StrategyContextTarget = StrategyContextTarget.PRIMARY,
    ) -> StrategyInvocationContext:
        base_messages = self._apply_replacements(self._base_messages)
        messages = terminal_response_messages(
            base_messages,
            self._final_json_instruction,
            self._runtime_state.execution.tool_calls,
            reason,
        )
        return await self._assemble_messages(
            messages=messages,
            phase=phase,
            tools=tools,
            target=target,
            apply_replacements=False,
        )
