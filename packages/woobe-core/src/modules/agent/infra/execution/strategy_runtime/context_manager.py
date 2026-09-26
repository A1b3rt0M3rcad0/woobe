from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.context_assembly import estimate_input_units
from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.strategy_sdk import (
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
        "selection_method": "strategy_context_contribution",
    }
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


class RuntimeStrategyContextManager:
    """Strategy-facing Context facade with runtime-owned contribution storage."""

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

    def inspect(self) -> StrategyContextInspection:
        execution_context = current_execution.get()
        policy = ContextPolicyV1.model_validate(
            (
                execution_context.context_policy
                if execution_context is not None
                else None
            )
            or {}
        )
        estimated = sum(
            estimate_input_units(_serialized_content(getattr(message, "content", "")))
            for message in self._runtime_state.messages
        )
        estimated += sum(
            estimate_input_units(_serialized_content(item.content))
            for item in self._contributions()
        )

        capacity = (
            execution_context.model_capacity_units
            if execution_context is not None
            else None
        )
        reserved = (
            execution_context.reserved_output_units
            if execution_context is not None
            else None
        )
        model_usable = (
            max(
                0,
                capacity
                - int(reserved or 0)
                - int(policy.budget.runtime_reserve_units or 0),
            )
            if isinstance(capacity, int) and capacity > 0
            else None
        )
        configured = policy.budget.max_input_units
        if model_usable is not None and configured is not None:
            usable = min(model_usable, configured)
        else:
            usable = model_usable if model_usable is not None else configured

        utilization = (
            estimated / usable
            if isinstance(usable, int) and usable > 0
            else None
        )
        if utilization is None:
            pressure = "UNKNOWN"
        elif utilization >= policy.pressure.critical_at:
            pressure = "CRITICAL"
        elif utilization >= policy.pressure.high_at:
            pressure = "HIGH"
        elif utilization >= policy.pressure.moderate_at:
            pressure = "MODERATE"
        else:
            pressure = "LOW"

        return StrategyContextInspection(
            message_count=len(self._runtime_state.messages),
            contribution_count=len(self._contributions()),
            estimated_input_units=estimated,
            usable_input_units=usable,
            utilization=utilization,
            pressure=pressure,
        )

    def has(self, key: str) -> bool:
        return key in self._runtime_state.context_contributions

    def set(self, contribution: StrategyContextContribution) -> None:
        key = contribution.key.strip()
        if not key:
            raise ValueError("Context contribution key must not be empty")
        self._runtime_state.context_contributions[key] = contribution
        self._sync_execution_context()

    def remove(self, key: str) -> None:
        self._runtime_state.context_contributions.pop(key, None)
        self._sync_execution_context()

    def _contributions(self) -> tuple[StrategyContextContribution, ...]:
        return tuple(
            contribution
            for contribution in self._runtime_state.context_contributions.values()
            if isinstance(contribution, StrategyContextContribution)
        )

    def _selected_tool_definitions(
        self,
        tools: StrategyToolSelection | None,
    ) -> tuple[dict[str, Any], ...]:
        mode = (
            tools.mode.value
            if tools is not None
            else StrategyToolSelectionMode.ALL.value
        )
        selected = self._capability.selected_tool_definitions(
            mode,
            tools.names if tools is not None else (),
        )
        return tuple(selected or ())

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

        selected_definitions = (
            ()
            if target is StrategyContextTarget.FALLBACK
            else self._selected_tool_definitions(tools)
        )
        selected_names = tuple(
            name
            for definition in selected_definitions
            if (name := self._tool_name(definition)) is not None
        )
        invocation_messages = _messages_with_bound_capability_authority(
            messages,
            has_tools=bool(selected_definitions),
            has_skills=any(name.startswith("skills_") for name in selected_names),
        )
        invocation_messages = _messages_with_skill_usage(
            invocation_messages,
            has_skills=any(name.startswith("skills_") for name in selected_names),
        )
        invocation_messages = _messages_with_tool_grounding(
            invocation_messages,
            has_tools=bool(selected_definitions),
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
                tool_selection_names=tools.names if tools is not None else (),
                call_index=next_call_index,
            )
        except InstrumentedExecutionError as exc:
            # Context assembly is part of the upcoming Model Invocation boundary.
            # A budget failure consumes that invocation index even though the
            # Provider was never called.
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

    async def summarize(
        self,
        *,
        key: str = "session.summary",
        scope: str = "session",
        target_units: int = 2000,
        phase: StrategyPhase | None = None,
    ) -> StrategyContextContribution:
        if scope != "session":
            raise ValueError("Context summarize currently supports only session scope")
        if target_units <= 0:
            raise ValueError("Context summarize target_units must be positive")
        if self._model is None:
            raise RuntimeError("Context summarization Model is not bound")

        source_lines: list[str] = []
        for message in self._runtime_state.messages:
            role = type(message).__name__
            content = _serialized_content(getattr(message, "content", ""))
            tool_calls = getattr(message, "tool_calls", None) or ()
            tool_call_id = getattr(message, "tool_call_id", None)
            suffix = ""
            if tool_calls:
                suffix += f" tool_calls={_serialized_content(tool_calls)}"
            if tool_call_id:
                suffix += f" tool_call_id={tool_call_id}"
            source_lines.append(f"[{role}]{suffix}\n{content}")

        summary_phase = phase or "context_summarization"
        summary_messages = [
            SystemMessage(
                content=(
                    "Summarize the supplied Session context for later Agent reasoning. "
                    "Preserve concrete facts, decisions, constraints, unresolved work, "
                    "important Tool results and identifiers. Do not invent information. "
                    f"Aim for at most approximately {target_units} input units."
                )
            ),
            HumanMessage(content="\n\n".join(source_lines)),
        ]
        no_tools = StrategyToolSelection(StrategyToolSelectionMode.NONE)
        invocation = await self._assemble_messages(
            messages=summary_messages,
            phase=summary_phase,
            tools=no_tools,
            target=StrategyContextTarget.PRIMARY,
            include_contributions=False,
            include_skill_context=False,
        )
        result = await self._model.invoke_auxiliary(
            context=invocation,
            tools=no_tools,
            phase=summary_phase,
        )
        content = result.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Context summarization returned no textual content")
        return StrategyContextContribution(
            key=key,
            source_type="SESSION",
            content=content,
            metadata={
                "selection_method": "strategy_context_summary",
                "scope": scope,
                "target_units": target_units,
                "source_message_count": len(self._runtime_state.messages),
            },
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
        messages = terminal_response_messages(
            self._base_messages,
            self._final_json_instruction,
            self._runtime_state.execution.tool_calls,
            reason,
        )
        return await self._assemble_messages(
            messages=messages,
            phase=phase,
            tools=tools,
            target=target,
        )
