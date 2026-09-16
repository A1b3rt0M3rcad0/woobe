from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategy
from modules.agent.application.strategy_sdk import (
    ExecutionCheckpointBoundary,
    ExecutionPolicy,
    ExecutionState,
    StrategyContext,
    StrategyDecision,
    StrategyDecisionType,
    StrategyInitialization,
    StrategyOutcome,
    StrategyResumeSnapshot,
    StrategyToolBatch,
    stop_reason_value,
    strategy_phase_with_iteration,
)


DEFAULT_MAX_TOOL_ROUNDS = 5
DEFAULT_MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS = 2
MAX_TOOL_ROUNDS = DEFAULT_MAX_TOOL_ROUNDS
MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS = (
    DEFAULT_MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS
)


class StandardPhase(StrEnum):
    RESPONSE_GENERATION = "response_generation"
    CAPABILITY_RESPONSE_GENERATION = "capability_response_generation"
    TOOL_FOLLOWUP = "tool_followup"
    FINAL_RESPONSE_GENERATION = "final_response_generation"


class StandardStopReason(StrEnum):
    REPEATED_SEMANTIC_FAILURES = "repeated semantic capability failures"
    CAPABILITY_ROUND_LIMIT = "capability round limit reached"
    PROVIDER_REJECTED_FOLLOWUP = (
        "the capability follow-up request was rejected by the provider"
    )


def _is_standard_model_phase(value: str) -> bool:
    if value in {
        StandardPhase.RESPONSE_GENERATION.value,
        StandardPhase.CAPABILITY_RESPONSE_GENERATION.value,
        StandardPhase.FINAL_RESPONSE_GENERATION.value,
    }:
        return True
    return value.startswith(f"{StandardPhase.TOOL_FOLLOWUP.value}_")


@dataclass(slots=True)
class StandardExecutionState(ExecutionState):
    messages: list[Any]
    next_phase: str
    tool_round: int = 0
    consecutive_failures: int = 0
    stopped_reason: str | None = None
    initial_tool_call: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        initialization: StrategyInitialization,
        resume: StrategyResumeSnapshot | None,
    ) -> "StandardExecutionState":
        initial_tool_call = initialization.bootstrap.get("initial_tool_call")
        if initial_tool_call is not None and not isinstance(initial_tool_call, dict):
            raise ValueError("Standard initial_tool_call must be a mapping")

        if resume is None:
            if not _is_standard_model_phase(initialization.initial_phase):
                raise ValueError(
                    f"Unsupported Standard initial phase: {initialization.initial_phase}"
                )
            return cls(
                messages=list(initialization.messages),
                next_phase=initialization.initial_phase,
                initial_tool_call=initial_tool_call,
            )

        cursor = dict(resume.cursor)
        next_phase = cursor.get("next_phase")
        if not isinstance(next_phase, str) or not _is_standard_model_phase(next_phase):
            raise InstrumentedExecutionError(
                "Agent recovery checkpoint is missing next execution phase",
                llm_calls=resume.execution.llm_calls,
                tool_calls=resume.execution.tool_calls,
                timeline=resume.execution.timeline,
            )
        try:
            tool_round = max(0, int(cursor.get("round_index") or 0))
            consecutive_failures = max(
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
        stopped_reason = (
            str(cursor["stopped_reason"])
            if cursor.get("stopped_reason")
            else None
        )
        if next_phase == StandardPhase.FINAL_RESPONSE_GENERATION.value and not stopped_reason:
            raise InstrumentedExecutionError(
                "Agent recovery checkpoint is missing terminal stop reason",
                llm_calls=resume.execution.llm_calls,
                tool_calls=resume.execution.tool_calls,
                timeline=resume.execution.timeline,
            )
        return cls(
            messages=[*initialization.messages, *resume.capability_messages],
            next_phase=next_phase,
            tool_round=tool_round,
            consecutive_failures=consecutive_failures,
            stopped_reason=stopped_reason,
            initial_tool_call=None,
        )

    def record_model_result(self, result) -> None:
        if result.has_tool_calls:
            self.messages.append(result.message)

    def record_tool_batch(
        self,
        batch: StrategyToolBatch,
        *,
        count_round: bool = True,
    ) -> None:
        self.messages.extend(batch.messages)
        if count_round:
            self.tool_round += 1
            self.consecutive_failures = (
                self.consecutive_failures + 1 if batch.has_failures else 0
            )

    def checkpoint_cursor(self) -> dict[str, Any]:
        return {
            "next_phase": self.next_phase,
            "round_index": self.tool_round,
            "consecutive_failure_rounds": self.consecutive_failures,
            "stopped_reason": self.stopped_reason,
        }

    def checkpoint_messages(self) -> list[Any]:
        return self.messages


@dataclass(frozen=True, slots=True)
class StandardExecutionPolicy(ExecutionPolicy[StandardExecutionState]):
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS
    max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS

    def __post_init__(self) -> None:
        if self.max_tool_rounds <= 0:
            raise ValueError("max_tool_rounds must be positive")
        if self.max_consecutive_failures <= 0:
            raise ValueError("max_consecutive_failures must be positive")

    def evaluate(self, state: StandardExecutionState) -> StrategyDecision:
        if state.consecutive_failures >= self.max_consecutive_failures:
            return StrategyDecision(
                type=StrategyDecisionType.FINALIZE,
                reason=StandardStopReason.REPEATED_SEMANTIC_FAILURES,
            )
        if state.tool_round >= self.max_tool_rounds:
            return StrategyDecision(
                type=StrategyDecisionType.FINALIZE,
                reason=StandardStopReason.CAPABILITY_ROUND_LIMIT,
            )
        return StrategyDecision(type=StrategyDecisionType.CONTINUE)


class StandardExecutionStrategy(ExecutionStrategy[StandardExecutionState]):
    """General-purpose model/Tool loop expressed only through shared Strategy primitives."""

    name = "standard"
    state_type = StandardExecutionState

    def __init__(self, policy: StandardExecutionPolicy | None = None) -> None:
        self.policy = policy or StandardExecutionPolicy()

    async def execute(
        self,
        ctx: StrategyContext[StandardExecutionState],
    ) -> StrategyOutcome:
        state = ctx.state

        if state.initial_tool_call is not None:
            tool_batch = await ctx.tools.execute_many([state.initial_tool_call])
            state.record_tool_batch(tool_batch, count_round=False)
            state.initial_tool_call = None
            await ctx.checkpoint(ExecutionCheckpointBoundary.PREFLIGHT)

        if state.next_phase == StandardPhase.FINAL_RESPONSE_GENERATION.value:
            result = await ctx.model.finalize(
                messages=state.messages,
                reason=state.stopped_reason or "Capability execution could not complete",
                phase=StandardPhase.FINAL_RESPONSE_GENERATION,
            )
            state.record_model_result(result)
            return ctx.complete(result)

        result = await ctx.model.invoke(
            messages=state.messages,
            phase=state.next_phase,
        )
        state.record_model_result(result)

        while result.has_tool_calls and state.tool_round < self.policy.max_tool_rounds:
            tool_batch = await ctx.tools.execute_many(result.tool_calls)
            state.record_tool_batch(tool_batch)

            if tool_batch.requires_suspension:
                if tool_batch.suspension_reason is None:
                    raise RuntimeError(
                        "Suspending Tool batch is missing a suspension reason"
                    )
                await ctx.checkpoint(ExecutionCheckpointBoundary.TOOL)
                return ctx.suspend(
                    reason=tool_batch.suspension_reason,
                    operation_ref=tool_batch.operation_ref,
                )

            decision = self.policy.evaluate(state)
            state.stopped_reason = (
                stop_reason_value(decision.reason)
                if decision.type is StrategyDecisionType.FINALIZE
                else None
            )
            state.next_phase = (
                StandardPhase.FINAL_RESPONSE_GENERATION.value
                if state.stopped_reason
                else strategy_phase_with_iteration(
                    StandardPhase.TOOL_FOLLOWUP,
                    state.tool_round,
                )
            )
            await ctx.checkpoint(ExecutionCheckpointBoundary.TOOL)

            if decision.type is StrategyDecisionType.FINALIZE:
                break

            try:
                result = await ctx.model.invoke(
                    messages=state.messages,
                    phase=state.next_phase,
                )
            except InstrumentedExecutionError:
                state.stopped_reason = StandardStopReason.PROVIDER_REJECTED_FOLLOWUP.value
                state.next_phase = StandardPhase.FINAL_RESPONSE_GENERATION.value
                break
            state.record_model_result(result)

        if state.stopped_reason and result.has_tool_calls:
            result = await ctx.model.finalize(
                messages=state.messages,
                reason=state.stopped_reason,
                phase=StandardPhase.FINAL_RESPONSE_GENERATION,
            )
            state.record_model_result(result)

        return ctx.complete(result)


__all__ = [
    "MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS",
    "MAX_TOOL_ROUNDS",
    "StandardExecutionPolicy",
    "StandardExecutionState",
    "StandardExecutionStrategy",
    "StandardPhase",
    "StandardStopReason",
]
