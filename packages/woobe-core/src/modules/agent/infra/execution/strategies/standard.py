from __future__ import annotations

from dataclasses import dataclass

from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategy
from modules.agent.application.strategy_sdk import (
    Completed,
    ExecutionCheckpointBoundary,
    ExecutionPhase,
    ExecutionPolicy,
    ExecutionState,
    ExecutionStopReason,
    StrategyContext,
    StrategyOutcome,
    Suspended,
    strategy_phase_with_iteration,
)


DEFAULT_MAX_TOOL_ROUNDS = 5
DEFAULT_MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS = 2
MAX_TOOL_ROUNDS = DEFAULT_MAX_TOOL_ROUNDS
MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS = (
    DEFAULT_MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS
)


class StandardPhase(ExecutionPhase):
    RESPONSE_GENERATION = "response_generation"
    CAPABILITY_RESPONSE_GENERATION = "capability_response_generation"
    TOOL_FOLLOWUP = "tool_followup"
    FINAL_RESPONSE_GENERATION = "final_response_generation"


class StandardStopReason(ExecutionStopReason):
    REPEATED_SEMANTIC_FAILURES = "repeated semantic capability failures"
    CAPABILITY_ROUND_LIMIT = "capability round limit reached"
    PROVIDER_REJECTED_FOLLOWUP = (
        "the capability follow-up request was rejected by the provider"
    )


class StandardExecutionState(ExecutionState):
    phase: str | None = None
    tool_round: int = 0
    consecutive_failures: int = 0
    stop_reason: StandardStopReason | None = None


@dataclass(frozen=True, slots=True)
class StandardExecutionPolicy(ExecutionPolicy[StandardExecutionState]):
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS
    max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS

    def __post_init__(self) -> None:
        if self.max_tool_rounds <= 0:
            raise ValueError("max_tool_rounds must be positive")
        if self.max_consecutive_failures <= 0:
            raise ValueError("max_consecutive_failures must be positive")

    def stop_reason(
        self,
        state: StandardExecutionState,
    ) -> StandardStopReason | None:
        if state.consecutive_failures >= self.max_consecutive_failures:
            return StandardStopReason.REPEATED_SEMANTIC_FAILURES
        if state.tool_round >= self.max_tool_rounds:
            return StandardStopReason.CAPABILITY_ROUND_LIMIT
        return None


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

        if state.phase == StandardPhase.FINAL_RESPONSE_GENERATION.value:
            result = await ctx.model.finalize(
                reason=(
                    state.stop_reason.value
                    if state.stop_reason is not None
                    else "Capability execution could not complete"
                ),
                phase=StandardPhase.FINAL_RESPONSE_GENERATION,
            )
            return Completed(result)

        tools = ctx.tools.all()
        invocation = await ctx.context.assemble(
            phase=state.phase,
            tools=tools,
        )
        result = await ctx.model.invoke(
            context=invocation,
            phase=state.phase,
        )

        while result.has_tool_calls and state.tool_round < self.policy.max_tool_rounds:
            tool_batch = await ctx.tools.execute_many(result.tool_calls)
            state.tool_round += 1
            state.consecutive_failures = (
                state.consecutive_failures + 1
                if tool_batch.has_failures
                else 0
            )

            if tool_batch.requires_suspension:
                if tool_batch.suspension_reason is None:
                    raise RuntimeError(
                        "Suspending Tool batch is missing a suspension reason"
                    )
                await ctx.checkpoint(ExecutionCheckpointBoundary.TOOL)
                return Suspended(
                    reason=tool_batch.suspension_reason,
                    operation_ref=tool_batch.operation_ref,
                )

            state.stop_reason = self.policy.stop_reason(state)
            state.phase = (
                StandardPhase.FINAL_RESPONSE_GENERATION.value
                if state.stop_reason is not None
                else strategy_phase_with_iteration(
                    StandardPhase.TOOL_FOLLOWUP,
                    state.tool_round,
                )
            )
            await ctx.checkpoint(ExecutionCheckpointBoundary.TOOL)

            if state.stop_reason is not None:
                break

            try:
                invocation = await ctx.context.assemble(
                    phase=state.phase,
                    tools=tools,
                )
                result = await ctx.model.invoke(
                    context=invocation,
                    phase=state.phase,
                )
            except InstrumentedExecutionError:
                state.stop_reason = StandardStopReason.PROVIDER_REJECTED_FOLLOWUP
                state.phase = StandardPhase.FINAL_RESPONSE_GENERATION.value
                break

        if state.stop_reason is not None and result.has_tool_calls:
            result = await ctx.model.finalize(
                reason=state.stop_reason.value,
                phase=StandardPhase.FINAL_RESPONSE_GENERATION,
            )

        return Completed(result)


__all__ = [
    "MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS",
    "MAX_TOOL_ROUNDS",
    "StandardExecutionPolicy",
    "StandardExecutionState",
    "StandardExecutionStrategy",
    "StandardPhase",
    "StandardStopReason",
]
