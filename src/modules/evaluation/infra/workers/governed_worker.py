from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.processor import EvaluationRunProcessor, _trial_payload, _utc_now
from modules.evaluation.application.scoring import aggregate_evaluation, build_estimate
from modules.evaluation.domain.enums import EvaluationRunStatus, EvaluationTrialStatus
from modules.evaluation.infra.database.models import (
    EstimateRunModel,
    EvaluationRunModel,
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
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


def _policy_assessment(value: str | None) -> str:
    if value in {"qualified", "qualified_with_warnings"}:
        return "meets_policy"
    if value == "not_qualified":
        return "below_policy"
    return "inconclusive"


class GovernedEvaluationRunProcessor(ConcurrentOutcomeAwareEvaluationRunProcessor):
    """Calculate evidence and policy assessment without making a human decision."""

    async def _prepare_trials(self, run_id: UUID) -> None:
        # Preserve resumability without rewriting a legitimate single target as candidate.
        async with self._session_factory() as session, session.begin():
            await session.execute(
                update(EvaluationTrialModel)
                .where(
                    EvaluationTrialModel.evaluation_run_id == run_id,
                    EvaluationTrialModel.status.in_(
                        {
                            EvaluationTrialStatus.EXECUTING.value,
                            EvaluationTrialStatus.WAITING_RUNTIME.value,
                            EvaluationTrialStatus.JUDGING.value,
                        }
                    ),
                    EvaluationTrialModel.completed_at.is_(None),
                )
                .values(
                    status=EvaluationTrialStatus.PENDING.value,
                    failure_code=None,
                    failure_detail=None,
                )
            )
        await EvaluationRunProcessor._prepare_trials(self, run_id)

    async def _aggregate(self, run_id: UUID) -> None:
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
            target_rows = list(
                (
                    await session.scalars(
                        select(EvaluationTargetModel).where(
                            EvaluationTargetModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            targets = {item.id: item for item in target_rows}
            payloads = [
                _trial_payload(item, targets[item.evaluation_target_id])
                for item in trials
                if item.evaluation_target_id in targets
            ]
            complete_aggregate = aggregate_evaluation(payloads, suite.acceptance_policy)

            assessment_side = "candidate" if run.baseline_target_id else "single"
            assessment_payloads = [
                item for item in payloads if item["side"] == assessment_side
            ]
            assessment_aggregate = aggregate_evaluation(
                assessment_payloads,
                suite.acceptance_policy,
            )
            assessment_status = _policy_assessment(
                assessment_aggregate.get("qualification_status")
            )

            target_summaries: list[dict[str, Any]] = []
            for target in target_rows:
                values = [item for item in payloads if item["side"] == target.side]
                side_aggregate = aggregate_evaluation(values, suite.acceptance_policy)
                raw_total = len(values)
                raw_passed = sum(1 for item in values if item.get("passed") is True)
                target_summaries.append(
                    {
                        "target_id": str(target.id),
                        "side": target.side,
                        "weighted_score": side_aggregate.get("overall_score"),
                        "weighted_pass_rate": side_aggregate.get("pass_rate"),
                        "raw_passed": raw_passed,
                        "raw_total": raw_total,
                        "raw_pass_rate": (
                            raw_passed / raw_total * 100 if raw_total else None
                        ),
                        "critical_failures": side_aggregate.get("critical_failures", 0),
                        "completed_trial_count": side_aggregate.get(
                            "completed_trial_count", 0
                        ),
                    }
                )

            preserved = (
                dict(run.aggregate_result)
                if isinstance(run.aggregate_result, dict)
                else {}
            )
            run.qualification_status = None
            run.overall_score = assessment_aggregate.get("overall_score")
            run.pass_rate = assessment_aggregate.get("pass_rate")
            run.aggregate_result = {
                **preserved,
                **complete_aggregate,
                "assessment": {
                    **assessment_aggregate,
                    "status": assessment_status,
                    "policy_status": assessment_aggregate.get(
                        "qualification_status"
                    ),
                    "decision_required": True,
                },
                "target_summaries": target_summaries,
                "decision": {"status": "pending"},
            }

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
            run.completed_at = _utc_now()
            run.lease_owner = None
            run.lease_expires_at = None

            # New Runs never create an automatic qualification decision.
            await session.execute(
                delete(ReleaseQualificationModel).where(
                    ReleaseQualificationModel.evaluation_run_id == run.id
                )
            )

            volume = int((suite.estimate_defaults or {}).get("volume", 10_000))
            existing_estimate_count = await session.scalar(
                select(func.count(EstimateRunModel.id)).where(
                    EstimateRunModel.evaluation_run_id == run.id
                )
            )
            if not existing_estimate_count:
                for target in target_rows:
                    completed_values = [
                        item
                        for item in payloads
                        if item["side"] == target.side
                        and item["status"] == EvaluationTrialStatus.COMPLETED.value
                    ]
                    if not completed_values:
                        continue
                    estimate = build_estimate(
                        values=completed_values,
                        volume=volume,
                        target_type=target.target_type,
                    )
                    session.add(
                        EstimateRunModel(
                            project_id=run.project_id,
                            evaluation_run_id=run.id,
                            target_id=target.id,
                            volume_unit="runs_per_month",
                            volume=volume,
                            assumptions={
                                "projection_method": "observed_trial_distribution",
                                "run_purpose": "evaluation",
                            },
                            observation_summary=estimate["observation_summary"],
                            price_snapshot=None,
                            price_snapshot_hash="none",
                            scenarios=estimate["scenarios"],
                            confidence=estimate["confidence"],
                            limitations=estimate["limitations"],
                            created_by=run.requested_by,
                        )
                    )


class GovernedEvaluationRunWorker(ConcurrentOutcomeAwareEvaluationRunWorker):
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
        self._processor = GovernedEvaluationRunProcessor(
            session_factory,
            settings=settings,
        )

    async def _claim(self) -> UUID | None:
        while True:
            run_id = await super()._claim()
            if run_id is None:
                return None
            async with self._session_factory() as session, session.begin():
                run = await session.get(EvaluationRunModel, run_id, with_for_update=True)
                if run is None:
                    continue
                if run.mode != "model_experiment":
                    return run_id
                run.status = EvaluationRunStatus.FAILED.value
                run.failure_code = "legacy_model_experiment_unsupported"
                run.failure_detail = (
                    "Model Experiment was removed. This historical Run cannot be "
                    "resumed because executing it as a real snapshot Evaluation would "
                    "produce incorrect evidence."
                )
                run.completed_at = _utc_now()
                run.qualification_status = None
                run.lease_owner = None
                run.lease_expires_at = None


__all__ = ["GovernedEvaluationRunProcessor", "GovernedEvaluationRunWorker"]
