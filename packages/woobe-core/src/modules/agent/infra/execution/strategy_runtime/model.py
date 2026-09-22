from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage

from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.strategy_sdk import (
    StrategyModelResult,
    StrategyPhase,
    strategy_phase_value,
)
from modules.agent.infra.execution.capabilities.message_progression import (
    terminal_response_messages,
)
from modules.agent.infra.execution.capabilities.model_invocation import (
    ModelInvocationCapability,
)
from modules.agent.infra.execution.strategy_runtime.runtime_state import StrategyRuntimeState


def _messages_with_execution_directive(
    messages: list[Any],
    *,
    phase: StrategyPhase,
    directive: str | None,
) -> list[Any]:
    """Materialize one Strategy directive without mutating runtime-owned messages."""

    if directive is None:
        return messages
    normalized = directive.strip()
    if not normalized:
        return messages

    phase_value = strategy_phase_value(phase)
    message = SystemMessage(
        content=(
            "<execution_directive>\n"
            f"phase: {phase_value}\n"
            "scope: current model invocation only\n\n"
            "Follow this directive within the Agent's existing objective, "
            "behavioral constraints, and Skills. It does not replace or mutate "
            "them.\n\n"
            f"{normalized}\n"
            "</execution_directive>"
        ),
        additional_kwargs={
            "woobe_context": {
                "source_type": "SYSTEM",
                "source_ref": f"execution_directive:{phase_value}",
                "kind": "execution_directive",
                "phase": phase_value,
                "selection_method": "strategy_directive",
                "trust": "system-controlled",
                "sensitivity": "internal",
            }
        },
    )

    # Keep provider-facing System messages grouped at the beginning while making
    # the directive the last system-level instruction before conversational input.
    materialized = list(messages)
    insertion = 0
    while (
        insertion < len(materialized)
        and materialized[insertion].__class__.__name__ == "SystemMessage"
    ):
        insertion += 1
    materialized.insert(insertion, message)
    return materialized


class RuntimeStrategyModel:
    """Strategy-facing Model facade with runtime instrumentation and conversation ownership."""

    __slots__ = (
        "_capability",
        "_runtime_state",
        "_base_messages",
        "_initial_phase",
        "_final_model",
        "_final_model_factory",
        "_final_json_instruction",
    )

    def __init__(
        self,
        *,
        capability: ModelInvocationCapability,
        runtime_state: StrategyRuntimeState,
        base_messages: list[Any],
        initial_phase: str,
        final_model: Any | None,
        final_model_factory: Any | None,
        final_json_instruction: str | None,
    ) -> None:
        self._capability = capability
        self._runtime_state = runtime_state
        self._base_messages = list(base_messages)
        self._initial_phase = initial_phase
        self._final_model = final_model
        self._final_model_factory = final_model_factory
        self._final_json_instruction = final_json_instruction

    async def _invoke(
        self,
        *,
        capability: ModelInvocationCapability,
        messages: list[Any],
        phase: StrategyPhase,
        directive: str | None = None,
        public_output: bool | None = None,
    ) -> StrategyModelResult:
        call_index = self._runtime_state.next_call_index()
        invocation_messages = _messages_with_execution_directive(
            messages,
            phase=phase,
            directive=directive,
        )
        try:
            result, call = await capability.invoke(
                messages=invocation_messages,
                phase=strategy_phase_value(phase),
                call_index=call_index,
                public_output=public_output,
            )
        except InstrumentedExecutionError as exc:
            self._runtime_state.absorb_model_error(exc)
            raise

        self._runtime_state.record_model_call(call)
        self._runtime_state.record_model_message(result)
        return StrategyModelResult(message=result)

    async def invoke(
        self,
        *,
        phase: StrategyPhase | None = None,
        directive: str | None = None,
        public_output: bool | None = None,
    ) -> StrategyModelResult:
        return await self._invoke(
            capability=self._capability,
            messages=self._runtime_state.messages,
            phase=phase or self._initial_phase,
            directive=directive,
            public_output=public_output,
        )

    async def finalize(
        self,
        *,
        reason: str,
        phase: StrategyPhase,
        directive: str | None = None,
        public_output: bool | None = None,
    ) -> StrategyModelResult:
        terminal_model = self._final_model
        if terminal_model is None and self._final_model_factory is not None:
            terminal_model = self._final_model_factory()
        if terminal_model is None:
            execution = self._runtime_state.execution
            raise InstrumentedExecutionError(
                reason,
                llm_calls=execution.llm_calls,
                tool_calls=execution.tool_calls,
                timeline=execution.timeline,
                tool_wall_latency_ms=execution.tool_wall_latency_ms,
                tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
                failure_context={
                    **(execution.failure_context or {}),
                    "partial_result_available": bool(execution.tool_calls),
                },
            )

        terminal_capability = self._capability.for_model(terminal_model)
        try:
            return await self._invoke(
                capability=terminal_capability,
                messages=terminal_response_messages(
                    self._base_messages,
                    self._final_json_instruction,
                    self._runtime_state.execution.tool_calls,
                    reason,
                ),
                phase=phase,
                directive=directive,
                public_output=public_output,
            )
        except InstrumentedExecutionError as exc:
            execution = self._runtime_state.execution
            raise InstrumentedExecutionError(
                str(exc),
                llm_calls=execution.llm_calls,
                tool_calls=execution.tool_calls,
                timeline=execution.timeline,
                tool_wall_latency_ms=execution.tool_wall_latency_ms,
                tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
                failure_context=execution.failure_context,
            ) from exc
