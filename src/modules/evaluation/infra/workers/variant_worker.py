from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.domain.enums import EvaluationMode
from modules.evaluation.infra.database.models import (
    EvaluationRunModel,
    EvaluationTargetModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
    ReleaseQualificationModel,
)
from modules.evaluation.infra.workers.concurrent_worker import (
    ConcurrentOutcomeAwareEvaluationRunProcessor,
    ConcurrentOutcomeAwareEvaluationRunWorker,
)
from shared.infra.config import Settings


class VariantAwareConcurrentEvaluationRunProcessor(
    ConcurrentOutcomeAwareEvaluationRunProcessor
):
    """Execute explicit model experiments without treating them as qualifications."""

    async def _execute_agent(
        self,
        trial: EvaluationTrialModel,
        target: EvaluationTargetModel,
        case: EvaluationTestCaseModel,
    ) -> tuple[dict[str, Any], dict[str, Any], None, UUID | None]:
        snapshot = target.snapshot or {}
        if not isinstance(snapshot.get("evaluation_variant"), dict):
            return await super()._execute_agent(trial, target, case)

        # The canonical Agent runtime applies snapshot_override for draft-style
        # invocations. The persisted target remains an immutable experimental
        # derivative and never changes the Agent Draft or any Release.
        runtime_target = SimpleNamespace(
            entity_id=target.entity_id,
            agent_release_id=None,
            snapshot=snapshot,
            source_type="draft",
            side=target.side,
        )
        return await super()._execute_agent(trial, runtime_target, case)

    async def _persist_final_result(self, **kwargs) -> None:
        await super()._persist_final_result(**kwargs)
        judge = kwargs["judge"]
        trial = kwargs["trial"]
        async with self._session_factory() as session, session.begin():
            row = await session.get(
                EvaluationTrialModel,
                trial.id,
                with_for_update=True,
            )
            if row is None:
                return
            metrics = dict(row.metrics or {})
            previous_judge_cost = float(
                metrics.get("judge_retry_previous_cost_usd") or 0
            )
            current_judge_cost = float(metrics.get("judge_cost_usd") or 0)
            if previous_judge_cost:
                metrics["judge_cost_usd"] = (
                    previous_judge_cost + current_judge_cost
                )
                metrics["judge_latest_attempt_cost_usd"] = current_judge_cost
                row.metrics = metrics

            if judge.structured_result is not None:
                return
            technical_error = str(judge.error or "")
            lowered = technical_error.lower()
            if "judge_output_length_limit" in lowered:
                code = "judge_output_length_limit"
                detail = (
                    "The Judge exhausted its output budget before completing the "
                    "structured score. Agent evidence was preserved and the judgment "
                    "can be retried without re-running the Agent or Tools."
                )
            elif "json" in lowered or "parse" in lowered:
                code = "judge_invalid_json"
                detail = (
                    "The Judge returned an invalid structured score. Agent evidence was "
                    "preserved and the judgment can be retried."
                )
            else:
                code = "judge_failed"
                detail = (
                    "The Judge could not complete this score. Agent evidence was "
                    "preserved for a judgment-only retry."
                )
            row.failure_code = code
            row.failure_detail = detail
            metrics = dict(row.metrics or {})
            metrics["judge_failure_code"] = code
            row.metrics = metrics

    async def _aggregate(self, run_id: UUID) -> None:
        await super()._aggregate(run_id)
        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None or run.mode != EvaluationMode.MODEL_EXPERIMENT.value:
                return

            # The base aggregator computes the comparative evidence. Model
            # experiments retain those metrics, but can never create or expose a
            # qualification for Draft, Staging, Release or the Agent itself.
            await session.execute(
                delete(ReleaseQualificationModel).where(
                    ReleaseQualificationModel.evaluation_run_id == run.id
                )
            )
            aggregate = dict(run.aggregate_result or {})
            reference_result = aggregate.get("qualification")
            aggregate["experiment"] = {
                "type": EvaluationMode.MODEL_EXPERIMENT.value,
                "qualification_eligible": False,
                "reason": (
                    "The baseline target changes the Provider Model and is an "
                    "experimental derivative of the reference Agent snapshot."
                ),
                "reference_result": reference_result,
            }
            aggregate["qualification"] = {
                "eligible": False,
                "status": None,
                "reason": "model_experiment",
            }
            run.aggregate_result = aggregate
            run.qualification_status = None
            run.overall_score = None
            run.pass_rate = None


class VariantAwareConcurrentEvaluationRunWorker(
    ConcurrentOutcomeAwareEvaluationRunWorker
):
    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings | None = None,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(
            session_factory,
            settings=settings,
            worker_id=worker_id,
        )
        self._processor = VariantAwareConcurrentEvaluationRunProcessor(
            session_factory,
            settings=settings,
        )


__all__ = [
    "VariantAwareConcurrentEvaluationRunProcessor",
    "VariantAwareConcurrentEvaluationRunWorker",
]
