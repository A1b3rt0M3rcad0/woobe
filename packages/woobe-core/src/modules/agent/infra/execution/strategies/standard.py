from __future__ import annotations

from dataclasses import dataclass

from modules.agent.application.interfaces.execution_strategy import (
    ExecutionStrategy,
    STANDARD_EXECUTION_COMPATIBILITY,
)
from modules.agent.application.strategy_sdk import (
    Completed,
    ExecutionCheckpointBoundary,
    ExecutionPhase,
    ExecutionPolicy,
    ExecutionState,
    ExecutionStopReason,
    StrategyContext,
    StrategyContextTarget,
    StrategyExecutionError,
    StrategyOutcome,
    Suspended,
    strategy_phase_with_iteration,
)


DEFAULT_MAX_TOOL_ROUNDS = 5
DEFAULT_MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS = 2
DEFAULT_MAX_EMPTY_OUTPUT_RETRIES = 1
MAX_TOOL_ROUNDS = DEFAULT_MAX_TOOL_ROUNDS
MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS = (
    DEFAULT_MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS
)


class StandardPhase(ExecutionPhase):
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    CONTEXT_COMPACTION = "context_compaction"
    RESPONSE_GENERATION = "response_generation"
    CAPABILITY_RESPONSE_GENERATION = "capability_response_generation"
    TOOL_FOLLOWUP = "tool_followup"
    FINAL_RESPONSE_GENERATION = "final_response_generation"
    FALLBACK_RESPONSE_GENERATION = "fallback_response_generation"


class StandardStopReason(ExecutionStopReason):
    REPEATED_SEMANTIC_FAILURES = "repeated semantic capability failures"
    CAPABILITY_ROUND_LIMIT = "capability round limit reached"
    PROVIDER_REJECTED_FOLLOWUP = (
        "the capability follow-up request was rejected by the provider"
    )


class StandardExecutionState(ExecutionState):
    phase: str | None = None
    preflight_resolved: bool = False
    tool_round: int = 0
    consecutive_failures: int = 0
    knowledge_resolved: bool = False
    stop_reason: StandardStopReason | None = None


@dataclass(frozen=True, slots=True)
class StandardExecutionPolicy(ExecutionPolicy[StandardExecutionState]):
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS
    max_consecutive_failures: int = DEFAULT_MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS
    max_empty_output_retries: int = DEFAULT_MAX_EMPTY_OUTPUT_RETRIES

    def __post_init__(self) -> None:
        if self.max_tool_rounds <= 0:
            raise ValueError("max_tool_rounds must be positive")
        if self.max_consecutive_failures <= 0:
            raise ValueError("max_consecutive_failures must be positive")
        if self.max_empty_output_retries < 0:
            raise ValueError("max_empty_output_retries must not be negative")

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
    compatibility = STANDARD_EXECUTION_COMPATIBILITY

    def __init__(self, policy: StandardExecutionPolicy | None = None) -> None:
        self.policy = policy or StandardExecutionPolicy()

    async def _fallback_or_raise(
        self,
        ctx: StrategyContext[StandardExecutionState],
        error: StrategyExecutionError,
    ):
        if not ctx.model.fallback_available:
            raise error
        no_tools = ctx.tools.none()
        invocation = await ctx.context.prepare(
            phase=StandardPhase.FALLBACK_RESPONSE_GENERATION,
            tools=no_tools,
            target=StrategyContextTarget.FALLBACK,
        )
        return await ctx.model.invoke_fallback(
            invocation,
            primary_error=str(error),
        )

    async def _repair_output_if_required(
        self,
        ctx: StrategyContext[StandardExecutionState],
        result,
    ):
        if ctx.output.requires_repair(result):
            return await ctx.output.repair(result, phase="json_repair")
        return result

    async def _recover_empty_public_output(
        self,
        ctx: StrategyContext[StandardExecutionState],
        result,
    ):
        """Give a terminal empty response one bounded generation retry.

        Capability results are reused through prepare_final and Tools stay disabled,
        so recovery cannot replay side effects. The outer runtime retains its terminal
        empty-output guard as defense in depth if the bounded retry also returns empty.
        """

        result = await self._repair_output_if_required(ctx, result)
        attempts = 0
        while (
            not ctx.output.has_public_output(result)
            and attempts < self.policy.max_empty_output_retries
        ):
            attempts += 1
            reason = "Model completed without producing public output"
            invocation = await ctx.context.prepare_final(
                reason=reason,
                phase=StandardPhase.FINAL_RESPONSE_GENERATION,
                tools=ctx.tools.none(),
            )
            try:
                result = await ctx.model.invoke(invocation)
            except StrategyExecutionError as exc:
                result = await self._fallback_or_raise(ctx, exc)
            result = await self._repair_output_if_required(ctx, result)
        return result

    async def execute(
        self,
        ctx: StrategyContext[StandardExecutionState],
    ) -> StrategyOutcome:
        state = ctx.state

        if not state.preflight_resolved:
            initial_tool_call = ctx.bootstrap.initial_tool_call
            if initial_tool_call is not None:
                await ctx.tools.execute_many([initial_tool_call])
            state.preflight_resolved = True
            if initial_tool_call is not None:
                await ctx.checkpoint(ExecutionCheckpointBoundary.PREFLIGHT)

        if state.phase is None:
            state.phase = (
                StandardPhase.CAPABILITY_RESPONSE_GENERATION.value
                if ctx.tools.has_any
                else StandardPhase.RESPONSE_GENERATION.value
            )

        if not state.knowledge_resolved:
            knowledge = await ctx.knowledge.retrieve(
                conversation=ctx.conversation,
                phase=StandardPhase.KNOWLEDGE_RETRIEVAL,
            )
            if knowledge.found:
                ctx.context.include_knowledge(knowledge)
            state.knowledge_resolved = True

        await ctx.context.compact(
            phase=StandardPhase.CONTEXT_COMPACTION,
        )

        if state.phase == StandardPhase.FINAL_RESPONSE_GENERATION.value:
            reason = (
                state.stop_reason.value
                if state.stop_reason is not None
                else "Capability execution could not complete"
            )
            no_tools = ctx.tools.none()
            invocation = await ctx.context.prepare_final(
                reason=reason,
                phase=StandardPhase.FINAL_RESPONSE_GENERATION,
                tools=no_tools,
            )
            try:
                result = await ctx.model.finalize(
                    invocation,
                    reason=reason,
                )
            except StrategyExecutionError as exc:
                result = await self._fallback_or_raise(ctx, exc)
            result = await self._recover_empty_public_output(ctx, result)
            return Completed(result)

        tools = ctx.tools.all()
        invocation = await ctx.context.prepare(phase=state.phase, tools=tools)
        try:
            result = await ctx.model.invoke(invocation)
        except StrategyExecutionError as exc:
            result = await self._fallback_or_raise(ctx, exc)

        while result.has_tool_calls and state.tool_round < self.policy.max_tool_rounds:
            tool_batch = await ctx.tools.execute_many(result.tool_calls)
            state.tool_round += 1
            state.consecutive_failures = (
                state.consecutive_failures + 1 if tool_batch.has_failures else 0
            )

            if tool_batch.requires_suspension:
                if tool_batch.suspension_reason is None:
                    raise RuntimeError(
                        "Suspending Tool batch is missing a suspension reason"
                    )
                state.phase = strategy_phase_with_iteration(
                    StandardPhase.TOOL_FOLLOWUP,
                    state.tool_round,
                )
                await ctx.checkpoint(ExecutionCheckpointBoundary.TOOL)
                return Suspended(
                    reason=tool_batch.suspension_reason,
                    operation_ref=tool_batch.operation_ref,
                    metadata=tool_batch.suspension_metadata,
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
                await ctx.context.compact(
                    phase=StandardPhase.CONTEXT_COMPACTION,
                )
                invocation = await ctx.context.prepare(
                    phase=state.phase,
                    tools=tools,
                )
                result = await ctx.model.invoke(invocation)
            except StrategyExecutionError as exc:
                if ctx.model.fallback_available:
                    result = await self._fallback_or_raise(ctx, exc)
                    state.phase = StandardPhase.FALLBACK_RESPONSE_GENERATION.value
                    break
                state.stop_reason = StandardStopReason.PROVIDER_REJECTED_FOLLOWUP
                state.phase = StandardPhase.FINAL_RESPONSE_GENERATION.value
                break

        if state.stop_reason is not None and result.has_tool_calls:
            await ctx.context.compact(
                phase=StandardPhase.CONTEXT_COMPACTION,
            )
            no_tools = ctx.tools.none()
            invocation = await ctx.context.prepare_final(
                reason=state.stop_reason.value,
                phase=StandardPhase.FINAL_RESPONSE_GENERATION,
                tools=no_tools,
            )
            try:
                result = await ctx.model.finalize(
                    invocation,
                    reason=state.stop_reason.value,
                )
            except StrategyExecutionError as exc:
                result = await self._fallback_or_raise(ctx, exc)

        result = await self._recover_empty_public_output(ctx, result)
        return Completed(result)


__all__ = [
    "DEFAULT_MAX_EMPTY_OUTPUT_RETRIES",
    "MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS",
    "MAX_TOOL_ROUNDS",
    "StandardExecutionPolicy",
    "StandardExecutionState",
    "StandardExecutionStrategy",
    "StandardPhase",
    "StandardStopReason",
]
