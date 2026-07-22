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


def _revision(aggregate: dict[str, Any]) -> int:
    try:
        return max(1, int(aggregate.get("evidence_revision") or 1))
    except (TypeError, ValueError):
        return 1


def _case_outcomes(values: list[EvaluationTrialModel]) -> dict[str, int]:
    grouped: dict[UUID, list[EvaluationTrialModel]] = {}
    for trial in values:
        grouped.setdefault(trial.test_case_id, []).append(trial)
    fully_passed = 0
    mixed = 0
    consistently_failed = 0
    needs_attention = 0
    for trials in grouped.values():
        passed = sum(1 for item in trials if item.passed is True)
        conclusive = sum(
            1
            for item in trials
            if item.status == EvaluationTrialStatus.COMPLETED.value
            and item.passed is not None
        )
        if passed == len(trials) and conclusive == len(trials):
            fully_passed += 1
        elif passed > 0:
            mixed += 1
            needs_attention += 1
        else:
            consistently_failed += 1
            needs_attention += 1
    return {
        "case_count": len(grouped),
        "cases_fully_passed": fully_passed,
        "cases_mixed": mixed,
        "cases_consistently_failed": consistently_failed,
        "cases_needing_attention": needs_attention,
    }


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
            if run is None or run.status == EvaluationRunStatus.CANCELLED.value:
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
            payload_by_trial = {
                item.id: _trial_payload(item, targets[item.evaluation_target_id])
                for item in trials
                if item.evaluation_target_id in targets
            }
            payloads = list(payload_by_trial.values())
            complete_aggregate = aggregate_evaluation(payloads, suite.acceptance_policy)

            primary_target_id = run.candidate_target_id
            if primary_target_id is None and target_rows:
                primary_target_id = target_rows[0].id
            assessment_trials = [
                item for item in trials if item.evaluation_target_id == primary_target_id
            ]
            assessment_payloads = [
                payload_by_trial[item.id]
                for item in assessment_trials
                if item.id in payload_by_trial
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
                target_trials = [
                    item for item in trials if item.evaluation_target_id == target.id
                ]
                values = [
                    payload_by_trial[item.id]
                    for item in target_trials
                    if item.id in payload_by_trial
                ]
                target_aggregate = aggregate_evaluation(values, suite.acceptance_policy)
                raw_total = len(values)
                raw_passed = sum(1 for item in values if item.get("passed") is True)
                target_summaries.append(
                    {
                        "target_id": str(target.id),
                        "side": target.side,
                        "weighted_score": target_aggregate.get("overall_score"),
                        "weighted_pass_rate": target_aggregate.get("pass_rate"),
                        "trial_outcomes_passed": raw_passed,
                        "trial_outcomes_total": raw_total,
                        "raw_passed": raw_passed,
                        "raw_total": raw_total,
                        "raw_pass_rate": (
                            raw_passed / raw_total * 100 if raw_total else None
                        ),
                        "critical_failures": target_aggregate.get("critical_failures", 0),
                        "completed_trial_count": target_aggregate.get(
                            "completed_trial_count", 0
                        ),
                        **_case_outcomes(target_trials),
                    }
                )

            preserved = (
                dict(run.aggregate_result)
                if isinstance(run.aggregate_result, dict)
                else {}
            )
            evidence_revision = _revision(preserved)
            retry_metadata = preserved.get("judgment_retry")
            if isinstance(retry_metadata, dict) and retry_metadata.get("started_at"):
                retry_metadata = {
                    **retry_metadata,
                    "status": "completed",
                    "completed_at": _utc_now().isoformat(),
                }

            run.qualification_status = None
            run.overall_score = assessment_aggregate.get("overall_score")
            run.pass_rate = assessment_aggregate.get("pass_rate")
            run.aggregate_result = {
                **preserved,
                **complete_aggregate,
                "evidence_revision": evidence_revision,
                "assessment": {
                    **assessment_aggregate,
                    "status": assessment_status,
                    "policy_status": assessment_aggregate.get(
                        "qualification_status"
                    ),
                    "decision_required": True,
                    "target_id": str(primary_target_id) if primary_target_id else None,
                },
                "target_summaries": target_summaries,
                "decision": {"status": "pending", "evidence_revision": evidence_revision},
                "judgment_retry": retry_metadata,
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
            existing_estimates = list(
                (
                    await session.scalars(
                        select(EstimateRunModel).where(
                            EstimateRunModel.evaluation_run_id == run.id
                        )
                    )
                ).all()
            )
            for target in target_rows:
                has_default_for_revision = any(
                    item.target_id == target.id
                    and (item.assumptions or {}).get("origin") == "suite_default"
                    and int((item.assumptions or {}).get("evidence_revision") or 1)
                    == evidence_revision
                    for item in existing_estimates
                )
                if has_default_for_revision:
                    continue
                completed_values = [
                    payload_by_trial[item.id]
                    for item in trials
                    if item.evaluation_target_id == target.id
                    and item.id in payload_by_trial
                    and item.status == EvaluationTrialStatus.COMPLETED.value
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
                            "origin": "suite_default",
                            "evidence_revision": evidence_revision,
                            "cost_scope": "target_runtime_only",
                        },
                        observation_summary=estimate["observation_summary"],
                        price_snapshot=None,
                        price_snapshot_hash=f"none-r{evidence_revision}",
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
