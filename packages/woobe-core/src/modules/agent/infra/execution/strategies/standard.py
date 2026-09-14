from __future__ import annotations

from typing import Any, Callable

from langchain_core.messages import AIMessage

from modules.agent.application.interfaces.execution import (
    InstrumentedExecution,
    InstrumentedExecutionError,
)
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.capabilities.bundle import (
    ExecutionCapabilities,
    build_execution_capabilities,
)
from modules.agent.infra.execution.capabilities.message_progression import (
    has_tool_calls,
    sanitize_base_messages,
    terminal_response_messages,
)
from modules.agent.infra.execution.capabilities.preparation import prepare_execution
from modules.agent.infra.execution.capabilities.result_finalization import (
    finalize_execution_result,
)
from modules.agent.infra.execution.capabilities.state import StrategyExecutionState

MAX_TOOL_ROUNDS = 5
MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS = 2


def _failure_context(
    context: dict[str, Any] | None,
    *,
    partial_result_available: bool,
) -> dict[str, Any]:
    return {
        **(context or {}),
        "partial_result_available": partial_result_available,
    }


async def _invoke_terminal_recovery(
    *,
    capabilities: ExecutionCapabilities,
    state: StrategyExecutionState,
    base_messages: list,
    stopped_reason: str,
    call_index: int,
    final_model: Any | None,
    final_model_factory: Callable[[], Any] | None,
    final_json_instruction: str | None,
) -> Any:
    terminal_model = final_model
    if terminal_model is None and final_model_factory is not None:
        terminal_model = final_model_factory()
    if terminal_model is None:
        execution = state.execution
        raise InstrumentedExecutionError(
            stopped_reason,
            llm_calls=execution.llm_calls,
            tool_calls=execution.tool_calls,
            timeline=execution.timeline,
            tool_wall_latency_ms=execution.tool_wall_latency_ms,
            tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
            failure_context=_failure_context(
                execution.failure_context,
                partial_result_available=bool(execution.tool_calls),
            ),
        )

    terminal_capability = capabilities.model.for_model(terminal_model)
    try:
        result, call = await terminal_capability.invoke(
            messages=terminal_response_messages(
                base_messages,
                final_json_instruction,
                state.execution.tool_calls,
                stopped_reason,
            ),
            phase="final_response_generation",
            call_index=call_index,
        )
    except InstrumentedExecutionError as exc:
        execution = state.execution
        raise InstrumentedExecutionError(
            str(exc),
            llm_calls=execution.llm_calls + exc.llm_calls,
            tool_calls=execution.tool_calls,
            timeline=execution.timeline + exc.timeline,
            tool_wall_latency_ms=execution.tool_wall_latency_ms,
            tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
            failure_context=_failure_context(
                exc.failure_context or execution.failure_context,
                partial_result_available=bool(execution.tool_calls),
            ),
        ) from exc

    state.record_model_result(result=result, call=call)
    return result


async def run_standard_strategy_loop(
    *,
    capabilities: ExecutionCapabilities,
    messages: list,
    initial_phase: str,
    final_json_instruction: str | None,
    final_model: Any | None = None,
    final_model_factory: Callable[[], Any] | None = None,
    initial_tool_call: dict[str, Any] | None = None,
) -> tuple[InstrumentedExecution, int]:
    """Execute the built-in Standard model/Tool algorithm using shared capabilities."""
    base_messages = sanitize_base_messages(messages)
    base_message_count = len(base_messages)
    resume = capabilities.recovery.load()

    if resume is not None:
        cursor = resume.cursor
        next_phase = cursor.get("next_phase")
        next_call_index = cursor.get("next_call_index")
        if not isinstance(next_phase, str) or not next_phase:
            raise InstrumentedExecutionError(
                "Agent recovery checkpoint is missing next execution phase",
                llm_calls=resume.execution.llm_calls,
                tool_calls=resume.execution.tool_calls,
                timeline=resume.execution.timeline,
            )
        try:
            call_index = int(next_call_index)
            round_index = max(0, int(cursor.get("round_index") or 0))
            consecutive_failure_rounds = max(
                0,
                int(cursor.get("consecutive_failure_rounds") or 0),
            )
        except (TypeError, ValueError) as exc:
            raise InstrumentedExecutionError(
                "Agent recovery checkpoint contains an invalid Standard cursor",
                llm_calls=resume.execution.llm_calls,
                tool_calls=resume.execution.tool_calls,
                timeline=resume.execution.timeline,
            ) from exc
        if call_index <= 0:
            raise InstrumentedExecutionError(
                "Agent recovery checkpoint contains an invalid next call index",
                llm_calls=resume.execution.llm_calls,
                tool_calls=resume.execution.tool_calls,
                timeline=resume.execution.timeline,
            )
        stopped_reason = (
            str(cursor["stopped_reason"])
            if cursor.get("stopped_reason")
            else None
        )
        state = StrategyExecutionState(
            messages=[*base_messages, *resume.capability_messages],
            execution=resume.execution,
            call_index=max(0, call_index - 1),
            iteration=round_index,
        )

        if next_phase == "final_response_generation":
            if not stopped_reason:
                raise InstrumentedExecutionError(
                    "Agent recovery checkpoint is missing terminal stop reason",
                    llm_calls=state.execution.llm_calls,
                    tool_calls=state.execution.tool_calls,
                    timeline=state.execution.timeline,
                )
            await _invoke_terminal_recovery(
                capabilities=capabilities,
                state=state,
                base_messages=base_messages,
                stopped_reason=stopped_reason,
                call_index=call_index,
                final_model=final_model,
                final_model_factory=final_model_factory,
                final_json_instruction=final_json_instruction,
            )
            return state.finish(), call_index

        result, call = await capabilities.model.invoke(
            messages=state.messages,
            phase=next_phase,
            call_index=call_index,
        )
        state.record_model_result(result=result, call=call)
    else:
        state = StrategyExecutionState(messages=list(base_messages))
        round_index = 0
        consecutive_failure_rounds = 0
        stopped_reason: str | None = None
        call_index = 1

        if initial_tool_call is not None:
            preflight = AIMessage(content="", tool_calls=[initial_tool_call])
            state.messages.append(preflight)
            batch = await capabilities.tools.execute_many([initial_tool_call])
            state.record_tool_batch(batch)
            await capabilities.recovery.checkpoint(
                phase="agent_preflight_boundary",
                messages=state.messages,
                base_message_count=base_message_count,
                execution=state.execution,
                cursor={
                    "next_phase": initial_phase,
                    "next_call_index": 1,
                    "round_index": 0,
                    "consecutive_failure_rounds": 0,
                    "stopped_reason": None,
                },
            )

        result, call = await capabilities.model.invoke(
            messages=state.messages,
            phase=initial_phase,
            call_index=call_index,
        )
        state.record_model_result(result=result, call=call)

    while has_tool_calls(result) and round_index < MAX_TOOL_ROUNDS:
        round_index += 1
        state.iteration = round_index
        state.messages.append(result)
        tool_calls = list(getattr(result, "tool_calls", None) or [])
        batch = await capabilities.tools.execute_many(tool_calls)
        state.record_tool_batch(batch)

        round_failed = any(info.success is False for info, _message, _payload in batch.results)
        consecutive_failure_rounds = (
            consecutive_failure_rounds + 1 if round_failed else 0
        )
        stopped_reason = None
        if consecutive_failure_rounds >= MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS:
            stopped_reason = "repeated semantic capability failures"
        elif round_index >= MAX_TOOL_ROUNDS:
            stopped_reason = "capability round limit reached"

        next_call_index = call_index + 1
        next_phase = (
            "final_response_generation"
            if stopped_reason
            else f"tool_followup_{round_index}"
        )
        await capabilities.recovery.checkpoint(
            phase="agent_tool_boundary",
            messages=state.messages,
            base_message_count=base_message_count,
            execution=state.execution,
            cursor={
                "next_phase": next_phase,
                "next_call_index": next_call_index,
                "round_index": round_index,
                "consecutive_failure_rounds": consecutive_failure_rounds,
                "stopped_reason": stopped_reason,
            },
        )
        if stopped_reason:
            break

        call_index = next_call_index
        try:
            result, call = await capabilities.model.invoke(
                messages=state.messages,
                phase=next_phase,
                call_index=call_index,
            )
        except InstrumentedExecutionError as exc:
            state.execution.llm_calls.extend(exc.llm_calls)
            state.execution.timeline.extend(exc.timeline)
            state.execution.failure_context = _failure_context(
                exc.failure_context,
                partial_result_available=bool(state.execution.tool_calls),
            )
            stopped_reason = (
                "the capability follow-up request was rejected by the provider"
            )
            break
        state.record_model_result(result=result, call=call)

    requires_terminal_recovery = bool(stopped_reason) and has_tool_calls(result)
    if requires_terminal_recovery:
        call_index += 1
        await _invoke_terminal_recovery(
            capabilities=capabilities,
            state=state,
            base_messages=base_messages,
            stopped_reason=stopped_reason or "Capability execution could not complete",
            call_index=call_index,
            final_model=final_model,
            final_model_factory=final_model_factory,
            final_json_instruction=final_json_instruction,
        )

    return state.finish(), call_index


class StandardExecutionStrategy:
    """Current Woobe Agent algorithm composed from reusable execution capabilities."""

    async def execute(self, request: ExecutionStrategyRequest) -> InstrumentedExecution:
        prepared = prepare_execution(request)
        capabilities = build_execution_capabilities(
            prepared=prepared,
            strategy_name="standard",
        )
        execution, call_index = await run_standard_strategy_loop(
            capabilities=capabilities,
            messages=prepared.messages,
            final_model=prepared.final_model,
            final_model_factory=prepared.final_model_factory,
            initial_phase=prepared.initial_phase,
            final_json_instruction=prepared.final_json_instruction,
        )
        return await finalize_execution_result(
            prepared=prepared,
            execution=execution,
            call_index=call_index,
        )
