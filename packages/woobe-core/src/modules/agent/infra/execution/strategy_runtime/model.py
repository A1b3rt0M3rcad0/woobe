from __future__ import annotations

from typing import Any

from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.strategy_sdk import (
    StrategyModelResult,
    StrategyPhase,
    strategy_phase_value,
)
from modules.agent.infra.execution.capabilities.message_progression import terminal_response_messages
from modules.agent.infra.execution.capabilities.model_invocation import ModelInvocationCapability
from modules.agent.infra.execution.strategy_runtime.runtime_state import StrategyRuntimeState


class RuntimeStrategyModel:
    """Strategy-facing Model facade with runtime instrumentation attached."""

    __slots__ = (
        "_capability",
        "_runtime_state",
        "_base_messages",
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
        final_model: Any | None,
        final_model_factory: Any | None,
        final_json_instruction: str | None,
    ) -> None:
        self._capability = capability
        self._runtime_state = runtime_state
        self._base_messages = list(base_messages)
        self._final_model = final_model
        self._final_model_factory = final_model_factory
        self._final_json_instruction = final_json_instruction

    async def _invoke(
        self,
        *,
        capability: ModelInvocationCapability,
        messages: list[Any],
        phase: StrategyPhase,
    ) -> StrategyModelResult:
        call_index = self._runtime_state.next_call_index()
        try:
            result, call = await capability.invoke(
                messages=messages,
                phase=strategy_phase_value(phase),
                call_index=call_index,
            )
        except InstrumentedExecutionError as exc:
            self._runtime_state.absorb_model_error(exc)
            raise
        self._runtime_state.record_model_call(call)
        return StrategyModelResult(message=result)

    async def invoke(
        self,
        *,
        messages: list[Any],
        phase: StrategyPhase,
    ) -> StrategyModelResult:
        return await self._invoke(
            capability=self._capability,
            messages=messages,
            phase=phase,
        )

    async def finalize(
        self,
        *,
        messages: list[Any],
        reason: str,
        phase: StrategyPhase,
    ) -> StrategyModelResult:
        del messages
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
