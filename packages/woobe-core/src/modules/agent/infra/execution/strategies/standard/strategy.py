from __future__ import annotations

from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategy
from modules.agent.application.strategy_sdk import (
    StrategyContext,
    StrategyDecisionType,
    StrategyOutcome,
)
from modules.agent.infra.execution.strategies.standard.phases import (
    StandardCheckpointBoundary,
    StandardPhase,
    tool_followup_phase,
)
from modules.agent.infra.execution.strategies.standard.policy import (
    StandardExecutionPolicy,
    StandardStopReason,
)
from modules.agent.infra.execution.strategies.standard.state import (
    StandardExecutionState,
)


class StandardExecutionStrategy(ExecutionStrategy[StandardExecutionState]):
    """General-purpose model/Tool loop expressed only through the Strategy SDK."""

    def __init__(self, policy: StandardExecutionPolicy) -> None:
        self._policy = policy

    async def execute(
        self,
        ctx: StrategyContext[StandardExecutionState],
    ) -> StrategyOutcome:
        state = ctx.state

        if state.initial_tool_call is not None:
            tool_batch = await ctx.tools.execute_many([state.initial_tool_call])
            state.record_tool_batch(tool_batch, count_round=False)
            state.initial_tool_call = None
            state.checkpoint_boundary = StandardCheckpointBoundary.PREFLIGHT
            await ctx.checkpoint()
            state.checkpoint_boundary = StandardCheckpointBoundary.TOOL

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

        while result.has_tool_calls and state.tool_round < self._policy.max_tool_rounds:
            tool_batch = await ctx.tools.execute_many(result.tool_calls)
            state.record_tool_batch(tool_batch)

            if tool_batch.requires_suspension:
                if tool_batch.suspension_reason is None:
                    raise RuntimeError(
                        "Suspending Tool batch is missing a suspension reason"
                    )
                await ctx.checkpoint()
                return ctx.suspend(
                    reason=tool_batch.suspension_reason,
                    operation_ref=tool_batch.operation_ref,
                )

            decision = self._policy.evaluate(state)
            state.stopped_reason = (
                decision.reason
                if decision.type is StrategyDecisionType.FINALIZE
                else None
            )
            state.next_phase = (
                StandardPhase.FINAL_RESPONSE_GENERATION.value
                if state.stopped_reason
                else tool_followup_phase(state.tool_round)
            )
            await ctx.checkpoint()

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

        requires_terminal_recovery = bool(state.stopped_reason) and result.has_tool_calls
        if requires_terminal_recovery:
            result = await ctx.model.finalize(
                messages=state.messages,
                reason=state.stopped_reason or "Capability execution could not complete",
                phase=StandardPhase.FINAL_RESPONSE_GENERATION,
            )
            state.record_model_result(result)

        return ctx.complete(result)
