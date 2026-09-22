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
    StrategyOutputMode,
    StrategyOutcome,
    Suspended,
    strategy_phase_with_iteration,
)


DEFAULT_MAX_EXPERIMENT_ROUNDS = 5


class ScientificMethodPhase(ExecutionPhase):
    OBSERVATION = "observation"
    HYPOTHESIS_FORMULATION = "hypothesis_formulation"
    EVIDENCE_ANALYSIS = "evidence_analysis"
    CRITICAL_REVIEW = "critical_review"
    CONCLUSION = "conclusion"


class ScientificMethodStopReason(ExecutionStopReason):
    EXPERIMENT_ROUND_LIMIT = "experiment round limit reached"
    PROVIDER_REJECTED_FOLLOWUP = (
        "the scientific-method follow-up request was rejected by the provider"
    )


class ScientificMethodExecutionState(ExecutionState):
    phase: str | None = None
    experiment_round: int = 0
    after_evidence_phase: str | None = None
    stop_reason: ScientificMethodStopReason | None = None


@dataclass(frozen=True, slots=True)
class ScientificMethodExecutionPolicy(
    ExecutionPolicy[ScientificMethodExecutionState]
):
    max_experiment_rounds: int = DEFAULT_MAX_EXPERIMENT_ROUNDS

    def __post_init__(self) -> None:
        if self.max_experiment_rounds <= 0:
            raise ValueError("max_experiment_rounds must be positive")

    def stop_reason(
        self,
        state: ScientificMethodExecutionState,
    ) -> ScientificMethodStopReason | None:
        if state.experiment_round >= self.max_experiment_rounds:
            return ScientificMethodStopReason.EXPERIMENT_ROUND_LIMIT
        return None


_OBSERVATION_DIRECTIVE = (
    "Frame the current problem as an investigable question. Separate direct observations "
    "from assumptions, identify material unknowns, and determine what evidence would be "
    "relevant. Do not jump to a conclusion. Prefer reasoning from evidence already present; "
    "request Tools only when an observation cannot be established from the current context."
)

_HYPOTHESIS_DIRECTIVE = (
    "Formulate falsifiable hypotheses and plausible alternatives for the investigable "
    "question. State what evidence would distinguish them. If additional evidence is "
    "materially necessary, request only the smallest useful experiment through available "
    "Tools. Do not treat an untested hypothesis as a conclusion."
)

_CRITICAL_REVIEW_DIRECTIVE = (
    "Attempt to falsify the current provisional conclusion. Look for contradictory evidence, "
    "alternative explanations, unsupported assumptions, and the weakest evidential link. "
    "If a material uncertainty can still be tested, request only the Tools needed for that "
    "test. Otherwise, do not request Tools and prepare to conclude."
)

_CONCLUSION_DIRECTIVE = (
    "Produce the conclusion supported by the investigation. Distinguish observations and "
    "evidence from inference, identify relevant uncertainty, and avoid claiming more than "
    "the collected evidence supports. Do not request additional Tools unless a material "
    "factual gap makes a defensible conclusion impossible."
)

_LIMITED_CONCLUSION_DIRECTIVE = (
    "Conclude using only the evidence already collected. Explicitly distinguish verified "
    "evidence, inference, and unresolved uncertainty. Do not request additional Tools. "
    "Do not conceal that the investigation ended because an execution limit or provider "
    "failure prevented further testing."
)


def _is_evidence_phase(phase: str) -> bool:
    prefix = ScientificMethodPhase.EVIDENCE_ANALYSIS.value
    return phase == prefix or phase.startswith(f"{prefix}_")


class ScientificMethodExecutionStrategy(
    ExecutionStrategy[ScientificMethodExecutionState]
):
    """Hypothesis-driven execution with explicit evidence collection and falsification."""

    name = "scientific_method"
    state_type = ScientificMethodExecutionState

    def __init__(
        self,
        policy: ScientificMethodExecutionPolicy | None = None,
    ) -> None:
        self.policy = policy or ScientificMethodExecutionPolicy()

    def _directive(self, state: ScientificMethodExecutionState) -> str:
        phase = state.phase or ScientificMethodPhase.OBSERVATION.value
        if phase == ScientificMethodPhase.OBSERVATION.value:
            return _OBSERVATION_DIRECTIVE
        if phase == ScientificMethodPhase.HYPOTHESIS_FORMULATION.value:
            return _HYPOTHESIS_DIRECTIVE
        if _is_evidence_phase(phase):
            return (
                f"Evaluate the evidence collected in experiment round "
                f"{state.experiment_round}. Compare it against the competing hypotheses, "
                "identify contradictions and alternative explanations, and decide whether "
                "another minimal experiment is materially necessary. Request a Tool only "
                "when another test is needed; otherwise produce a provisional conclusion "
                "for critical review."
            )
        if phase == ScientificMethodPhase.CRITICAL_REVIEW.value:
            return _CRITICAL_REVIEW_DIRECTIVE
        if phase == ScientificMethodPhase.CONCLUSION.value:
            return _CONCLUSION_DIRECTIVE
        raise RuntimeError(f"Unsupported scientific-method phase: {phase}")

    def _after_evidence_phase(self, phase: str) -> str:
        if phase == ScientificMethodPhase.OBSERVATION.value:
            return ScientificMethodPhase.HYPOTHESIS_FORMULATION.value
        return ScientificMethodPhase.CRITICAL_REVIEW.value

    def _next_phase_without_tools(
        self,
        state: ScientificMethodExecutionState,
    ) -> str | None:
        phase = state.phase or ScientificMethodPhase.OBSERVATION.value
        if phase == ScientificMethodPhase.OBSERVATION.value:
            return ScientificMethodPhase.HYPOTHESIS_FORMULATION.value
        if phase == ScientificMethodPhase.HYPOTHESIS_FORMULATION.value:
            return ScientificMethodPhase.CRITICAL_REVIEW.value
        if _is_evidence_phase(phase):
            next_phase = (
                state.after_evidence_phase
                or ScientificMethodPhase.CRITICAL_REVIEW.value
            )
            state.after_evidence_phase = None
            return next_phase
        if phase == ScientificMethodPhase.CRITICAL_REVIEW.value:
            return ScientificMethodPhase.CONCLUSION.value
        if phase == ScientificMethodPhase.CONCLUSION.value:
            return None
        raise RuntimeError(f"Unsupported scientific-method phase: {phase}")

    async def execute(
        self,
        ctx: StrategyContext[ScientificMethodExecutionState],
    ) -> StrategyOutcome:
        state = ctx.state
        if state.phase is None:
            state.phase = ScientificMethodPhase.OBSERVATION.value

        while True:
            if (
                state.phase == ScientificMethodPhase.CONCLUSION.value
                and state.stop_reason is not None
            ):
                result = await ctx.model.finalize(
                    reason=state.stop_reason.value,
                    phase=ScientificMethodPhase.CONCLUSION,
                    directive=_LIMITED_CONCLUSION_DIRECTIVE,
                    output_mode=StrategyOutputMode.FINAL,
                )
                return Completed(result)

            try:
                result = await ctx.model.invoke(
                    phase=state.phase,
                    directive=self._directive(state),
                    output_mode=(
                        StrategyOutputMode.FINAL
                        if state.phase == ScientificMethodPhase.CONCLUSION.value
                        else StrategyOutputMode.INTERNAL
                    ),
                )
            except InstrumentedExecutionError:
                state.stop_reason = (
                    ScientificMethodStopReason.PROVIDER_REJECTED_FOLLOWUP
                )
                state.phase = ScientificMethodPhase.CONCLUSION.value
                continue

            if result.has_tool_calls:
                state.stop_reason = self.policy.stop_reason(state)
                if state.stop_reason is not None:
                    state.phase = ScientificMethodPhase.CONCLUSION.value
                    continue

                current_phase = state.phase
                tool_batch = await ctx.tools.execute_many(result.tool_calls)
                state.experiment_round += 1
                state.after_evidence_phase = self._after_evidence_phase(
                    current_phase
                )
                state.phase = strategy_phase_with_iteration(
                    ScientificMethodPhase.EVIDENCE_ANALYSIS,
                    state.experiment_round,
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

                await ctx.checkpoint(ExecutionCheckpointBoundary.TOOL)
                continue

            next_phase = self._next_phase_without_tools(state)
            if next_phase is None:
                return Completed(result)
            state.phase = next_phase


__all__ = [
    "DEFAULT_MAX_EXPERIMENT_ROUNDS",
    "ScientificMethodExecutionPolicy",
    "ScientificMethodExecutionState",
    "ScientificMethodExecutionStrategy",
    "ScientificMethodPhase",
    "ScientificMethodStopReason",
]
