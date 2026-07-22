from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.processor import _trial_payload
from modules.evaluation.application.scoring import aggregate_evaluation, build_estimate
from modules.evaluation.domain.enums import (
    EvaluationMode,
    EvaluationRunStatus,
    EvaluationTrialStatus,
)
from modules.evaluation.infra.database.models import (
    EstimateRunModel,
    EvaluationRunModel,
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
    EvaluatorModelCallModel,
    ReleaseQualificationModel,
)
from modules.evaluation.infra.workers.concurrent_worker import (
    ConcurrentOutcomeAwareEvaluationRunProcessor,
    ConcurrentOutcomeAwareEvaluationRunWorker,
)
from shared.infra.config import Settings
from shared.infra.errors import ValidationError


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
        async with self._session_factory() as session:
            current = await session.get(EvaluationRunModel, run_id)
            is_experiment = bool(
                current is not None
                and current.mode == EvaluationMode.MODEL_EXPERIMENT.value
            )
        if not is_experiment:
            await super()._aggregate(run_id)
            return

        async with self._session_factory() as session, session.begin():
            run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
            if run is None:
                return
            if run.status == EvaluationRunStatus.CANCELLED.value:
                return
            run.status = EvaluationRunStatus.AGGREGATING.value

            suite = await session.get(EvaluationSuiteVersionModel, run.suite_version_id)
            if suite is None:
                raise ValidationError("Evaluation Suite version not found")

            trials = list(
                (
                    await session.scalars(
                        select(EvaluationTrialModel)
                        .where(EvaluationTrialModel.evaluation_run_id == run.id)
                        .order_by(EvaluationTrialModel.execution_order)
                    )
                ).all()
            )
            targets = {
                item.id: item
                for item in (
                    await session.scalars(
                        select(EvaluationTargetModel).where(
                            EvaluationTargetModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            }
            payloads = [
                _trial_payload(item, targets[item.evaluation_target_id])
                for item in trials
                if item.evaluation_target_id in targets
            ]
            complete_aggregate = aggregate_evaluation(
                payloads,
                suite.acceptance_policy,
            )
            side_results = {
                target.side: aggregate_evaluation(
                    [item for item in payloads if item["side"] == target.side],
                    suite.acceptance_policy,
                )
                for target in targets.values()
            }

            run.qualification_status = None
            run.overall_score = None
            run.pass_rate = None
            run.aggregate_result = {
                **complete_aggregate,
                "experiment": {
                    "type": EvaluationMode.MODEL_EXPERIMENT.value,
                    "qualification_eligible": False,
                    "reason": (
                        "The experimental target changes the Provider Model and is "
                        "not the deployed or versioned Agent configuration."
                    ),
                    "target_results": side_results,
                },
                "qualification": {
                    "eligible": False,
                    "status": None,
                    "reason": "model_experiment",
                },
            }

            # Defensive cleanup for any legacy experiment that may have been
            # aggregated before model_experiment became a distinct mode.
            await session.execute(
                delete(ReleaseQualificationModel).where(
                    ReleaseQualificationModel.evaluation_run_id == run.id
                )
            )

            model_call_cost = await session.scalar(
                select(func.sum(EvaluatorModelCallModel.cost_usd)).where(
                    EvaluatorModelCallModel.evaluation_run_id == run.id
                )
            )
            target_costs = [
                float((item.metrics or {}).get("cost_usd"))
                for item in trials
                if (item.metrics or {}).get("cost_usd") is not None
            ]
            run.measured_total_cost = sum(target_costs) + float(model_call_cost or 0)

            incomplete = any(
                item.status
                not in {
                    EvaluationTrialStatus.COMPLETED.value,
                    EvaluationTrialStatus.INCONCLUSIVE.value,
                }
                for item in trials
            )
            run.status = (
                EvaluationRunStatus.PARTIALLY_COMPLETED.value
                if incomplete
                else EvaluationRunStatus.COMPLETED.value
            )
            run.completed_at = datetime.now(timezone.utc)
            run.lease_owner = None
            run.lease_expires_at = None

            volume = int((suite.estimate_defaults or {}).get("volume", 10_000))
            existing_estimate_count = await session.scalar(
                select(func.count(EstimateRunModel.id)).where(
                    EstimateRunModel.evaluation_run_id == run.id
                )
            )
            if not existing_estimate_count:
                for target_id, evaluation_target in targets.items():
                    target_trials = [
                        item
                        for item in payloads
                        if item["side"] == evaluation_target.side
                        and item["status"] == EvaluationTrialStatus.COMPLETED.value
                    ]
                    estimate = build_estimate(
                        values=target_trials,
                        volume=volume,
                        target_type=evaluation_target.target_type,
                    )
                    session.add(
                        EstimateRunModel(
                            project_id=run.project_id,
                            evaluation_run_id=run.id,
                            target_id=target_id,
                            volume_unit="runs_per_month",
                            volume=volume,
                            assumptions={
                                "projection_method": "observed_trial_distribution",
                                "run_purpose": "evaluation",
                                "experiment_type": EvaluationMode.MODEL_EXPERIMENT.value,
                                "qualification_eligible": False,
                            },
                            observation_summary=estimate["observation_summary"],
                            price_snapshot=None,
                            scenarios=estimate["scenarios"],
                            confidence=estimate["confidence"],
                            limitations=[
                                *estimate["limitations"],
                                "Experimental model results do not qualify any Agent version.",
                            ],
                            created_by=run.requested_by,
                        )
                    )


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
