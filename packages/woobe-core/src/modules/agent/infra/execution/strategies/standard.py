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
    StrategyContextContribution,
    StrategyContextTarget,
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

    async def _fallback_or_raise(
        self,
        ctx: StrategyContext[StandardExecutionState],
        error: InstrumentedExecutionError,
    ):
        if not ctx.model.fallback_available:
            raise error
        no_tools = ctx.tools.none()
        invocation = await ctx.context.assemble(
            phase=StandardPhase.FALLBACK_RESPONSE_GENERATION,
            tools=no_tools,
            target=StrategyContextTarget.FALLBACK,
        )
        return await ctx.model.invoke_fallback(
            context=invocation,
            primary_error=str(error),
            phase=StandardPhase.FALLBACK_RESPONSE_GENERATION,
            tools=no_tools,
        )

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
                phase="knowledge_retrieval",
            )
            state.knowledge_resolved = True
            if knowledge.found:
                ctx.context.set(
                    StrategyContextContribution(
                        key="knowledge.primary",
                        source_type="KNOWLEDGE",
                        content=knowledge.content,
                        metadata={
                            "retrieval": dict(knowledge.metadata),
                            "sources": [
                                source.model_dump(mode="json")
                                for source in knowledge.sources
                            ],
                        },
                    )
                )

        if state.phase == StandardPhase.FINAL_RESPONSE_GENERATION.value:
            reason = (
                state.stop_reason.value
                if state.stop_reason is not None
                else "Capability execution could not complete"
            )
            no_tools = ctx.tools.none()
            invocation = await ctx.context.assemble_final(
                reason=reason,
                phase=StandardPhase.FINAL_RESPONSE_GENERATION,
                tools=no_tools,
            )
            try:
                result = await ctx.model.finalize(
                    reason=reason,
                    phase=StandardPhase.FINAL_RESPONSE_GENERATION,
                    context=invocation,
                    tools=no_tools,
                )
            except InstrumentedExecutionError as exc:
                result = await self._fallback_or_raise(ctx, exc)
            if ctx.output.requires_repair(result):
                result = await ctx.output.repair(
                    result,
                    phase="json_repair",
                )
            return Completed(result)

        tools = ctx.tools.all()
        invocation = await ctx.context.assemble(
            phase=state.phase,
            tools=tools,
        )
        try:
            result = await ctx.model.invoke(
                context=invocation,
                tools=tools,
                phase=state.phase,
            )
        except InstrumentedExecutionError as exc:
            result = await self._fallback_or_raise(ctx, exc)

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
                    tools=tools,
                    phase=state.phase,
                )
            except InstrumentedExecutionError as exc:
                if ctx.model.fallback_available:
                    result = await self._fallback_or_raise(ctx, exc)
                    state.phase = StandardPhase.FALLBACK_RESPONSE_GENERATION.value
                    break
                state.stop_reason = StandardStopReason.PROVIDER_REJECTED_FOLLOWUP
                state.phase = StandardPhase.FINAL_RESPONSE_GENERATION.value
                break

        if state.stop_reason is not None and result.has_tool_calls:
            no_tools = ctx.tools.none()
            invocation = await ctx.context.assemble_final(
                reason=state.stop_reason.value,
                phase=StandardPhase.FINAL_RESPONSE_GENERATION,
                tools=no_tools,
            )
            try:
                result = await ctx.model.finalize(
                    reason=state.stop_reason.value,
                    phase=StandardPhase.FINAL_RESPONSE_GENERATION,
                    context=invocation,
                    tools=no_tools,
                )
            except InstrumentedExecutionError as exc:
                result = await self._fallback_or_raise(ctx, exc)

        if ctx.output.requires_repair(result):
            result = await ctx.output.repair(
                result,
                phase="json_repair",
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
