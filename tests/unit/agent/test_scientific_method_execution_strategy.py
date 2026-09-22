from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.strategy_sdk import (
    Completed,
    StrategyModelResult,
    StrategyOutputMode,
    StrategyToolBatch,
)
from modules.agent.infra.execution.strategies.scientific_method import (
    ScientificMethodExecutionPolicy,
    ScientificMethodExecutionState,
    ScientificMethodExecutionStrategy,
    ScientificMethodPhase,
    ScientificMethodStopReason,
)


def _result(
    content: str,
    tool_calls: list[dict] | None = None,
) -> StrategyModelResult:
    return StrategyModelResult(
        message=SimpleNamespace(content=content, tool_calls=tool_calls or [])
    )


class _Model:
    def __init__(self, responses: list[StrategyModelResult]) -> None:
        self.responses = list(responses)
        self.invocations: list[dict[str, object]] = []
        self.finalizations: list[dict[str, object]] = []

    async def invoke(self, *, phase=None, directive=None, output_mode=None):
        self.invocations.append(
            {
                "phase": phase,
                "directive": directive,
                "output_mode": output_mode,
            }
        )
        return self.responses.pop(0)

    async def finalize(
        self,
        *,
        reason,
        phase,
        directive=None,
        output_mode=None,
    ):
        self.finalizations.append(
            {
                "reason": reason,
                "phase": phase,
                "directive": directive,
                "output_mode": output_mode,
            }
        )
        return _result("limited conclusion")


class _Tools:
    def __init__(self) -> None:
        self.calls: list[tuple[dict, ...]] = []

    async def execute_many(self, tool_calls):
        self.calls.append(tuple(tool_calls))
        return StrategyToolBatch(results=(), messages=(), has_failures=False)


class _Context:
    def __init__(
        self,
        model: _Model,
        state: ScientificMethodExecutionState | None = None,
    ) -> None:
        self.state = state or ScientificMethodExecutionState()
        self.model = model
        self.tools = _Tools()
        self.checkpoints: list[object] = []

    async def checkpoint(self, boundary=None):
        self.checkpoints.append(boundary)


@pytest.mark.asyncio
async def test_scientific_method_uses_directives_and_reopens_investigation() -> None:
    model = _Model(
        [
            _result("observations"),
            _result(
                "",
                [{"id": "experiment-1", "name": "search", "args": {"q": "a"}}],
            ),
            _result("evidence one"),
            _result(
                "",
                [{"id": "experiment-2", "name": "search", "args": {"q": "b"}}],
            ),
            _result("evidence two"),
            _result("critical review complete"),
            _result("final conclusion"),
        ]
    )
    ctx = _Context(model)

    outcome = await ScientificMethodExecutionStrategy().execute(ctx)

    assert isinstance(outcome, Completed)
    assert outcome.result.content == "final conclusion"
    assert ctx.state.experiment_round == 2
    assert len(ctx.tools.calls) == 2
    assert len(ctx.checkpoints) == 2

    phases = [item["phase"] for item in model.invocations]
    assert phases == [
        "observation",
        "hypothesis_formulation",
        "evidence_analysis_1",
        "critical_review",
        "evidence_analysis_2",
        "critical_review",
        "conclusion",
    ]
    directives = [str(item["directive"]) for item in model.invocations]
    assert "investigable question" in directives[0]
    assert "falsifiable hypotheses" in directives[1]
    assert "experiment round 1" in directives[2]
    assert "Attempt to falsify" in directives[3]
    assert "experiment round 2" in directives[4]
    assert "Produce the conclusion" in directives[-1]
    assert [item["output_mode"] for item in model.invocations] == [
        StrategyOutputMode.INTERNAL,
        StrategyOutputMode.INTERNAL,
        StrategyOutputMode.INTERNAL,
        StrategyOutputMode.INTERNAL,
        StrategyOutputMode.INTERNAL,
        StrategyOutputMode.INTERNAL,
        StrategyOutputMode.FINAL,
    ]


@pytest.mark.asyncio
async def test_scientific_method_concludes_from_collected_evidence_after_provider_failure() -> None:
    class _ProviderFailingModel(_Model):
        async def invoke(self, *, phase=None, directive=None, output_mode=None):
            if phase == ScientificMethodPhase.CRITICAL_REVIEW.value:
                self.invocations.append(
                    {
                        "phase": phase,
                        "directive": directive,
                        "output_mode": output_mode,
                    }
                )
                raise InstrumentedExecutionError("provider rejected follow-up")
            return await super().invoke(
                phase=phase,
                directive=directive,
                output_mode=output_mode,
            )

    model = _ProviderFailingModel(
        [
            _result(
                "",
                [{"id": "experiment-1", "name": "search", "args": {"q": "a"}}],
            ),
            _result("evidence one"),
            _result("hypothesis"),
        ]
    )
    ctx = _Context(model)

    outcome = await ScientificMethodExecutionStrategy().execute(ctx)

    assert isinstance(outcome, Completed)
    assert outcome.result.content == "limited conclusion"
    assert ctx.state.experiment_round == 1
    assert (
        ctx.state.stop_reason
        == ScientificMethodStopReason.PROVIDER_REJECTED_FOLLOWUP
    )
    assert [item["phase"] for item in model.invocations] == [
        ScientificMethodPhase.OBSERVATION.value,
        "evidence_analysis_1",
        ScientificMethodPhase.HYPOTHESIS_FORMULATION.value,
        ScientificMethodPhase.CRITICAL_REVIEW.value,
    ]
    assert len(model.finalizations) == 1
    assert (
        model.finalizations[0]["output_mode"]
        == StrategyOutputMode.FINAL
    )
    assert "evidence already collected" in str(
        model.finalizations[0]["directive"]
    )




@pytest.mark.asyncio
async def test_scientific_method_stops_before_exceeding_experiment_limit() -> None:
    model = _Model(
        [
            _result("observations"),
            _result(
                "",
                [{"id": "experiment-1", "name": "search", "args": {"q": "a"}}],
            ),
            _result(
                "",
                [{"id": "experiment-2", "name": "search", "args": {"q": "b"}}],
            ),
        ]
    )
    ctx = _Context(model)
    strategy = ScientificMethodExecutionStrategy(
        ScientificMethodExecutionPolicy(max_experiment_rounds=1)
    )

    outcome = await strategy.execute(ctx)

    assert isinstance(outcome, Completed)
    assert outcome.result.content == "limited conclusion"
    assert ctx.state.experiment_round == 1
    assert len(ctx.tools.calls) == 1
    assert (
        ctx.state.stop_reason
        == ScientificMethodStopReason.EXPERIMENT_ROUND_LIMIT
    )
    assert len(model.finalizations) == 1
    finalization = model.finalizations[0]
    assert finalization["phase"] == ScientificMethodPhase.CONCLUSION
    assert "Do not request additional Tools" in str(finalization["directive"])
    assert finalization["output_mode"] == StrategyOutputMode.FINAL
